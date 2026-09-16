"""任务进度提交业务规则校验回归(B3)。

背景:修复前 update_progress 只校验"任务存在 + 解锁态",未校验 task.status / defaultCompleted:
  - 停用任务(status=0)可被商家提交 completed,写入 merchant_task_progress(status=1 任务才参与派生,
    停用任务被 _find_enabled_by_stage_ids 剔除)-> 产生与派生口径不一致的垃圾进度记录。
规则(真源 project/docs/阶段隔离规则与阶段二任务清单.md §1.3 停用任务自动剔除):
  - task.status != 1 -> 400(停用任务不可提交);
  - default_completed=1 的任务完成态由系统派生:可幂等提交 completed(前端"完成整个阶段"会包含它们),
    但不可提交 pending(不可把系统默认完成改为未完成)-> 400。
NestJS 对账:backend updateProgress/findByTaskId 同样无此校验(仅 400 任务不存在 / 403 未解锁),
本项比 NestJS 更严格,但错误码沿用既有 400 口径。

隔离:自建临时二级任务(_test_ 前缀 taskId,status=0 不参与派生;defaultCompleted=1 被派生豁免),
finally 删除任务与临时商家。
"""

import uuid

from sqlalchemy import text

from app.core.security import create_merchant_token

from tests.conftest import cleanup_temp_merchant, make_temp_merchant

_TASK_IDS = []


def _headers(merchant_id: str) -> dict:
    return {"Authorization": f"Bearer {create_merchant_token(merchant_id)}"}


def _make_task(session, status: int, default_completed: int) -> str:
    task_id = "_test_" + uuid.uuid4().hex[:10]
    session.execute(
        text(
            "INSERT INTO second_level_task (taskId, firstLevelTaskId, stageId, title, type, completionType, "
            "defaultCompleted, status, sortOrder) VALUES (:t, '_test_fl', 'onboarding', '_test_task', "
            "'manual', 'manual', :d, :s, 9999)"
        ),
        {"t": task_id, "d": default_completed, "s": status},
    )
    session.commit()
    _TASK_IDS.append(task_id)
    return task_id


def _cleanup(session) -> None:
    for task_id in _TASK_IDS:
        session.execute(text("DELETE FROM merchant_task_progress WHERE taskId = :t"), {"t": task_id})
        session.execute(text("DELETE FROM second_level_task WHERE taskId = :t"), {"t": task_id})
    session.commit()
    _TASK_IDS.clear()


def test_disabled_task_submission_rejected(client, session):
    """停用任务(status=0)提交 completed -> 400,且不写进度。"""
    merchant_id = make_temp_merchant(session)
    try:
        task_id = _make_task(session, status=0, default_completed=0)
        resp = client.post("/api/task/progress", headers=_headers(merchant_id),
                           json={"taskId": task_id, "status": "completed"})
        assert resp.status_code == 400, resp.text
        assert resp.json()["code"] == 400
        written = session.execute(
            text("SELECT COUNT(*) FROM merchant_task_progress WHERE merchantId = :m AND taskId = :t"),
            {"m": merchant_id, "t": task_id},
        ).scalar()
        assert written == 0
    finally:
        _cleanup(session)
        cleanup_temp_merchant(session, merchant_id)


def test_default_completed_task_cannot_be_set_pending(client, session):
    """default_completed=1 的任务不可置为未完成(400)。"""
    merchant_id = make_temp_merchant(session)
    try:
        task_id = _make_task(session, status=1, default_completed=1)
        resp = client.post("/api/task/progress", headers=_headers(merchant_id),
                           json={"taskId": task_id, "status": "pending"})
        assert resp.status_code == 400, resp.text
        assert resp.json()["code"] == 400
    finally:
        _cleanup(session)
        cleanup_temp_merchant(session, merchant_id)


def test_default_completed_task_completed_is_idempotent(client, session):
    """default_completed=1 的任务可幂等提交 completed(前端"完成整个阶段"会包含它们,不得破坏该路径)。"""
    merchant_id = make_temp_merchant(session)
    try:
        task_id = _make_task(session, status=1, default_completed=1)
        resp = client.post("/api/task/progress", headers=_headers(merchant_id),
                           json={"taskId": task_id, "status": "completed"})
        assert resp.status_code == 201, resp.text
        assert resp.json()["code"] == 0
    finally:
        _cleanup(session)
        cleanup_temp_merchant(session, merchant_id)


def test_enabled_task_submission_still_works(client, session):
    """正常启用任务可提交 completed / 回退 pending(回归)。"""
    merchant_id = make_temp_merchant(session)
    try:
        task_id = _make_task(session, status=1, default_completed=0)
        first = client.post("/api/task/progress", headers=_headers(merchant_id),
                            json={"taskId": task_id, "status": "completed"})
        assert first.status_code == 201, first.text
        back = client.post("/api/task/progress", headers=_headers(merchant_id),
                           json={"taskId": task_id, "status": "pending"})
        assert back.status_code == 201, back.text
    finally:
        _cleanup(session)
        cleanup_temp_merchant(session, merchant_id)
