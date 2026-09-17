"""账号绑定回归(#PB-36:1 个京麦商家ID ↔ N 个商家账号,只共享进度)。

真源:project/docs/后端技术方案.md §5.2 API-22 / §6.2;方案 dev-docs/任务单/merchant-account-binding-design.md §9.1。
本文件逐例覆盖方案 §9.1 用例 1-20(每个用例 docstring 标注对应编号);用例 21/22 由门禁三连
(check_schema/check_data_encoding/check_orphan)+ 全量回归数字佐证(见汇报)。

隔离纪律(铁律 5):
- 临时商家一律用 tests/conftest.py 的 make_temp_merchant / cleanup_temp_merchant;
- 自建二级任务、直接落的进度行、绑定组/成员行、internal_notify_log 行、临时管理员
  **全部先记 id 再按 id 删除**(禁止按条件批量删);
- 内部通知默认打桩(任何用例都不得打真实飞书通道),正文留档供脱敏断言。
"""

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import bindparam, text
from sqlalchemy.exc import IntegrityError

from app.core.security import create_merchant_token, hash_password
from app.db.engine import SessionLocal, engine
from app.services import internal_notify
from app.services.merchant import JD_MERCHANT_ID_TAKEN_MESSAGE
from app.services.merchant_binding import (
    BIND_SELF_MESSAGE,
    BINDING_NOT_FOUND_MESSAGE,
    MERCHANT_NOT_FOUND_MESSAGE,
    NOT_REGISTERED_MESSAGE,
    TARGET_IN_OTHER_GROUP_MESSAGE,
    resolve_group_merchant_ids,
)
from tests.conftest import cleanup_temp_merchant, make_temp_merchant

ADMIN_PASSWORD = "Test@12345"
DUPLICATE_EVENT = internal_notify.EVENT_MERCHANT_ID_DUPLICATE_REGISTRATION

# 本轮自建实体的 id 登记表(收尾按 id 精确删除)
_MERCHANT_IDS: list = []
_TASK_IDS: list = []
_GROUP_IDS: list = []
_MEMBER_IDS: list = []
_NOTIFY_IDS: list = []
_SENT_TEXTS: list = []


@pytest.fixture()
def session():
    """本文件专用会话:**READ COMMITTED** —— 端点用另一连接提交,默认 REPEATABLE READ 会读到旧快照。"""
    s = SessionLocal(bind=engine.execution_options(isolation_level="READ COMMITTED"))
    yield s
    # 收尾顺序:先按 id 清临时商家(conftest 助手;覆盖范围 = scripts/merchant_scope.py 的动态发现,
    # 不写死表数),再清自建绑定/任务/通知行
    for merchant_id in _MERCHANT_IDS:
        cleanup_temp_merchant(s, merchant_id)
    _MERCHANT_IDS.clear()
    _cleanup_created(s)
    s.close()


@pytest.fixture(autouse=True)
def stub_im_channel(monkeypatch):
    """默认打桩内部通知发送 + **显式注入测试接收人**;正文留档供脱敏断言。

    #PB-37 A:接收人不再有源码默认值(不硬编码 PII)→ 显式注入并清 settings 缓存,
    使通知类用例不随部署方 .env 而时绿时红(需要「未配置」语义的用例用 notify_env 覆盖)。
    """
    from app.core.config import get_settings

    monkeypatch.setenv("INTERNAL_NOTIFY_RECEIVE_ID", "<OPEN_ID>_receive_id")
    get_settings.cache_clear()
    _SENT_TEXTS.clear()

    def _fake_send(target_type, target, text):
        _SENT_TEXTS.append(text)
        return True, None

    monkeypatch.setattr(internal_notify, "_send_text", _fake_send)
    yield
    _SENT_TEXTS.clear()
    get_settings.cache_clear()


# ---------- 助手 ----------


def _temp_merchant(session, current_stage: str = "onboarding", status: int = 1) -> str:
    """临时商家(复用 conftest 助手;登记 id,夹具收尾统一清理)。"""
    merchant_id = make_temp_merchant(session, current_stage=current_stage, status=status)
    _MERCHANT_IDS.append(merchant_id)
    return merchant_id


def _unique_jd() -> str:
    """唯一京麦商家ID(仅数字,长度 ≥8 以便断言部分脱敏)。"""
    return str(uuid.uuid4().int)[:10]


def _merchant_headers(merchant_id: str) -> dict:
    return {"Authorization": f"Bearer {create_merchant_token(merchant_id)}"}


def _admin_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _make_admin(session, role: str = "admin") -> str:
    username = "_test_bind_" + role + "_" + uuid.uuid4().hex[:8]
    encoded, salt = hash_password(ADMIN_PASSWORD)
    session.execute(
        text(
            "INSERT INTO admin_account (username, passwordHash, salt, realName, role, status) "
            "VALUES (:u, :h, :s, '_test 管理员', :r, 1)"
        ),
        {"u": username, "h": encoded, "s": salt, "r": role},
    )
    session.commit()
    return username


def _cleanup_admin(session, username: str) -> None:
    session.execute(text("DELETE FROM admin_account WHERE username = :u"), {"u": username})
    session.commit()


