
"""`type` / `completionType` 枚举对齐开发库现实取值(#PB-40,阻塞级修复)。

背景(#AF-20 已用真实 UI + API 证实):开发库存在越界取值(type 的 form/jump/upload、completionType 的
form_submit/file_upload),而后端 Literal 只有 3 值 ⇒ 这 8 条任务从管理后台保存必 400(编辑表单把库里旧值原样回传)。
总控裁决:**扩展枚举到现实值,不动数据**;行为语义以 actionType(#PB-39 / 真源 §8.3.9)为准。

本文件四条用例:
1. 防漂移(#PB-40-R1 口径):**库内取值必须 ⊆ 枚举** —— 这才是「会导致保存 400」的方向,硬断言;
   反向(枚举值暂时没有行使用)**无害**,只记一行「未被使用的取值」,**不失败**(避免某唯一行被删就假红);
2. 同源:Literal == 服务层 TASK_TYPES / COMPLETION_TYPES(#PB-39 先例的同一手法);
3. 往返:8 条越界行各自的现值组合原样回传 → 200;且**真实 8 行分毫未动**(前后快照逐字段一致);
4. 负向:未知值 → 400 + 统一校验文案(HTTP),服务层兜底守卫同样拒绝。

隔离:临时管理员(make_temp_admin)+ 临时二级任务(`_test_` 前缀,finally 按 taskId 删除);真实配置行只读。
"""
import logging
import typing
import uuid

from sqlalchemy import text

from app.core.error_handlers import VALIDATION_MESSAGE
from app.core.exceptions import ApiException
from app.services.admin_task_config import COMPLETION_TYPES, TASK_TYPES
from tests.conftest import cleanup_temp_admin, make_temp_admin

logger = logging.getLogger("api")

TASK_CREATE = "/api/admin/task/create"
# 越界取值(type 的 3 个交互值 / completionType 的 2 个表单值)
OUT_OF_SCOPE_SQL = ("SELECT id, taskId, type, completionType, title, actionText, actionUrl "
                    "FROM second_level_task WHERE type IN ('form','jump','upload') "
                    "OR completionType IN ('form_submit','file_upload') ORDER BY taskId")
SNAPSHOT_SQL = ("SELECT id, taskId, type, completionType, title, actionText, actionUrl, updatedAt "
                "FROM second_level_task WHERE taskId NOT LIKE '_test_%' ORDER BY id")

_CREATED_TASK_IDS: list = []


def _headers(token: str) -> dict:
    return {"Authorization": "Bearer " + token}


