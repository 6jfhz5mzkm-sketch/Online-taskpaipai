
"""任务行为语义字段 actionType / actionParam 接入回归(#PB-39;schema v1.11 / #DB-23)。

真源:project/docs/后端技术方案.md §1.3 / §5.2;设计单 dev-docs/任务单/action-type-design.md §2.1。
口径:
- 投影 = services/task.py::second_level_dict(**单一处**)⇒ 商家端 GET /api/task/stages 与管理端任务配置同时生效;
- actionType 10 值枚举(非法 → 400 且复用统一校验出口文案);
- actionParam 仅 data_form/data_upload 允许且**必须非空**,其余行为**必须为空**(违反 → 400 同文案);
- **纯增量**:既有字段集合与取值一个不改。

隔离:临时管理员(conftest make_temp_admin)+ 临时二级任务(_test_ 前缀 taskId,finally 按 taskId 删除)。
"""
import typing
import uuid

from sqlalchemy import text

from app.core.error_handlers import VALIDATION_MESSAGE
from app.core.security import create_merchant_token
from tests.conftest import cleanup_temp_admin, make_temp_admin

STAGES_PATH = "/api/task/stages"
TASK_CREATE = "/api/admin/task/create"
TASK_LIST = "/api/admin/task/list"

# 管理端/商家端共用的二级任务投影键集(既有 17 键 + #PB-39 新增 2 键 = 19 键;顺序即投影顺序)
BASE_PROJECTION_KEYS = [
    "id", "taskId", "firstLevelTaskId", "stageId", "title", "description", "detail", "type",
    "completionType", "actionText", "actionUrl", "tag", "defaultCompleted", "status", "sortOrder",
    "createdAt", "updatedAt",
]
NEW_PROJECTION_KEYS = ["actionType", "actionParam"]

_CREATED_TASK_IDS: list = []


def _merchant_headers() -> dict:
    return {"Authorization": "Bearer " + create_merchant_token("mock_merchant_001")}


def _admin_headers(token: str) -> dict:
    return {"Authorization": "Bearer " + token}


