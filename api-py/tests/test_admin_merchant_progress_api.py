"""管理端商家任务进度列表回归(#PB-22)。

缺陷:GET /api/admin/merchant/progress 曾把 merchantId 写成必填,管理后台「商家管理」页
(admin/src/pages/merchant-progress/index.vue:108 无参调用;admin/src/api/task-progress.ts:19-22)
因此收到 400(当时文案「请求参数不合法：字段 merchantId」;该文案已于 #PB-24-1-R1 口语化),异常被页面 catch 吞成 console.error -> 商家列表恒空。

本单口径:merchantId 可选(不传 / 空值 = 全部商家);「全部」取数落服务层 task_progress.list_all,
排序 merchantId, taskId 固定(前端按 merchantId 聚合);显式上界 MAX_PROGRESS_ROWS,超限抛结构化 400
「结果过多，请按商家查询」——**不静默截断**。
读权限按真源「需登录」(`任务管理后台开发标准` §6 该行 + §7.2「平台数据登录管理员均可读」),
故 viewer 亦可读;写权限仍限 admin/super_admin(403 文案不变)。

隔离:临时管理员按 username 清理;临时商家按 merchant_id 清理(连带其进度行);只读用例零写入。
"""

import uuid

import pytest
from sqlalchemy import text

from app.core.security import hash_password
from app.db.models.admin_account import AdminAccount
from app.services import task_progress
from tests.conftest import cleanup_temp_admin, cleanup_temp_merchant, make_temp_merchant

LIST_PATH = "/api/admin/merchant/progress"
DETAIL_PATH = "/api/admin/merchant/progress/"
UNLOCK_PATH = "/api/admin/merchant/{mid}/unlock-phase1"
ROW_KEYS = {"id", "merchantId", "taskId", "status", "completedAt", "createdAt", "updatedAt"}
CAP_MESSAGE = "结果过多，请按商家查询"


@pytest.fixture()
def admins(client, session):
    """创建临时管理员并返回取 token 的函数(结束按 username 清理)。"""
    created = []

    def _token(role: str = "super_admin") -> str:
        username = f"_test_mprog_{uuid.uuid4().hex[:8]}"
        password = "Test@12345"
        enc, salt = hash_password(password)
        session.add(AdminAccount(username=username, passwordHash=enc, salt=salt,
                                 realName="商家进度测试", role=role, status=1))
        session.commit()
        created.append(username)
        resp = client.post("/api/admin/auth/login", json={"username": username, "password": password})
        assert resp.status_code == 200, resp.text
        return resp.json()["data"]["token"]

    yield _token
    for name in created:
        cleanup_temp_admin(session, name)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _row_count(session) -> int:
    """开发库进度行数(先结束本会话事务:REPEATABLE READ 下否则读到旧快照)。"""
    session.commit()
    return int(session.execute(text("SELECT COUNT(*) FROM merchant_task_progress")).scalar())


def _any_merchant_id(session) -> str:
    session.commit()
    return str(session.execute(
        text("SELECT merchantId FROM merchant_task_progress ORDER BY id LIMIT 1")
    ).scalar())


def _insert_progress(session, merchant_id: str, task_id: str) -> int:
    session.execute(
        text("INSERT INTO merchant_task_progress (merchantId, taskId, status) VALUES (:m, :t, 'pending')"),
        {"m": merchant_id, "t": task_id},
    )
    session.commit()
    return int(session.execute(
        text("SELECT id FROM merchant_task_progress WHERE merchantId = :m AND taskId = :t"),
        {"m": merchant_id, "t": task_id},
    ).scalar())


