"""管理端任务配置(阶段 / 一级任务 / 二级任务)CRUD 回归(#PB-7)。

契约基准(总控裁决:前端真实调用 + NestJS 既有实现优先于文档 §6.3):
- GET /api/admin/{stage|group|task}/list
- GET /api/admin/{stage|group|task}/{id}
- POST /api/admin/{stage|group|task}/create
- PUT /api/admin/{stage|group|task}/{id}
- DELETE /api/admin/{stage|group|task}/{id}
鉴权:list/detail 需管理员登录;create/update/delete 需 super_admin/admin。

隔离:临时管理员(make_temp_admin)+ 临时配置实体(_test_ 前缀),finally 按标识直接删除,
不触碰真实阶段/任务配置;需要「有进度记录」时插入临时 taskId 的临时行,finally 一并清除。
"""
import uuid

from sqlalchemy import text

from app.core.security import create_merchant_token
from tests.conftest import cleanup_temp_admin, make_temp_admin

STAGE_CREATE = "/api/admin/stage/create"
GROUP_CREATE = "/api/admin/group/create"
TASK_CREATE = "/api/admin/task/create"
MISSING_ID = 999999999


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


def _admin_token(client, username: str, password: str) -> str:
    resp = client.post("/api/admin/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _cleanup(session, stage_ids=(), group_ids=(), task_ids=()) -> None:
    """按标识清理临时配置(顺序:二级 -> 一级 -> 阶段;进度行一并清)。"""
    for task_id in task_ids:
        session.execute(text("DELETE FROM merchant_task_progress WHERE taskId = :t"), {"t": task_id})
        session.execute(text("DELETE FROM second_level_task WHERE taskId = :t"), {"t": task_id})
    for group_id in group_ids:
        session.execute(text("DELETE FROM first_level_task WHERE taskId = :t"), {"t": group_id})
    for stage_id in stage_ids:
        session.execute(text("DELETE FROM stage_config WHERE stage_id = :s"), {"s": stage_id})
    session.commit()


def _create(client, token, path, payload) -> dict:
    resp = client.post(path, headers=_headers(token), json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["code"] == 0, body
    return body["data"]


def test_task_config_endpoints_require_admin_token(client):
    """15 个接口在无 token 时一律 401(管理员 JWT 守卫在业务逻辑之前生效)。"""
    cases = [
        ("GET", "/api/admin/stage/list", None),
        ("GET", f"/api/admin/stage/{MISSING_ID}", None),
        ("POST", STAGE_CREATE, {"stageId": "_test_x", "stageNum": 1, "title": "_test"}),
        ("PUT", f"/api/admin/stage/{MISSING_ID}", {"title": "_test"}),
        ("DELETE", f"/api/admin/stage/{MISSING_ID}", None),
        ("GET", "/api/admin/group/list", None),
        ("GET", f"/api/admin/group/{MISSING_ID}", None),
        ("POST", GROUP_CREATE, {"taskId": "_test_x", "stageId": "_test_s", "title": "_test"}),
        ("PUT", f"/api/admin/group/{MISSING_ID}", {"title": "_test"}),
        ("DELETE", f"/api/admin/group/{MISSING_ID}", None),
        ("GET", "/api/admin/task/list", None),
        ("GET", f"/api/admin/task/{MISSING_ID}", None),
        ("POST", TASK_CREATE, {"taskId": "_test_x", "firstLevelTaskId": "_test_g", "stageId": "_test_s",
                               "title": "_test", "type": "guide", "completionType": "click_read"}),
        ("PUT", f"/api/admin/task/{MISSING_ID}", {"title": "_test"}),
        ("DELETE", f"/api/admin/task/{MISSING_ID}", None),
    ]
    for method, path, payload in cases:
        resp = client.request(method, path, json=payload)
        assert resp.status_code == 401, (method, path, resp.status_code, resp.text)
        assert resp.json()["code"] == 401


def test_merchant_token_rejected_on_task_config(client):
    """商家 token 用的是另一个 secret,不能访问管理端任务配置接口。"""
    token = create_merchant_token("mock_merchant_001")
    resp = client.get("/api/admin/stage/list", headers=_headers(token))
    assert resp.status_code == 401, resp.text
    assert resp.json()["code"] == 401


def test_stage_crud_and_guards(client, session):
    """阶段 CRUD 主路径 + 唯一标识冲突 / 关联任务拒绝删除 / 404。"""
    suffix = _suffix()
    stage_id = f"_test_stage_{suffix}"
    group_id = f"_test_group_{suffix}"
    username, password = make_temp_admin(session)
    try:
        token = _admin_token(client, username, password)

        created = _create(client, token, STAGE_CREATE, {
            "stageId": stage_id, "stageNum": 91, "title": "_test 阶段",
            "description": "临时", "buttonText": "开始", "sortOrder": 91, "phaseNum": 2,
        })
        assert created["stageId"] == stage_id
        assert created["stageNum"] == 91 and created["phaseNum"] == 2 and created["sortOrder"] == 91
        assert created["status"] == 1
        assert isinstance(created["id"], str) and created["createdAt"].endswith("Z")
        stage_pk = created["id"]

        listed = client.get("/api/admin/stage/list", headers=_headers(token)).json()["data"]
        assert any(s["stageId"] == stage_id for s in listed)
        # 列表排序口径:sort_order ASC, stage_num ASC
        keys = [(s["sortOrder"], s["stageNum"]) for s in listed]
        assert keys == sorted(keys)

        detail = client.get(f"/api/admin/stage/{stage_pk}", headers=_headers(token))
        assert detail.status_code == 200 and detail.json()["data"]["stageId"] == stage_id

        missing = client.get(f"/api/admin/stage/{MISSING_ID}", headers=_headers(token))
        assert missing.status_code == 404 and missing.json()["code"] == 404

        dup = client.post(STAGE_CREATE, headers=_headers(token), json={
            "stageId": stage_id, "stageNum": 92, "title": "_test 重复",
        })
        assert dup.status_code == 400 and dup.json()["code"] == 400

        bad = client.post(STAGE_CREATE, headers=_headers(token), json={
            "stageId": f"_test_bad_{suffix}", "stageNum": 0, "title": "_test 非法",
        })
        assert bad.status_code == 400

        updated = client.put(f"/api/admin/stage/{stage_pk}", headers=_headers(token), json={
            "title": "_test 阶段(改)", "phaseNum": 1,
        })
        assert updated.status_code == 200, updated.text
        assert updated.json()["data"]["title"] == "_test 阶段(改)"
        assert updated.json()["data"]["phaseNum"] == 1
        assert updated.json()["data"]["stageId"] == stage_id  # 未提供的键不被清空

        # 关联一级任务存在时禁止删除阶段
        _create(client, token, GROUP_CREATE, {
            "taskId": group_id, "stageId": stage_id, "title": "_test 一级任务", "sortOrder": 1,
        })
        blocked = client.delete(f"/api/admin/stage/{stage_pk}", headers=_headers(token))
        assert blocked.status_code == 400, blocked.text
        assert "无法删除" in blocked.json()["message"]

        group_pk = client.get("/api/admin/group/list", headers=_headers(token),
                              params={"stageId": stage_id}).json()["data"][0]["id"]
        assert client.delete(f"/api/admin/group/{group_pk}", headers=_headers(token)).status_code == 200

        removed = client.delete(f"/api/admin/stage/{stage_pk}", headers=_headers(token))
        assert removed.status_code == 200 and removed.json()["data"] == {"success": True}
        assert client.get(f"/api/admin/stage/{stage_pk}", headers=_headers(token)).status_code == 404
    finally:
        _cleanup(session, stage_ids=(stage_id,), group_ids=(group_id,))
        cleanup_temp_admin(session, username)


def test_group_crud_and_guards(client, session):
    """一级任务 CRUD 主路径 + stageId 过滤 / 唯一标识冲突 / 关联二级任务拒绝删除 / 404。"""
    suffix = _suffix()
    stage_id = f"_test_stage_{suffix}"
    group_id = f"_test_group_{suffix}"
    other_group_id = f"_test_group_other_{suffix}"
    task_id = f"_test_task_{suffix}"
    username, password = make_temp_admin(session)
    try:
        token = _admin_token(client, username, password)
        _create(client, token, STAGE_CREATE, {"stageId": stage_id, "stageNum": 93, "title": "_test 阶段(过滤)"})

        created = _create(client, token, GROUP_CREATE, {
            "taskId": group_id, "stageId": stage_id, "title": "_test 一级任务",
            "description": "临时", "buttonText": "去完成", "sortOrder": 3,
        })
        assert created["taskId"] == group_id and created["stageId"] == stage_id
        assert created["buttonText"] == "去完成" and created["status"] == 1
        group_pk = created["id"]

        filtered = client.get("/api/admin/group/list", headers=_headers(token),
                              params={"stageId": stage_id}).json()["data"]
        assert [g["taskId"] for g in filtered] == [group_id]

        _create(client, token, GROUP_CREATE, {
            "taskId": other_group_id, "stageId": stage_id, "title": "_test 一级任务(不过滤)", "sortOrder": 1,
        })
        ordered = client.get("/api/admin/group/list", headers=_headers(token),
                             params={"stageId": stage_id}).json()["data"]
        assert [g["taskId"] for g in ordered] == [other_group_id, group_id]  # sortOrder ASC

        detail = client.get(f"/api/admin/group/{group_pk}", headers=_headers(token))
        assert detail.status_code == 200 and detail.json()["data"]["taskId"] == group_id
        assert client.get(f"/api/admin/group/{MISSING_ID}", headers=_headers(token)).status_code == 404

        dup = client.post(GROUP_CREATE, headers=_headers(token),
                          json={"taskId": group_id, "stageId": stage_id, "title": "_test 重复"})
        assert dup.status_code == 400

        updated = client.put(f"/api/admin/group/{group_pk}", headers=_headers(token),
                             json={"title": "_test 一级任务(改)", "sortOrder": 0})
        assert updated.status_code == 200
        assert updated.json()["data"]["title"] == "_test 一级任务(改)"
        assert updated.json()["data"]["taskId"] == group_id

        task = _create(client, token, TASK_CREATE, {
            "taskId": task_id, "firstLevelTaskId": group_id, "stageId": stage_id,
            "title": "_test 二级任务", "type": "guide", "completionType": "click_read",
        })
        task_pk = task["id"]
        blocked = client.delete(f"/api/admin/group/{group_pk}", headers=_headers(token))
        assert blocked.status_code == 400 and "无法删除" in blocked.json()["message"]

        assert client.delete(f"/api/admin/task/{task_pk}", headers=_headers(token)).status_code == 200
        assert client.delete(f"/api/admin/group/{group_pk}", headers=_headers(token)).json()["data"] == {"success": True}
    finally:
        _cleanup(session, stage_ids=(stage_id,), group_ids=(group_id, other_group_id), task_ids=(task_id,))
        cleanup_temp_admin(session, username)


def test_task_crud_and_guards(client, session):
    """二级任务 CRUD 主路径 + 过滤 / 枚举与必填校验 / 唯一标识冲突 / 进度记录拒绝删除。"""
    suffix = _suffix()
    stage_id = f"_test_stage_{suffix}"
    group_id = f"_test_group_{suffix}"
    task_id = f"_test_task_{suffix}"
    username, password = make_temp_admin(session)
    try:
        token = _admin_token(client, username, password)
        _create(client, token, STAGE_CREATE, {"stageId": stage_id, "stageNum": 94, "title": "_test 阶段(task)"})
        _create(client, token, GROUP_CREATE, {"taskId": group_id, "stageId": stage_id, "title": "_test 一级(task)"})

        created = _create(client, token, TASK_CREATE, {
            "taskId": task_id, "firstLevelTaskId": group_id, "stageId": stage_id,
            "title": "_test 二级任务", "description": "描述", "detail": "# 详情",
            "type": "mandatory", "completionType": "manual_submit",
            "actionText": "去完成", "actionUrl": "https://example.com", "tag": "必做",
            "defaultCompleted": 0, "sortOrder": 5,
        })
        assert created["taskId"] == task_id and created["firstLevelTaskId"] == group_id
        assert created["type"] == "mandatory" and created["completionType"] == "manual_submit"
        assert created["tag"] == "必做" and created["status"] == 1
        task_pk = created["id"]

        fetched = client.get("/api/admin/task/list", headers=_headers(token),
                             params={"firstLevelTaskId": group_id}).json()["data"]
        assert [t["taskId"] for t in fetched] == [task_id]
        by_stage = client.get("/api/admin/task/list", headers=_headers(token),
                              params={"stageId": stage_id}).json()["data"]
        assert any(t["taskId"] == task_id for t in by_stage)

        detail = client.get(f"/api/admin/task/{task_pk}", headers=_headers(token))
        assert detail.status_code == 200 and detail.json()["data"]["detail"] == "# 详情"
        assert client.get(f"/api/admin/task/{MISSING_ID}", headers=_headers(token)).status_code == 404

        dup = client.post(TASK_CREATE, headers=_headers(token), json={
            "taskId": task_id, "firstLevelTaskId": group_id, "stageId": stage_id,
            "title": "_test 重复", "type": "guide", "completionType": "click_read",
        })
        assert dup.status_code == 400

        illegal = client.post(TASK_CREATE, headers=_headers(token), json={
            "taskId": f"_test_bad_{suffix}", "firstLevelTaskId": group_id, "stageId": stage_id,
            "title": "_test 非法枚举", "type": "unknown", "completionType": "click_read",
        })
        assert illegal.status_code == 400

        missing_field = client.post(TASK_CREATE, headers=_headers(token), json={
            "taskId": f"_test_bad2_{suffix}", "stageId": stage_id,
            "title": "_test 缺字段", "type": "guide", "completionType": "click_read",
        })
        assert missing_field.status_code == 400

        updated = client.put(f"/api/admin/task/{task_pk}", headers=_headers(token),
                             json={"title": "_test 二级任务(改)", "type": "suggested"})
        assert updated.status_code == 200
        assert updated.json()["data"]["title"] == "_test 二级任务(改)"
        assert updated.json()["data"]["type"] == "suggested"
        assert updated.json()["data"]["taskId"] == task_id

        # 已有商家进度记录时禁止删除
        session.execute(
            text("INSERT INTO merchant_task_progress (merchantId, taskId, status) VALUES ('_test_merchant', :t, 'completed')"),
            {"t": task_id},
        )
        session.commit()
        blocked = client.delete(f"/api/admin/task/{task_pk}", headers=_headers(token))
        assert blocked.status_code == 400, blocked.text
        assert "已有 1 条商家进度记录" in blocked.json()["message"]

        session.execute(text("DELETE FROM merchant_task_progress WHERE taskId = :t"), {"t": task_id})
        session.commit()
        removed = client.delete(f"/api/admin/task/{task_pk}", headers=_headers(token))
        assert removed.status_code == 200 and removed.json()["data"] == {"success": True}
    finally:
        _cleanup(session, stage_ids=(stage_id,), group_ids=(group_id,), task_ids=(task_id,))
        cleanup_temp_admin(session, username)


def test_stage_update_rejects_null_on_not_null_column(client, session):
    """显式把 NOT NULL 列置 null 返回 400,而不是落库抛 IntegrityError(500)。"""
    suffix = _suffix()
    stage_id = f"_test_stage_{suffix}"
    username, password = make_temp_admin(session)
    try:
        token = _admin_token(client, username, password)
        created = _create(client, token, STAGE_CREATE, {"stageId": stage_id, "stageNum": 95, "title": "_test 阶段(null)"})
        resp = client.put(f"/api/admin/stage/{created['id']}", headers=_headers(token), json={"title": None})
        assert resp.status_code == 400, resp.text
        assert "不能为 null" in resp.json()["message"]
        still = client.get(f"/api/admin/stage/{created['id']}", headers=_headers(token)).json()["data"]
        assert still["title"] == "_test 阶段(null)"
    finally:
        _cleanup(session, stage_ids=(stage_id,))
        cleanup_temp_admin(session, username)