def _login(client, username: str, password: str) -> str:
    resp = client.post("/api/admin/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["token"]


def _task_payload(**overrides) -> dict:
    payload = {
        "taskId": "_test_action_" + uuid.uuid4().hex[:8],
        "firstLevelTaskId": "_test_fl",
        "stageId": "onboarding",
        "title": "_test 行为字段任务",
        "type": "guide",
        "completionType": "click_read",
    }
    payload.update(overrides)
    return payload


def _create(client, token, **overrides):
    payload = _task_payload(**overrides)
    resp = client.post(TASK_CREATE, headers=_admin_headers(token), json=payload)
    if resp.status_code == 201:
        _CREATED_TASK_IDS.append(payload["taskId"])
    return resp


def _cleanup_tasks(session) -> None:
    for task_id in _CREATED_TASK_IDS:
        session.execute(text("DELETE FROM merchant_task_progress WHERE taskId = :t"), {"t": task_id})
        session.execute(text("DELETE FROM second_level_task WHERE taskId = :t"), {"t": task_id})
    session.commit()
    _CREATED_TASK_IDS.clear()


def _db_action_map(session) -> dict:
    rows = session.execute(
        text("SELECT taskId, actionType, actionParam FROM second_level_task")
    ).mappings().all()
    return {r["taskId"]: (r["actionType"], r["actionParam"]) for r in rows}


def _stages_tasks(client) -> dict:
    """商家端 /api/task/stages 拍平成 {taskId: task 投影}。"""
    resp = client.get(STAGES_PATH, headers=_merchant_headers())
    assert resp.status_code == 200, resp.text
    found = {}
    for stage in resp.json()["data"]:
        for group in stage.get("firstLevelTasks", []):
            for task in group.get("secondLevelTasks", []):
                found[task["taskId"]] = task
    return found


# ---------- ① 商家端投影 ----------


def test_stages_projection_carries_action_fields_matching_db(client, session):
    """① 商家端 /api/task/stages 的每条任务都带 actionType/actionParam,且值与库内逐条一致。"""
    db_map = _db_action_map(session)
    tasks = _stages_tasks(client)
    assert tasks, "前置:商家端 stages 应返回任务"
    for task_id, task in tasks.items():
        assert "actionType" in task and "actionParam" in task, task_id
        assert (task["actionType"], task["actionParam"]) == db_map[task_id], task_id
    # 关键取值真实可见(阶段一 category_picker 必在;专区 data_* 带参数)
    assert tasks["T1.1.2"]["actionType"] == "category_picker"
    assert tasks["T1.1.2"]["actionParam"] is None
    data_tasks = {k: v for k, v in tasks.items() if str(v["actionType"]).startswith("data_")}
    assert data_tasks, "前置:专区 data_* 任务应出现在 stages 响应中"
    for task_id, task in data_tasks.items():
        assert task["actionParam"], (task_id, task)


# ---------- ② 管理端投影 ----------


def test_admin_task_projection_carries_action_fields_matching_db(client, session):
    """② 管理端任务配置接口(GET /list)同样带两字段且与库内一致(共用同一投影)。"""
    username, password = make_temp_admin(session)
    try:
        token = _login(client, username, password)
        resp = client.get(TASK_LIST, params={"stageId": "shopdata"}, headers=_admin_headers(token))
        assert resp.status_code == 200, resp.text
        rows = resp.json()["data"]
        assert rows, "前置:shopdata 阶段应有任务"
        db_map = _db_action_map(session)
        for row in rows:
            assert set(NEW_PROJECTION_KEYS) <= set(row), row
            assert (row["actionType"], row["actionParam"]) == db_map[row["taskId"]], row["taskId"]
        params = {r["actionParam"] for r in rows if r["actionType"] in ("data_form", "data_upload")}
        assert params == {"star", "product-count", "health-score", "trade", "traffic", "product"}, params
    finally:
        cleanup_temp_admin(session, username)


# ---------- ③ 非法枚举 ----------


def test_invalid_action_type_rejected(client, session):
    """③ 非 10 值枚举 → 400 + 统一校验文案(创建与更新两条路径)。"""
    username, password = make_temp_admin(session)
    try:
        token = _login(client, username, password)
        created = client.post(TASK_CREATE, headers=_admin_headers(token),
                              json=_task_payload(actionType="bogus_action"))
        assert created.status_code == 400, created.text
        body = created.json()
        assert body["code"] == 400 and body["message"] == VALIDATION_MESSAGE and body["data"] is None

        ok = _create(client, token)
        assert ok.status_code == 201, ok.text
        task_pk = ok.json()["data"]["id"]
        updated = client.put("/api/admin/task/" + str(task_pk), headers=_admin_headers(token),
                             json={"actionType": "data_forms"})
        assert updated.status_code == 400, updated.text
        assert updated.json()["message"] == VALIDATION_MESSAGE
    finally:
        _cleanup_tasks(session)
        cleanup_temp_admin(session, username)


# ---------- ④ data_* 缺参数 ----------


def test_data_form_requires_action_param(client, session):
    """④ data_form/data_upload 缺参数(或空串)→ 400;补上参数 → 201 且落库一致。"""
    username, password = make_temp_admin(session)
    try:
        token = _login(client, username, password)
        missing = _create(client, token, actionType="data_form")
        assert missing.status_code == 400, missing.text
        assert missing.json()["message"] == VALIDATION_MESSAGE
        blank = _create(client, token, actionType="data_upload", actionParam="   ")
        assert blank.status_code == 400, blank.text
        assert blank.json()["message"] == VALIDATION_MESSAGE

        ok = _create(client, token, actionType="data_form", actionParam="star")
        assert ok.status_code == 201, ok.text
        data = ok.json()["data"]
        assert (data["actionType"], data["actionParam"]) == ("data_form", "star")
        stored = session.execute(
            text("SELECT actionType, actionParam FROM second_level_task WHERE taskId = :t"),
            {"t": data["taskId"]},
        ).mappings().first()
        assert (stored["actionType"], stored["actionParam"]) == ("data_form", "star")

        # 部分更新:只把 data_form 任务的 actionParam 清空 → 400
        cleared = client.put("/api/admin/task/" + str(data["id"]), headers=_admin_headers(token),
                             json={"actionParam": None})
        assert cleared.status_code == 400, cleared.text
        assert cleared.json()["message"] == VALIDATION_MESSAGE
    finally:
        _cleanup_tasks(session)
        cleanup_temp_admin(session, username)


# ---------- ⑤ 非 data_* 带参数 ----------


def test_non_data_action_type_rejects_action_param(client, session):
    """⑤ 非 data_* 行为带参数 → 400;把 data_* 任务切成 none 时必须显式清空参数。"""
    username, password = make_temp_admin(session)
    try:
        token = _login(client, username, password)
        for action_type in ("none", "advisor_qr"):
            bad = _create(client, token, actionType=action_type, actionParam="star")
            assert bad.status_code == 400, (action_type, bad.text)
            assert bad.json()["message"] == VALIDATION_MESSAGE

        created = _create(client, token, actionType="data_form", actionParam="health-score")
        assert created.status_code == 201, created.text
        task = created.json()["data"]
        # 只改 actionType 而不清参数 → 与库内 actionParam 组合非法 → 400
        switch = client.put("/api/admin/task/" + str(task["id"]), headers=_admin_headers(token),
                            json={"actionType": "none"})
        assert switch.status_code == 400, switch.text
        assert switch.json()["message"] == VALIDATION_MESSAGE
        # 显式清空参数 → 200,库内 actionParam 落 NULL
        cleared = client.put("/api/admin/task/" + str(task["id"]), headers=_admin_headers(token),
                             json={"actionType": "none", "actionParam": None})
        assert cleared.status_code == 200, cleared.text
        assert (cleared.json()["data"]["actionType"], cleared.json()["data"]["actionParam"]) == ("none", None)
        stored = session.execute(
            text("SELECT actionType, actionParam FROM second_level_task WHERE taskId = :t"),
            {"t": task["taskId"]},
        ).mappings().first()
        assert (stored["actionType"], stored["actionParam"]) == ("none", None)
    finally:
        _cleanup_tasks(session)
        cleanup_temp_admin(session, username)


# ---------- ⑥ 纯增量回归 ----------


def test_projection_is_pure_increment(client, session):
    """⑥ 纯增量:省略两字段 → 默认 none/NULL;既有字段集合与取值不变(键集恰好 = 既有 + 2 新键)。"""
    username, password = make_temp_admin(session)
    try:
        token = _login(client, username, password)
        created = _create(client, token, title="_test 增量回归", actionText="去登记", actionUrl="https://example.com/x")
        assert created.status_code == 201, created.text
        data = created.json()["data"]
        assert (data["actionType"], data["actionParam"]) == ("none", None)
        # 既有字段取值逐一不变
        assert data["title"] == "_test 增量回归"
        assert data["actionText"] == "去登记"
        assert data["actionUrl"] == "https://example.com/x"
        assert data["type"] == "guide" and data["completionType"] == "click_read"
        assert data["status"] == 1 and data["defaultCompleted"] == 0

        # 键集恰好 = 既有 17 键 + 新 2 键(不增不减)
        expected_keys = set(BASE_PROJECTION_KEYS) | set(NEW_PROJECTION_KEYS)
        assert set(data) == expected_keys, set(data) ^ expected_keys
        # 新字段落在 actionUrl 之后(与 DB 列序一致)
        order = list(data)
        assert order.index("actionType") == order.index("actionUrl") + 1
        assert order.index("actionParam") == order.index("actionType") + 1

        # 单一投影:商家端对**同一真实任务**的键集与两字段取值,与库内/admin 侧一致
        #   (临时任务挂在 _test_fl 一级任务下,不会出现在 stages 的渲染树里,故用真实任务核对)
        stages_task = _stages_tasks(client)["T1.1.2"]
        assert set(stages_task) == expected_keys
        assert (stages_task["actionType"], stages_task["actionParam"]) == ("category_picker", None)
        db_row = session.execute(
            text("SELECT actionType, actionParam FROM second_level_task WHERE taskId = :t"),
            {"t": "T1.1.2"},
        ).mappings().first()
        assert (stages_task["actionType"], stages_task["actionParam"]) == (db_row["actionType"], db_row["actionParam"])
    finally:
        _cleanup_tasks(session)
        cleanup_temp_admin(session, username)


def test_action_type_literal_matches_service_enum():
    """防漂移:路由 Literal 与服务层枚举真源必须完全一致(10 值)。"""
    from app.api.v1.admin_task import ActionType
    from app.services.admin_task_config import ACTION_TYPES, DATA_ACTION_TYPES

    assert set(typing.get_args(ActionType)) == set(ACTION_TYPES)
    assert len(ACTION_TYPES) == 10
    assert DATA_ACTION_TYPES <= set(ACTION_TYPES)