def test_no_param_returns_all_merchant_rows(client, session, admins):
    """复现点:不带 merchantId 必须 200 且返回全部行(修复前为 400 字段校验错误)。"""
    token = admins()
    resp = client.get(LIST_PATH, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    rows = body["data"]
    assert len(rows) == _row_count(session)
    assert len(rows) > 0
    assert set(rows[0]) == ROW_KEYS
    assert all(r["merchantId"] and r["taskId"] for r in rows)
    # 排序确定性:两次请求的 payload(含顺序)完全一致
    again = client.get(LIST_PATH, headers=_auth(token))
    assert again.json()["data"] == rows


def test_query_param_matches_detail_path(client, session, admins):
    """带 merchantId 的查询结果与 /progress/{merchantId} 完全一致(同一服务层口径)。"""
    token = admins()
    mid = _any_merchant_id(session)
    by_query = client.get(LIST_PATH, params={"merchantId": mid}, headers=_auth(token))
    by_path = client.get(DETAIL_PATH + mid, headers=_auth(token))
    assert by_query.status_code == 200, by_query.text
    assert by_path.status_code == 200, by_path.text
    assert by_query.json()["data"] == by_path.json()["data"]
    assert len(by_query.json()["data"]) > 0


def test_blank_query_param_behaves_like_absent(client, session, admins):
    """显式空值不得再触发 400(前端 `merchantId ? {merchantId} : {}` 的兜底语义)。"""
    token = admins()
    resp = client.get(LIST_PATH, params={"merchantId": ""}, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["data"]) == _row_count(session)


def test_read_is_login_only_and_write_is_admin_role(client, session, admins):
    """读 = 需登录(真源 §6 该行 + §7.2);写 = admin/super_admin;403 文案不变。"""
    for role in ("super_admin", "admin", "viewer"):
        resp = client.get(LIST_PATH, headers=_auth(admins(role)))
        assert resp.status_code == 200, (role, resp.text)
    assert client.get(LIST_PATH).status_code == 401

    denied = client.post(UNLOCK_PATH.format(mid="_test_missing_merchant"), headers=_auth(admins("viewer")))
    assert denied.status_code == 403, denied.text
    assert denied.json()["message"] == "无权限执行该操作"

    merchant_id = make_temp_merchant(session)
    try:
        allowed = client.post(UNLOCK_PATH.format(mid=merchant_id), headers=_auth(admins("admin")))
        assert allowed.status_code == 201, allowed.text
        assert allowed.json()["data"] == {"success": True, "stage2_unlocked": True}
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_row_cap_returns_structured_error_without_truncation(monkeypatch, client, session, admins):
    """上界行为:未超限全量返回;超限结构化 400 且 data 为 null(绝不截断);单商家查询不受上界影响。"""
    token = admins()
    total = _row_count(session)
    assert total > 1

    monkeypatch.setattr(task_progress, "MAX_PROGRESS_ROWS", total)
    at_cap = client.get(LIST_PATH, headers=_auth(token))
    assert at_cap.status_code == 200, at_cap.text
    assert len(at_cap.json()["data"]) == total      # 边界:恰好等于上界 -> 全量

    monkeypatch.setattr(task_progress, "MAX_PROGRESS_ROWS", total - 1)
    over = client.get(LIST_PATH, headers=_auth(token))
    assert over.status_code == 400, over.text
    assert over.json() == {"code": 400, "message": CAP_MESSAGE, "data": None}

    mid = _any_merchant_id(session)
    escape = client.get(LIST_PATH, params={"merchantId": mid}, headers=_auth(token))
    assert escape.status_code == 200, escape.text
    assert len(escape.json()["data"]) > 0


def test_list_all_orders_by_merchant_then_task(session):
    """list_all 排序 = merchantId, taskId(前端按 merchantId 聚合,顺序须可复现)。"""
    merchant_id = make_temp_merchant(session)
    row_ids = []
    try:
        row_ids.append(_insert_progress(session, merchant_id, "b_task"))
        row_ids.append(_insert_progress(session, merchant_id, "a_task"))

        rows = task_progress.list_all(session)
        mine = [r.taskId for r in rows if r.merchantId == merchant_id]
        assert mine == ["a_task", "b_task"], mine
        assert len(rows) == _row_count(session)
    finally:
        for row_id in row_ids:
            session.execute(text("DELETE FROM merchant_task_progress WHERE id = :i"), {"i": row_id})
        session.commit()
        cleanup_temp_merchant(session, merchant_id)