def _login(client, username: str) -> str:
    resp = client.post("/api/admin/auth/login", json={"username": username, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["token"]


def _make_task(session, stage_id: str, status: int = 1, default_completed: int = 0) -> str:
    """自建二级任务(_test_ 前缀,收尾按 taskId 删除)。"""
    task_id = "_test_" + uuid.uuid4().hex[:10]
    session.execute(
        text(
            "INSERT INTO second_level_task (taskId, firstLevelTaskId, stageId, title, type, completionType, "
            "defaultCompleted, status, sortOrder) VALUES (:t, '_test_fl', :s, '_test_task', "
            "'manual', 'manual', :d, :st, 9999)"
        ),
        {"t": task_id, "s": stage_id, "d": default_completed, "st": status},
    )
    session.commit()
    _TASK_IDS.append(task_id)
    return task_id


def _set_progress_row(session, merchant_id: str, task_id: str, status: str, completed_at=None) -> None:
    """直接落一行进度(用于构造「最早完成时间」等确定性场景;cleanup_temp_merchant 会按 merchantId 覆盖)。"""
    session.execute(
        text(
            "INSERT INTO merchant_task_progress (merchantId, taskId, status, completedAt) "
            "VALUES (:m, :t, :s, :c)"
        ),
        {"m": merchant_id, "t": task_id, "s": status, "c": completed_at},
    )
    session.commit()


def _register(client, merchant_id: str, jd_merchant_id: str):
    return client.put(
        "/api/merchant/registration",
        headers=_merchant_headers(merchant_id),
        json={"jd_merchant_id": jd_merchant_id},
    )


def _bind(client, token: str, merchant_id: str, member_merchant_id: str):
    return client.post(
        f"/api/admin/merchant/{merchant_id}/bindings",
        headers=_admin_headers(token),
        json={"member_merchant_id": member_merchant_id},
    )


def _unbind(client, token: str, merchant_id: str, member_merchant_id: str):
    return client.delete(
        f"/api/admin/merchant/{merchant_id}/bindings/{member_merchant_id}",
        headers=_admin_headers(token),
    )


def _bindings(client, token: str, merchant_id: str):
    return client.get(f"/api/admin/merchant/{merchant_id}/bindings", headers=_admin_headers(token))


def _progress(client, merchant_id: str) -> dict:
    resp = client.get("/api/task/progress", headers=_merchant_headers(merchant_id))
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _submit(client, merchant_id: str, task_id: str, status: str = "completed"):
    return client.post(
        "/api/task/progress",
        headers=_merchant_headers(merchant_id),
        json={"taskId": task_id, "status": status},
    )


def _record_group(session, group_id: int) -> int:
    _GROUP_IDS.append(int(group_id))
    rows = session.execute(
        text("SELECT id FROM merchant_binding_member WHERE group_id = :g"), {"g": int(group_id)}
    ).scalars().all()
    _MEMBER_IDS.extend(int(r) for r in rows)
    return int(group_id)


def _progress_snapshot(session, merchant_ids) -> list:
    """解绑前后逐行快照(含 completedAt/updatedAt):证明解绑**不动任何进度行**。"""
    stmt = text(
        "SELECT id, merchantId, taskId, status, completedAt, createdAt, updatedAt "
        "FROM merchant_task_progress WHERE merchantId IN :ids ORDER BY id"
    ).bindparams(bindparam("ids", expanding=True))
    return session.execute(stmt, {"ids": list(merchant_ids)}).all()


def _inconsistent_closed_group_ids(session, group_id=None) -> list:
    """不变量反证(#PB-37 E):**不应存在**「组已关闭(active_key IS NULL)但其成员里仍有 active_key=1」的状态。

    该状态会让该账号永久占用 uk_member_active 槽位 → 再也无法被重新绑定;期望命中 **0**。
    """
    sql = (
        "SELECT g.id FROM merchant_binding_group g "
        "JOIN merchant_binding_member m ON m.group_id = g.id AND m.active_key = 1 "
        "WHERE g.active_key IS NULL"
    )
    params = {}
    if group_id is not None:
        sql += " AND g.id = :g"
        params["g"] = group_id
    return list(session.execute(text(sql), params).scalars().all())


def _record_notify_rows(session, dedupe_key: str) -> None:
    """记录该去重键的通知行 id(删除仍按 id 精确执行,不做条件批量删)。"""
    rows = session.execute(
        text("SELECT id FROM internal_notify_log WHERE dedupe_key = :k"), {"k": dedupe_key}
    ).scalars().all()
    _NOTIFY_IDS.extend(int(r) for r in rows)


def _bind_and_record(client, session, token: str, merchant_id: str, member_merchant_id: str) -> int:
    """绑定并登记组/成员 id(收尾清理);断言 201。"""
    resp = _bind(client, token, merchant_id, member_merchant_id)
    assert resp.status_code == 201, resp.text
    return _record_group(session, int(resp.json()["data"]["group_id"]))


def _cleanup_created(session) -> None:
    """按记录到的 id 精确删除本轮自建实体(成员 → 组 → 进度 → 任务 → 通知行),幂等。"""
    for member_id in _MEMBER_IDS:
        session.execute(text("DELETE FROM merchant_binding_member WHERE id = :i"), {"i": member_id})
    for group_id in _GROUP_IDS:
        session.execute(text("DELETE FROM merchant_binding_group WHERE id = :i"), {"i": group_id})
    for task_id in _TASK_IDS:
        session.execute(text("DELETE FROM merchant_task_progress WHERE taskId = :t"), {"t": task_id})
        session.execute(text("DELETE FROM second_level_task WHERE taskId = :t"), {"t": task_id})
    for notify_id in _NOTIFY_IDS:
        session.execute(text("DELETE FROM internal_notify_log WHERE id = :i"), {"i": notify_id})
    session.commit()
    _TASK_IDS.clear()
    _GROUP_IDS.clear()
    _MEMBER_IDS.clear()
    _NOTIFY_IDS.clear()


# ===== 用例 1-7:绑定关系与唯一性 =====


def test_bind_creates_group_and_two_members(client, session):
    """用例 1:绑定成功(无组 → 建组):201;组 1 行 active_key=1;成员 2 行;bound_by=管理员 username。"""
    a = _temp_merchant(session)
    b = _temp_merchant(session)
    jd = _unique_jd()
    assert _register(client, a, jd).status_code == 200
    username = _make_admin(session)
    try:
        token = _login(client, username)
        resp = _bind(client, token, a, b)
        assert resp.status_code == 201, resp.text
        assert resp.json()["code"] == 0 and resp.json()["message"] == "绑定成功", resp.text
        data = resp.json()["data"]
        assert data["success"] is True
        gid = _record_group(session, int(data["group_id"]))

        group = session.execute(
            text("SELECT jd_merchant_id, active_key, created_by, closed_at FROM merchant_binding_group WHERE id = :g"),
            {"g": gid},
        ).mappings().first()
        assert group["jd_merchant_id"] == jd
        assert group["active_key"] == 1 and group["closed_at"] is None
        assert group["created_by"] == username

        members = session.execute(
            text("SELECT merchant_id, active_key, bound_by FROM merchant_binding_member "
                 "WHERE group_id = :g ORDER BY id"),
            {"g": gid},
        ).mappings().all()
        assert [(m["merchant_id"], m["active_key"], m["bound_by"]) for m in members] == [
            (a, 1, username), (b, 1, username)
        ], members

        detail = _bindings(client, token, a).json()["data"]
        assert detail["jd_merchant_id"] == jd and detail["group_id"] == str(gid)
        assert {m["merchant_id"] for m in detail["members"]} == {a, b}
        assert sum(1 for m in detail["members"] if m["is_self"]) == 1
        assert all(m["bound_by"] == username and m["bound_at"] for m in detail["members"])
    finally:
        _cleanup_admin(session, username)


def test_bind_is_idempotent(client, session):
    """用例 2:对同一成员重复绑定 → 不新增行(成员行仍 2),返回现状。"""
    a = _temp_merchant(session)
    b = _temp_merchant(session)
    jd = _unique_jd()
    assert _register(client, a, jd).status_code == 200
    username = _make_admin(session)
    try:
        token = _login(client, username)
        gid = _bind_and_record(client, session, token, a, b)
        again = _bind(client, token, a, b)
        assert again.status_code == 201, again.text
        assert int(again.json()["data"]["group_id"]) == gid
        total = session.execute(
            text("SELECT COUNT(*) FROM merchant_binding_member WHERE group_id = :g"), {"g": gid}
        ).scalar()
        active = session.execute(
            text("SELECT COUNT(*) FROM merchant_binding_member WHERE group_id = :g AND active_key = 1"),
            {"g": gid},
        ).scalar()
        assert (total, active) == (2, 2), (total, active)
    finally:
        _cleanup_admin(session, username)


def test_bind_target_in_other_group_rejected(client, session):
    """用例 3:目标已在其它组 → 400 该账号已绑定到其它商家;两表行数不变。"""
    a1 = _temp_merchant(session)
    a2 = _temp_merchant(session)
    b = _temp_merchant(session)
    assert _register(client, a1, _unique_jd()).status_code == 200
    assert _register(client, a2, _unique_jd()).status_code == 200
    username = _make_admin(session)
    try:
        token = _login(client, username)
        _bind_and_record(client, session, token, a1, b)
        before = (
            session.execute(text("SELECT COUNT(*) FROM merchant_binding_group")).scalar(),
            session.execute(text("SELECT COUNT(*) FROM merchant_binding_member")).scalar(),
        )
        resp = _bind(client, token, a2, b)
        assert resp.status_code == 400, resp.text
        assert resp.json()["message"] == TARGET_IN_OTHER_GROUP_MESSAGE
        after = (
            session.execute(text("SELECT COUNT(*) FROM merchant_binding_group")).scalar(),
            session.execute(text("SELECT COUNT(*) FROM merchant_binding_member")).scalar(),
        )
        assert after == before, (before, after)
    finally:
        _cleanup_admin(session, username)


def test_bind_self_rejected(client, session):
    """用例 4:绑定自身 → 400 不能绑定自身(不建组、不写成员行)。"""
    a = _temp_merchant(session)
    assert _register(client, a, _unique_jd()).status_code == 200
    username = _make_admin(session)
    try:
        token = _login(client, username)
        resp = _bind(client, token, a, a)
        assert resp.status_code == 400, resp.text
        assert resp.json()["message"] == BIND_SELF_MESSAGE
        assert session.execute(
            text("SELECT COUNT(*) FROM merchant_binding_member WHERE merchant_id = :m"), {"m": a}
        ).scalar() == 0
    finally:
        _cleanup_admin(session, username)


def test_bind_initiator_without_registration_rejected(client, session):
    """用例 5:发起方未登记 jd_merchant_id → 400 该商家尚未登记京麦商家ID，无法绑定;不建组。"""
    a = _temp_merchant(session)          # 未登记京麦ID
    b = _temp_merchant(session)
    username = _make_admin(session)
    try:
        token = _login(client, username)
        resp = _bind(client, token, a, b)
        assert resp.status_code == 400, resp.text
        assert resp.json()["message"] == NOT_REGISTERED_MESSAGE
        assert session.execute(
            text("SELECT COUNT(*) FROM merchant_binding_group WHERE created_by = :u"), {"u": username}
        ).scalar() == 0
    finally:
        _cleanup_admin(session, username)


def test_bind_target_missing_or_soft_deleted_404(client, session):
    """用例 6:目标不存在 / 已软删 → 404 商家不存在(不自动创建、不写成员行)。"""
    a = _temp_merchant(session)
    soft_deleted = _temp_merchant(session)
    assert _register(client, a, _unique_jd()).status_code == 200
    username = _make_admin(session)
    try:
        token = _login(client, username)
        missing = _bind(client, token, a, "_test_bind_missing_" + uuid.uuid4().hex[:6])
        assert missing.status_code == 404, missing.text
        assert missing.json()["message"] == MERCHANT_NOT_FOUND_MESSAGE

        session.execute(
            text("UPDATE merchant SET deleted_at = NOW() WHERE merchant_id = :m"), {"m": soft_deleted}
        )
        session.commit()
        deleted = _bind(client, token, a, soft_deleted)
        assert deleted.status_code == 404, deleted.text
        assert deleted.json()["message"] == MERCHANT_NOT_FOUND_MESSAGE

        ghost = _bindings(client, token, "_test_bind_ghost_" + uuid.uuid4().hex[:6])
        assert ghost.status_code == 404, ghost.text
        assert ghost.json()["message"] == MERCHANT_NOT_FOUND_MESSAGE
    finally:
        _cleanup_admin(session, username)


def test_second_active_group_for_same_jd_rejected_by_db(client, session):
    """用例 7:一个 jd_merchant_id 只能一个活跃组 —— 第二条活跃组被数据库层拒绝(1062)。"""
    a = _temp_merchant(session)
    b = _temp_merchant(session)
    jd = _unique_jd()
    assert _register(client, a, jd).status_code == 200
    username = _make_admin(session)
    try:
        token = _login(client, username)
        gid = _bind_and_record(client, session, token, a, b)
        with pytest.raises(IntegrityError) as exc:
            session.execute(
                text("INSERT INTO merchant_binding_group (jd_merchant_id, active_key, created_by) "
                     "VALUES (:j, 1, '_test_probe')"),
                {"j": jd},
            )
            session.commit()
        assert "1062" in str(exc.value) or "Duplicate" in str(exc.value), str(exc.value)
        session.rollback()
        # 已关闭组(active_key=NULL)可与活跃组同 jd 共存 → 历史行可无限保留
        session.execute(
            text("INSERT INTO merchant_binding_group (jd_merchant_id, active_key, created_by) "
                 "VALUES (:j, NULL, '_test_probe')"),
            {"j": jd},
        )
        session.commit()
        _GROUP_IDS.append(int(session.execute(
            text("SELECT id FROM merchant_binding_group WHERE jd_merchant_id = :j AND active_key IS NULL"),
            {"j": jd},
        ).scalar()))
        assert session.execute(
            text("SELECT active_key FROM merchant_binding_group WHERE id = :g"), {"g": gid}
        ).scalar() == 1
    finally:
        _cleanup_admin(session, username)


# ===== 用例 8-13:进度并集读取口径 =====


def test_progress_union_read(client, session):
    """用例 8:进度并集 —— A 完成 T1、B 完成 T2 → 两者 completedTasks 均含 T1+T2,remaining 相应减少。"""
    a = _temp_merchant(session)
    b = _temp_merchant(session)
    assert _register(client, a, _unique_jd()).status_code == 200
    username = _make_admin(session)
    try:
        token = _login(client, username)
        t1 = _make_task(session, "onboarding")
        t2 = _make_task(session, "onboarding")
        before = _progress(client, a)
        assert t1 not in before["completedTasks"] and t2 not in before["completedTasks"]
        assert t1 in before["phase1_remaining_task_ids"] and t2 in before["phase1_remaining_task_ids"]

        _bind_and_record(client, session, token, a, b)
        assert _submit(client, a, t1).status_code == 201
        assert _submit(client, b, t2).status_code == 201

        for mid in (a, b):
            data = _progress(client, mid)
            assert {t1, t2} <= set(data["completedTasks"]), (mid, data["completedTasks"])
            assert t1 not in data["phase1_remaining_task_ids"], mid
            assert t2 not in data["phase1_remaining_task_ids"], mid
    finally:
        _cleanup_admin(session, username)


def test_group_completed_at_is_earliest_and_monotonic(client, session):
    """用例 9:同一 taskId 的完成时间取组内最早,且不因后写入而后移(单调)。"""
    from app.services.task_progress import get_group_progress

    a = _temp_merchant(session)
    b = _temp_merchant(session)
    assert _register(client, a, _unique_jd()).status_code == 200
    username = _make_admin(session)
    try:
        token = _login(client, username)
        _bind_and_record(client, session, token, a, b)
        task_id = _make_task(session, "onboarding")
        early = datetime.now().replace(microsecond=0) - timedelta(hours=3)
        _set_progress_row(session, a, task_id, "completed", early)

        state = get_group_progress(session, a)
        assert state["completed_at"][task_id] == early
        assert state["completed_task_ids"] == [task_id]

        # B 走真实写路径再完成一次(其行 completedAt = now,晚于 early)
        assert _submit(client, b, task_id).status_code == 201
        after = get_group_progress(session, a)
        assert after["completed_at"][task_id] == early, "后写入不得把店铺级完成时间往后推"
        assert session.execute(
            text("SELECT completedAt FROM merchant_task_progress WHERE merchantId = :m AND taskId = :t"),
            {"m": a, "t": task_id},
        ).scalar() == early
    finally:
        _cleanup_admin(session, username)


def test_phase2_gate_follows_group_union(client, session):
    """用例 10:门禁按并集 —— A 已解锁阶段二 ⇒ 同组 B 可提交阶段二任务;未绑定 B 仍 403。"""
    a = _temp_merchant(session, current_stage="shop_setup")
    b = _temp_merchant(session)
    outsider = _temp_merchant(session)
    assert _register(client, a, _unique_jd()).status_code == 200
    username = _make_admin(session)
    try:
        token = _login(client, username)
        t2 = _make_task(session, "brand")      # PHASE2_STAGE_IDS 内
        assert _submit(client, b, t2).status_code == 403
        assert _submit(client, outsider, t2).status_code == 403

        _bind_and_record(client, session, token, a, b)
        allowed = _submit(client, b, t2)
        assert allowed.status_code == 201, allowed.text
        assert allowed.json()["data"]["stage2_unlocked"] is True
        assert _submit(client, outsider, t2).status_code == 403, "并集只覆盖组内"
    finally:
        _cleanup_admin(session, username)


def test_stages_unlock_by_group_or(client, session):
    """用例 11:组内 OR 解锁 —— 任一成员已解锁 ⇒ 另一成员 /api/task/stages 不再返回锁定壳。"""
    a = _temp_merchant(session, current_stage="shop_setup")
    b = _temp_merchant(session)
    outsider = _temp_merchant(session)
    assert _register(client, a, _unique_jd()).status_code == 200
    username = _make_admin(session)

    def _locked_map(merchant_id: str) -> dict:
        resp = client.get("/api/task/stages", headers=_merchant_headers(merchant_id))
        assert resp.status_code == 200, resp.text
        return {s["stageId"]: s["locked"] for s in resp.json()["data"]}

    try:
        token = _login(client, username)
        phase2_stage = session.execute(
            text("SELECT stage_id FROM stage_config WHERE phase_num = 2 ORDER BY sort_order LIMIT 1")
        ).scalar()
        assert phase2_stage, "前置:阶段配置存在"
        assert _locked_map(b)[phase2_stage] is True
        _bind_and_record(client, session, token, a, b)
        assert _locked_map(b)[phase2_stage] is False
        assert _locked_map(outsider)[phase2_stage] is True
    finally:
        _cleanup_admin(session, username)


def test_data_center_two_layer_semantics(client, session):
    """用例 12:data_center_unlocked = 本账号 persisted OR 组内 listing 并集派生(双层语义)。"""
    a = _temp_merchant(session, current_stage="shop_setup")
    b = _temp_merchant(session, current_stage="shop_setup")
    c = _temp_merchant(session, current_stage="shop_setup")
    d = _temp_merchant(session, current_stage="shop_setup")
    assert _register(client, a, _unique_jd()).status_code == 200
    assert _register(client, c, _unique_jd()).status_code == 200
    username = _make_admin(session)
    try:
        token = _login(client, username)
        _bind_and_record(client, session, token, a, b)
        _bind_and_record(client, session, token, c, d)

        # 正向:组内 listing 任务并集全部完成 → 未持久化的 B 也解锁
        listing_tasks = session.execute(
            text("SELECT taskId FROM second_level_task WHERE stageId = 'listing' "
                 "AND status = 1 AND defaultCompleted <> 1")
        ).scalars().all()
        assert listing_tasks, "前置:存在启用的 listing 任务"
        for task_id in listing_tasks:
            _set_progress_row(session, a, task_id, "completed", datetime.now().replace(microsecond=0))
        assert _progress(client, b)["data_center_unlocked"] is True
        assert _progress(client, a)["data_center_unlocked"] is True
        assert session.execute(
            text("SELECT data_center_unlocked FROM merchant WHERE merchant_id = :m"), {"m": b}
        ).scalar() == 0, "读路径不得写库"

        # 反向:账号级持久化标记不共享
        session.execute(
            text("UPDATE merchant SET data_center_unlocked = 1 WHERE merchant_id = :m"), {"m": c}
        )
        session.commit()
        assert _progress(client, c)["data_center_unlocked"] is True
        assert _progress(client, d)["data_center_unlocked"] is False
    finally:
        _cleanup_admin(session, username)


def test_cancel_completion_unions_within_group(client, session):
    """用例 13:并集后果 —— A 取消完成但 B 仍 completed ⇒ 组内仍为 completed;两人都取消才回落。"""
    a = _temp_merchant(session)
    b = _temp_merchant(session)
    assert _register(client, a, _unique_jd()).status_code == 200
    username = _make_admin(session)
    try:
        token = _login(client, username)
        _bind_and_record(client, session, token, a, b)
        task_id = _make_task(session, "onboarding")
        assert _submit(client, a, task_id).status_code == 201
        assert _submit(client, b, task_id).status_code == 201
        assert task_id in _progress(client, a)["completedTasks"]

        assert _submit(client, a, task_id, "pending").status_code == 201
        assert task_id in _progress(client, a)["completedTasks"], "B 的行仍在 ⇒ 组内仍视为完成"

        assert _submit(client, b, task_id, "pending").status_code == 201
        assert task_id not in _progress(client, a)["completedTasks"], "两人都取消才回落 pending"
        assert task_id not in _progress(client, b)["completedTasks"]
    finally:
        _cleanup_admin(session, username)


# ===== 用例 14-17:解绑与权限 =====


def test_release_falls_back_and_keeps_progress_rows(client, session):
    """用例 14:解绑回落 —— 各自只见自己的完成集合;merchant_task_progress 逐行不变。"""
    a = _temp_merchant(session)
    b = _temp_merchant(session)
    assert _register(client, a, _unique_jd()).status_code == 200
    username = _make_admin(session)
    try:
        token = _login(client, username)
        _bind_and_record(client, session, token, a, b)
        t1 = _make_task(session, "onboarding")
        t2 = _make_task(session, "onboarding")
        assert _submit(client, a, t1).status_code == 201
        assert _submit(client, b, t2).status_code == 201
        assert {t1, t2} <= set(_progress(client, a)["completedTasks"])
        before = _progress_snapshot(session, (a, b))

        released = _unbind(client, token, a, b)
        assert released.status_code == 200, released.text
        assert released.json()["code"] == 0 and released.json()["message"] == "已解绑", released.text
        assert released.json()["data"] == {"success": True}

        pa, pb = _progress(client, a), _progress(client, b)
        assert t1 in pa["completedTasks"] and t2 not in pa["completedTasks"], pa
        assert t2 in pb["completedTasks"] and t1 not in pb["completedTasks"], pb
        assert _progress_snapshot(session, (a, b)) == before, "解绑不得改动任何进度行"
        assert resolve_group_merchant_ids(session, a) == [a]
        assert resolve_group_merchant_ids(session, b) == [b]
    finally:
        _cleanup_admin(session, username)


def test_release_closes_group_when_under_two_members(client, session):
    """用例 15(+#PB-37 E):解绑后活跃成员 < 2 → 组关闭 **且同事务退役最后一名活跃成员行**;

    并回归「同一账号必须能再次被绑定」(修复前该账号会永久撞 uk_member_active → 1062/500)。
    """
    a = _temp_merchant(session)
    b = _temp_merchant(session)
    assert _register(client, a, _unique_jd()).status_code == 200
    username = _make_admin(session)
    try:
        token = _login(client, username)
        gid = _bind_and_record(client, session, token, a, b)
        assert _unbind(client, token, a, b).status_code == 200

        group = session.execute(
            text("SELECT active_key, closed_at, closed_by FROM merchant_binding_group WHERE id = :g"),
            {"g": gid},
        ).mappings().first()
        assert group["active_key"] is None
        assert group["closed_at"] is not None and group["closed_by"] == username

        member = session.execute(
            text("SELECT active_key, released_at, released_by FROM merchant_binding_member "
                 "WHERE group_id = :g AND merchant_id = :m"),
            {"g": gid, "m": b},
        ).mappings().first()
        assert member["active_key"] is None
        assert member["released_at"] is not None and member["released_by"] == username
        assert session.execute(
            text("SELECT COUNT(*) FROM merchant_binding_member WHERE group_id = :g"), {"g": gid}
        ).scalar() == 2, "解绑保留行(留痕),不删历史"

        # #PB-37 E:最后一名成员的成员行也必须退役(否则该账号永久无法再被绑定)
        last = session.execute(
            text("SELECT active_key, released_at, released_by FROM merchant_binding_member "
                 "WHERE group_id = :g AND merchant_id = :m"),
            {"g": gid, "m": a},
        ).mappings().first()
        assert last["active_key"] is None, "关组后不得残留 active_key=1 的成员行"
        assert last["released_at"] is not None and last["released_by"] == username
        assert session.execute(
            text("SELECT COUNT(*) FROM merchant_binding_member WHERE group_id = :g AND active_key = 1"),
            {"g": gid},
        ).scalar() == 0
        assert _inconsistent_closed_group_ids(session, gid) == [], "组关闭 + 残留活跃成员行"

        # 解绑后详情回到「未绑定」形态
        detail = _bindings(client, token, a).json()["data"]
        assert detail["group_id"] is None
        assert len(detail["members"]) == 1 and detail["members"][0]["is_self"] is True
        assert detail["members"][0]["bound_at"] is None and detail["members"][0]["bound_by"] is None

        # 核心回归(#PB-37 E):同一账号必须能**再次被绑定**(修复前 1062 → 500/误报 400)
        new_gid = _bind_and_record(client, session, token, a, b)
        assert new_gid != gid, "重新绑定应新建一个活跃组"
        assert session.execute(
            text("SELECT active_key FROM merchant_binding_group WHERE id = :g"), {"g": new_gid}
        ).scalar() == 1
        assert session.execute(
            text("SELECT COUNT(*) FROM merchant_binding_member WHERE group_id = :g AND active_key = 1"),
            {"g": new_gid},
        ).scalar() == 2
        assert _inconsistent_closed_group_ids(session) == []
    finally:
        _cleanup_admin(session, username)


def test_release_keeps_group_active_when_two_members_remain(client, session):
    """#PB-37 E 反向保护:3 人组解绑 1 人(剩 2 人)→ 组**保持活跃**、剩 2 行 active_key=1、被解绑那行 NULL。"""
    a = _temp_merchant(session)
    b = _temp_merchant(session)
    c = _temp_merchant(session)
    assert _register(client, a, _unique_jd()).status_code == 200
    username = _make_admin(session)
    try:
        token = _login(client, username)
        gid = _bind_and_record(client, session, token, a, b)
        assert _record_group(session, _bind_and_record(client, session, token, a, c)) == gid, "同一京麦ID 应复用同组"
        assert _unbind(client, token, a, b).status_code == 200

        group = session.execute(
            text("SELECT active_key, closed_at FROM merchant_binding_group WHERE id = :g"), {"g": gid}
        ).mappings().first()
        assert group["active_key"] == 1 and group["closed_at"] is None, "剩 2 人时组必须保持活跃"
        active_rows = session.execute(
            text("SELECT merchant_id FROM merchant_binding_member WHERE group_id = :g AND active_key = 1"),
            {"g": gid},
        ).scalars().all()
        assert sorted(active_rows) == sorted([a, c]), active_rows
        released = session.execute(
            text("SELECT active_key, released_at, released_by FROM merchant_binding_member "

                 "WHERE group_id = :g AND merchant_id = :m"),
            {"g": gid, "m": b},
        ).mappings().first()
        assert released["active_key"] is None
        assert released["released_at"] is not None and released["released_by"] == username
    finally:
        _cleanup_admin(session, username)

def test_release_missing_relation_404(client, session):
    """用例 16:解绑不存在的关系 → 404 绑定关系不存在。"""
    a = _temp_merchant(session)
    b = _temp_merchant(session)
    outsider = _temp_merchant(session)
    assert _register(client, a, _unique_jd()).status_code == 200
    username = _make_admin(session)
    try:
        token = _login(client, username)
        none_yet = _unbind(client, token, a, b)
        assert none_yet.status_code == 404, none_yet.text
        assert none_yet.json()["message"] == BINDING_NOT_FOUND_MESSAGE

        _bind_and_record(client, session, token, a, b)
        not_in_group = _unbind(client, token, a, outsider)
        assert not_in_group.status_code == 404, not_in_group.text
        assert not_in_group.json()["message"] == BINDING_NOT_FOUND_MESSAGE
        assert session.execute(
            text("SELECT COUNT(*) FROM merchant_binding_member WHERE merchant_id IN (:a, :b) AND active_key = 1"),
            {"a": a, "b": b},
        ).scalar() == 2, "失败解绑不得破坏既有关系"
    finally:
        _cleanup_admin(session, username)


def test_bindings_permissions(client, session):
    """用例 17:GET 需登录(200);POST/DELETE 需 admin/super_admin,viewer → 403;无 token → 401。"""
    viewer = _make_admin(session, "viewer")
    admin = _make_admin(session, "admin")
    a = _temp_merchant(session)
    b = _temp_merchant(session)
    assert _register(client, a, _unique_jd()).status_code == 200
    try:
        path = f"/api/admin/merchant/{a}/bindings"
        assert client.get(path).status_code == 401
        assert client.post(path, json={"member_merchant_id": b}).status_code == 401
        assert client.delete(f"{path}/{b}").status_code == 401

        viewer_token = _login(client, viewer)
        assert _bindings(client, viewer_token, a).status_code == 200
        assert _bind(client, viewer_token, a, b).status_code == 403
        assert _unbind(client, viewer_token, a, b).status_code == 403
        assert session.execute(
            text("SELECT COUNT(*) FROM merchant_binding_member WHERE merchant_id IN (:a, :b)"), {"a": a, "b": b}
        ).scalar() == 0, "403 不得产生任何写入"

        admin_token = _login(client, admin)
        _bind_and_record(client, session, admin_token, a, b)
        assert _unbind(client, admin_token, a, b).status_code == 200
    finally:
        _cleanup_admin(session, viewer)
        _cleanup_admin(session, admin)


# ===== 用例 18-20:重复登记拒绝 + 内部通知 =====


def test_duplicate_registration_rejected(client, session):
    """用例 18:两条占用判据 → 400 该商家已被登记;本人重提交同值 200;本人所在组内登记同值 允许。"""
    owner = _temp_merchant(session)
    other = _temp_merchant(session)
    member = _temp_merchant(session)
    third = _temp_merchant(session)
    jd = _unique_jd()
    assert _register(client, owner, jd).status_code == 200
    username = _make_admin(session)
    try:
        token = _login(client, username)

        # 判据①:别的活跃账号已登记同值
        conflict = _register(client, other, jd)
        assert conflict.status_code == 400, conflict.text
        assert conflict.json()["message"] == JD_MERCHANT_ID_TAKEN_MESSAGE
        assert session.execute(
            text("SELECT jd_merchant_id FROM merchant WHERE merchant_id = :m"), {"m": other}
        ).scalar() is None, "写入不得发生"
        assert len(_SENT_TEXTS) == 1, "判据①命中应触发一次内部通知"

        # 本人重提交同值 = 幂等(200),不额外触发通知
        assert _register(client, owner, jd).status_code == 200
        assert len(_SENT_TEXTS) == 1

        # 组内成员登记同值 → 允许(判据① 排除本组账号)
        _bind_and_record(client, session, token, owner, member)
        in_group = _register(client, member, jd)
        assert in_group.status_code == 200, in_group.text
        assert session.execute(
            text("SELECT jd_merchant_id FROM merchant WHERE merchant_id = :m"), {"m": member}
        ).scalar() == jd

        # 判据②:该值已有活跃组(清空 owner 登记后,该值不再被任何账号登记)
        assert _register(client, owner, "").status_code == 200
        second = _register(client, third, jd)
        assert second.status_code == 400, second.text
        assert second.json()["message"] == JD_MERCHANT_ID_TAKEN_MESSAGE
        assert session.execute(
            text("SELECT jd_merchant_id FROM merchant WHERE merchant_id = :m"), {"m": third}
        ).scalar() is None
    finally:
        _record_notify_rows(session, "jd:" + jd)
        _cleanup_admin(session, username)


def test_duplicate_registration_notify_dedupe_24h(client, session, caplog):
    """用例 19:同一 jd 连续申请 5 次 → sent 行 = 1、其余 4 次只 logger.warning;5 次均 400。"""
    owner = _temp_merchant(session)
    other = _temp_merchant(session)
    jd = _unique_jd()
    assert _register(client, owner, jd).status_code == 200
    try:
        for _ in range(5):
            resp = _register(client, other, jd)
            assert resp.status_code == 400, resp.text
            assert resp.json()["message"] == JD_MERCHANT_ID_TAKEN_MESSAGE

        rows = session.execute(
            text("SELECT id, status, dedupe_key FROM internal_notify_log "
                 "WHERE event_type = :e AND dedupe_key = :k"),
            {"e": DUPLICATE_EVENT, "k": "jd:" + jd},
        ).mappings().all()
        assert len(rows) == 1, rows
        assert rows[0]["status"] == "sent"
        assert rows[0]["dedupe_key"] == "jd:" + jd
        assert len(_SENT_TEXTS) == 1, "24h 窗口内只发送一次"
        skipped = [r for r in caplog.records if "已发送,跳过" in r.getMessage()]
        assert len(skipped) == 4, [r.getMessage() for r in caplog.records]
    finally:
        _record_notify_rows(session, "jd:" + jd)


def test_duplicate_registration_notify_masks_identifiers(client, session, caplog):
    """用例 20:通知正文与通知行不含完整手机号;申请商家ID 为部分脱敏(保前 4 后 4)。"""
    from app.core.utils import mask_jd_merchant_id, mask_phone

    owner = _temp_merchant(session)
    other = _temp_merchant(session)
    jd = _unique_jd()
    phone = "139" + str(uuid.uuid4().int)[:8]
    session.execute(text("UPDATE merchant SET phone = :p WHERE merchant_id = :m"), {"p": phone, "m": other})
    session.commit()
    assert _register(client, owner, jd).status_code == 200
    try:
        resp = _register(client, other, jd)
        assert resp.status_code == 400, resp.text
        assert len(_SENT_TEXTS) == 1
        text_body = _SENT_TEXTS[0]
        assert mask_phone(phone) in text_body and phone not in text_body
        assert mask_jd_merchant_id(jd) in text_body and jd not in text_body
        assert other in text_body and "京麦商家ID重复登记申请" in text_body

        row = session.execute(
            text("SELECT target, error_message, merchant_id, dedupe_key FROM internal_notify_log "
                 "WHERE event_type = :e AND dedupe_key = :k"),
            {"e": DUPLICATE_EVENT, "k": "jd:" + jd},
        ).mappings().first()
        assert row is not None
        assert phone not in str(row["target"]) and phone not in str(row["merchant_id"])
        assert phone not in str(row["error_message"])
        # 唯一按设计保留完整 ID 的字段是去重键(方案 §5.3 明文 jd:<jd_merchant_id>;内部幂等键,不进 IM 正文)
        assert row["dedupe_key"] == "jd:" + jd
        # 日志侧不得出现完整手机号/完整京麦ID(通知函数只打脱敏值)
        leaked = [r.getMessage() for r in caplog.records
                  if phone in r.getMessage() or jd in r.getMessage()]
        assert leaked == [], leaked
    finally:
        _record_notify_rows(session, "jd:" + jd)


# ===== 用例 22:无绑定 = 行为不变(服务层证据;全量回归数字见汇报) =====


# ===== #PB-37 A:内部通知接收人未配置 = 显式跳过(源码不硬编码 PII) =====


@pytest.fixture()
def notify_env(monkeypatch):
    """按需覆盖内部通知相关环境变量,并清 settings 缓存(值只由 .env/环境变量注入,#PB-37 A)。"""
    from app.core.config import get_settings

    def _set(receive_id: str) -> None:
        monkeypatch.setenv("INTERNAL_NOTIFY_RECEIVE_ID", receive_id)
        get_settings.cache_clear()

    yield _set
    monkeypatch.delenv("INTERNAL_NOTIFY_RECEIVE_ID", raising=False)
    get_settings.cache_clear()


def _trigger_duplicate_registration(client, session):
    """造一对「owner 已登记 + other 重登记」的临时商家,触发一次重复登记 400。返回 (owner, other, jd)。"""
    owner = _temp_merchant(session)
    other = _temp_merchant(session)
    jd = _unique_jd()
    assert _register(client, owner, jd).status_code == 200
    return owner, other, jd


def test_internal_notify_skips_when_receive_id_unconfigured(client, session, notify_env, caplog):
    """#PB-37 A:接收人未配置 → 通知**显式跳过**(不发送、不写行、不影响 400),并留下说明日志。"""
    notify_env("")
    owner, other, jd = _trigger_duplicate_registration(client, session)
    resp = _register(client, other, jd)
    assert resp.status_code == 400, resp.text
    assert resp.json()["message"] == JD_MERCHANT_ID_TAKEN_MESSAGE
    assert _SENT_TEXTS == [], "未配置接收人时不得调用发送"
    rows = session.execute(
        text("SELECT COUNT(*) FROM internal_notify_log WHERE dedupe_key = :k"), {"k": "jd:" + jd}
    ).scalar()
    assert rows == 0, "未配置接收人时不得写通知行"
    skipped = [r.getMessage() for r in caplog.records if "内部通知跳过" in r.getMessage()]
    assert skipped and "未配置" in skipped[0], skipped


def test_internal_notify_sends_when_receive_id_configured(client, session, notify_env):
    """#PB-37 A:已配置接收人 → 通知正常发送并落一条 sent 行(发送通道仍打桩,不打真实飞书)。"""
    notify_env("<OPEN_ID>_receive_id")
    owner, other, jd = _trigger_duplicate_registration(client, session)
    try:
        resp = _register(client, other, jd)
        assert resp.status_code == 400, resp.text
        assert len(_SENT_TEXTS) == 1, _SENT_TEXTS
        row = session.execute(
            text("SELECT status, target FROM internal_notify_log WHERE dedupe_key = :k"), {"k": "jd:" + jd}
        ).mappings().first()
        assert row is not None and row["status"] == "sent"
        assert row["target"] == "<OPEN_ID>_receive_id"
    finally:
        _record_notify_rows(session, "jd:" + jd)


def test_receive_id_default_is_empty_and_startup_validation_unaffected(monkeypatch):
    """#PB-37 A:源码默认值为空串(无 PII);空值不参与启动期 fail-fast,且 fail-fast 本身仍有效。"""
    from app.core.config import ConfigurationError, Settings, validate_startup_settings

    # 1) 读**字段默认值**(不看实例:实例可能被环境变量/.env 覆盖):必须为空
    #    —— 源码内不得残留真实 open_id 等 PII
    assert Settings.model_fields["INTERNAL_NOTIFY_RECEIVE_ID"].default == ""
    bare = Settings(_env_file=None)
    # 2) dev 环境:直接放行(未配置接收人不影响本地开发/测试)
    validate_startup_settings(bare)
    # 3) 非 dev 环境 + 合规密钥 + 接收人留空:仍放行(该字段**不**纳入启动期强校验)
    prod = Settings(
        _env_file=None, DEBUG=False, LOGIN_MODE="real",
        JWT_SECRET="a" * 64, ADMIN_JWT_SECRET="b" * 64, DB_PASS="strong-pass-not-dev",
        FEISHU_APP_ID="cli_demo", FEISHU_APP_SECRET="feishu-secret-value",
        INTERNAL_NOTIFY_RECEIVE_ID="",
    )
    validate_startup_settings(prod)
    # 4) 负向对照:fail-fast 未被削弱 —— 仍为公开 dev 兜底密钥时照样拒绝启动
    with pytest.raises(ConfigurationError):
        validate_startup_settings(Settings(
            _env_file=None, DEBUG=False, LOGIN_MODE="real",
            JWT_SECRET="dev-secret-key-change-in-production", ADMIN_JWT_SECRET="x" * 40,
            DB_PASS="strong-pass-not-dev", FEISHU_APP_ID="cli_demo", FEISHU_APP_SECRET="feishu-secret-value",
        ))


# ===== #PB-37 D:并发唯一键冲突 → 回滚 + 重读 → 结构化 400(确定性打桩,无 sleep/概率) =====


def _concurrent_insert_group(session, jd_merchant_id: str, initiator: str, member: str) -> int:
    """模拟**并发事务**(独立连接):建一个活跃组 + 两名成员并提交。全部 id 登记待清理。"""
    session.execute(
        text("INSERT INTO merchant_binding_group (jd_merchant_id, active_key, created_by) "
             "VALUES (:j, 1, '_test_concurrent')"),
        {"j": jd_merchant_id},
    )
    session.commit()
    group_id = int(session.execute(
        text("SELECT id FROM merchant_binding_group WHERE jd_merchant_id = :j AND active_key = 1"),
        {"j": jd_merchant_id},
    ).scalar())
    for merchant_id in (initiator, member):
        session.execute(
            text("INSERT INTO merchant_binding_member (group_id, merchant_id, active_key, bound_by) "
                 "VALUES (:g, :m, 1, '_test_concurrent')"),
            {"g": group_id, "m": merchant_id},
        )
    session.commit()
    _record_group(session, group_id)
    return group_id


def _conflict_spy(session, monkeypatch, concurrent_action):
    """把并发插入精确卡在「目标账号预检查(第 2 次读组)之后、写库之前」——确定性,不用 sleep。

    bind_member 的调用序列固定为:① 读发起方所在组 → ② 读目标账号所在组 → ③ 写库(建组/加成员)。
    因此第 2 次读组时执行并发插入,即可稳定复现「预检查通过、写入撞唯一键」的窗口。
    """
    from app.services import merchant_binding

    real = merchant_binding._active_group_of_merchant
    calls = {"n": 0}

    def spy(db, merchant_id):
        calls["n"] += 1
        result = real(db, merchant_id)   # 先按原实现读取:预检查必须**仍然通过**
        if calls["n"] == 2:
            concurrent_action()          # 读完之后、写库之前:并发事务插入并提交
        return result

    monkeypatch.setattr(merchant_binding, "_active_group_of_merchant", spy)
    return calls


def test_bind_concurrent_group_conflict_returns_400(client, session, monkeypatch, caplog):
    """#PB-37 D:并发对同一京麦ID 建组(uk_group_active 1062)→ 400「该京麦商家ID已有绑定组…」+ **无半写行**。"""
    from app.services.merchant_binding import JD_MERCHANT_ID_BOUND_MESSAGE

    a = _temp_merchant(session)
    b = _temp_merchant(session)
    x = _temp_merchant(session)
    y = _temp_merchant(session)
    jd = _unique_jd()
    assert _register(client, a, jd).status_code == 200
    username = _make_admin(session)
    try:
        token = _login(client, username)
        before = (
            session.execute(text("SELECT COUNT(*) FROM merchant_binding_group")).scalar(),
            session.execute(text("SELECT COUNT(*) FROM merchant_binding_member")).scalar(),
        )
        _conflict_spy(session, monkeypatch, lambda: _concurrent_insert_group(session, jd, x, y))

        resp = _bind(client, token, a, b)
        assert resp.status_code == 400, resp.text
        assert resp.json()["code"] == 400 and resp.json()["message"] == JD_MERCHANT_ID_BOUND_MESSAGE
        monkeypatch.undo()

        after = (
            session.execute(text("SELECT COUNT(*) FROM merchant_binding_group")).scalar(),
            session.execute(text("SELECT COUNT(*) FROM merchant_binding_member")).scalar(),
        )
        assert after == (before[0] + 1, before[1] + 2), (before, after)
        assert session.execute(
            text("SELECT COUNT(*) FROM merchant_binding_group WHERE created_by = :u"), {"u": username}
        ).scalar() == 0, "失败事务不得留下组行(半写)"
        assert session.execute(
            text("SELECT COUNT(*) FROM merchant_binding_member WHERE merchant_id IN (:a, :b)"), {"a": a, "b": b}
        ).scalar() == 0, "失败事务不得留下成员行(半写)"
        assert session.execute(
            text("SELECT COUNT(*) FROM merchant_binding_group WHERE jd_merchant_id = :j AND active_key = 1"),
            {"j": jd},
        ).scalar() == 1, "并发赢家的组必须完好"
        conflicts = [r.getMessage() for r in caplog.records if "绑定并发冲突" in r.getMessage()]
        assert conflicts and "已被并发建立活跃组" in conflicts[0], conflicts
    finally:
        _cleanup_admin(session, username)


def test_bind_concurrent_member_conflict_returns_400(client, session, monkeypatch, caplog):
    """#PB-37 D:并发把同一账号绑进别的组(uk_member_active 1062)→ 400「该账号已绑定到其它商家」+ 无半写行。"""
    from app.services.merchant_binding import TARGET_IN_OTHER_GROUP_MESSAGE as EXPECTED_MESSAGE

    a = _temp_merchant(session)
    b = _temp_merchant(session)
    x = _temp_merchant(session)
    y = _temp_merchant(session)
    jd_a = _unique_jd()
    jd_other = _unique_jd()
    assert _register(client, a, jd_a).status_code == 200
    username = _make_admin(session)
    try:
        token = _login(client, username)
        before = (
            session.execute(text("SELECT COUNT(*) FROM merchant_binding_group")).scalar(),
            session.execute(text("SELECT COUNT(*) FROM merchant_binding_member")).scalar(),
        )
        _conflict_spy(session, monkeypatch, lambda: _concurrent_insert_group(session, jd_other, x, b))

        resp = _bind(client, token, a, b)
        assert resp.status_code == 400, resp.text
        assert resp.json()["message"] == EXPECTED_MESSAGE, resp.text
        monkeypatch.undo()

        after = (
            session.execute(text("SELECT COUNT(*) FROM merchant_binding_group")).scalar(),
            session.execute(text("SELECT COUNT(*) FROM merchant_binding_member")).scalar(),
        )
        assert after == (before[0] + 1, before[1] + 2), (before, after)
        assert session.execute(
            text("SELECT COUNT(*) FROM merchant_binding_group WHERE created_by = :u"), {"u": username}
        ).scalar() == 0, "被回滚的组行不得残留(半写)"
        assert session.execute(
            text("SELECT COUNT(*) FROM merchant_binding_member WHERE merchant_id = :a"), {"a": a}
        ).scalar() == 0, "被回滚的成员行不得残留(半写)"
        assert session.execute(
            text("SELECT COUNT(*) FROM merchant_binding_member WHERE merchant_id = :b AND active_key = 1"),
            {"b": b},
        ).scalar() == 1, "并发赢家的绑定必须完好"
        conflicts = [r.getMessage() for r in caplog.records if "绑定并发冲突" in r.getMessage()]
        assert conflicts and "已被并发绑到其它组" in conflicts[0], conflicts
    finally:
        _cleanup_admin(session, username)


def test_unbound_account_group_resolution_and_projection_unchanged(client, session):
    """用例 22:未绑定账号 —— 组解析回退 [自己];progress 四字段与改造前口径一致(只有自己)。"""
    merchant_id = _temp_merchant(session)
    assert resolve_group_merchant_ids(session, merchant_id) == [merchant_id]
    data = _progress(client, merchant_id)
    assert set(data) == {"completedTasks", "stage2_unlocked", "data_center_unlocked",
                         "phase1_remaining_task_ids"}
    assert data["completedTasks"] == []
    assert data["stage2_unlocked"] is False
    assert data["data_center_unlocked"] is False
    assert len(data["phase1_remaining_task_ids"]) > 0