def _login(client, username: str, password: str) -> str:
    resp = client.post("/api/admin/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["token"]


def _create(client, token, **overrides):
    payload = {
        "taskId": "_test_enum_" + uuid.uuid4().hex[:8],
        "firstLevelTaskId": "_test_fl",
        "stageId": "onboarding",
        "title": "_test 枚举对齐",
        "type": "guide",
        "completionType": "click_read",
    }
    payload.update(overrides)
    resp = client.post(TASK_CREATE, headers=_headers(token), json=payload)
    if resp.status_code == 201:
        _CREATED_TASK_IDS.append(payload["taskId"])
    return resp


def _cleanup_tasks(session) -> None:
    for task_id in _CREATED_TASK_IDS:
        session.execute(text("DELETE FROM merchant_task_progress WHERE taskId = :t"), {"t": task_id})
        session.execute(text("DELETE FROM second_level_task WHERE taskId = :t"), {"t": task_id})
    session.commit()
    _CREATED_TASK_IDS.clear()


def _db_distinct(session, column: str) -> set:
    return {r[0] for r in session.execute(text("SELECT DISTINCT " + column + " FROM second_level_task")).all()}


# ---------- ① 防漂移:库内取值 ⊆ 枚举(库里有、代码不认 ⇒ 保存 400) ----------


def assert_db_values_covered(column: str, db_values: set, allowed) -> set:
    """核心断言(**函数级可探针调用**):库内取值必须 ⊆ 允许值;返回未被任何行使用的允许值(仅报告)。

    方向(#PB-40-R1 总控裁定):
    - **硬断言**:`db_values - allowed` 非空 = 库里出现代码不认的取值 ⇒ 该任务保存必 400(本次 8 行越界的成因),
      必须失败并**指名**该取值;
    - **非失败报告**:`allowed - db_values`(枚举值暂时没有行使用)是**无害**的 —— 只记一行日志;
      否则「某唯一行被删/被改」就会假红,而本项目已吃过多次假红阻塞全链的亏。
    """
    allowed_set = set(allowed)
    missing = sorted(db_values - allowed_set)
    assert not missing, f"{column} 出现枚举未覆盖的取值(会导致该任务保存 400): {missing}"
    unused = sorted(allowed_set - db_values)
    if unused:
        logger.info(f"{column} 未被任何行使用的枚举取值(仅记录,不失败): {unused}")
        print(f"[enum-report] {column} 未被任何行使用的取值: {unused}")
    return set(unused)


def test_enums_cover_all_db_values(session):
    """① 防漂移:库内取值 ⊆ 两个 Literal(及服务层同源元组);未使用的枚举值只报告、不失败。"""
    from app.api.v1.admin_task import CompletionType, TaskType

    db_types = _db_distinct(session, "type")
    db_completions = _db_distinct(session, "completionType")
    # 硬断言(唯一会失败的方向):库里有的,代码必须都认
    assert_db_values_covered("type", db_types, typing.get_args(TaskType))
    assert_db_values_covered("completionType", db_completions, typing.get_args(CompletionType))
    assert_db_values_covered("type", db_types, TASK_TYPES)
    assert_db_values_covered("completionType", db_completions, COMPLETION_TYPES)
    # 冒烟:枚举本身不得为空(防止误删全部取值)
    assert len(TASK_TYPES) == 6 and len(COMPLETION_TYPES) == 5


# ---------- ② 同源:Literal == 服务层元组 ----------


def test_literals_match_service_enum_tuples():
    """② 路由 Literal 与服务层元组必须完全一致(两处表达、单一真源;#PB-39 的同一手法)。"""
    from app.api.v1.admin_task import CompletionType, TaskType

    assert set(typing.get_args(TaskType)) == set(TASK_TYPES)
    assert set(typing.get_args(CompletionType)) == set(COMPLETION_TYPES)
    assert list(typing.get_args(TaskType)) == list(TASK_TYPES)          # 顺序也一致(既有值在前)
    assert list(typing.get_args(CompletionType)) == list(COMPLETION_TYPES)


# ---------- ③ 8 条越界行往返 ----------


def test_out_of_scope_rows_roundtrip_accepted_and_real_rows_untouched(client, session):
    """③ 8 条越界行现值组合原样回传 → 200;且真实行**逐字段未动**(前后快照一致)。"""
    real_rows = session.execute(text(OUT_OF_SCOPE_SQL)).mappings().all()
    assert len(real_rows) == 8, [dict(r) for r in real_rows]
    assert {r["taskId"] for r in real_rows} == {
        "T2.1.2", "T2.1.3", "T2.5.1", "T2.5.2", "T2.5.3", "T2.5.4", "T2.5.5", "T2.5.6",
    }
    snapshot_before = session.execute(text(SNAPSHOT_SQL)).all()

    username, password = make_temp_admin(session)
    try:
        token = _login(client, username, password)
        # 载体:一个临时任务(不碰真实 8 行);逐个把真实行的现值组合原样 PUT 上去
        carrier = _create(client, token)
        assert carrier.status_code == 201, carrier.text
        carrier_row = carrier.json()["data"]
        for row in real_rows:
            payload = {
                "type": row["type"],
                "completionType": row["completionType"],
                "title": row["title"],
                "actionText": row["actionText"],
                "actionUrl": row["actionUrl"],
            }
            resp = client.put("/api/admin/task/" + str(carrier_row["id"]), headers=_headers(token), json=payload)
            assert resp.status_code == 200, (row["taskId"], payload, resp.text)
            data = resp.json()["data"]
            assert (data["type"], data["completionType"]) == (row["type"], row["completionType"])
        # 真实 8 行 / 全表快照必须逐字段一致(未 UPDATE、updatedAt 未变)
        assert session.execute(text(SNAPSHOT_SQL)).all() == snapshot_before
    finally:
        _cleanup_tasks(session)
        cleanup_temp_admin(session, username)


# ---------- ④ 未知值 → 400 ----------


def test_unknown_enum_value_rejected(client, session):
    """④ 未知取值:HTTP 两条路径 → 400 + 统一文案;服务层兜底守卫同样拒绝(任何调用方都写不进越界值)。"""
    username, password = make_temp_admin(session)
    try:
        token = _login(client, username, password)
        bad_type = client.post(TASK_CREATE, headers=_headers(token),
                               json={"taskId": "_test_enum_bad1", "firstLevelTaskId": "_test_fl",
                                     "stageId": "onboarding", "title": "_test", "type": "bogus",
                                     "completionType": "click_read"})
        assert bad_type.status_code == 400, bad_type.text
        assert bad_type.json()["code"] == 400 and bad_type.json()["message"] == VALIDATION_MESSAGE

        ok = _create(client, token)
        assert ok.status_code == 201, ok.text
        task_pk = ok.json()["data"]["id"]
        bad_completion = client.put("/api/admin/task/" + str(task_pk), headers=_headers(token),
                                    json={"completionType": "bogus_done"})
        assert bad_completion.status_code == 400, bad_completion.text
        assert bad_completion.json()["message"] == VALIDATION_MESSAGE

        # 服务层兜底:绕过 DTO 直接调用也被拒(证明守卫是活的,不是只靠 Literal)
        from app.services.admin_task_config import _assert_task_enums

        for payload in ({"type": "bogus"}, {"completionType": "bogus_done"}):
            try:
                _assert_task_enums(payload)
                raise AssertionError("服务层守卫未拒绝越界值: %s" % payload)
            except ApiException as exc:
                assert exc.code == 400 and exc.message == VALIDATION_MESSAGE
        _assert_task_enums({"type": "form", "completionType": "file_upload"})   # 现实值放行
    finally:
        _cleanup_tasks(session)
        cleanup_temp_admin(session, username)
