"""管理端商家列表 / 进度 / 一键解锁回归(P1 权限)。

真源:app/api/v1/admin_merchant.py。
口径:
- 全部接口需管理员 token;商家 token(另一 secret)-> 401;
- 列表:分页边界(page_size 上限 100、page 下限 1)与返回结构;
- 一键解锁:需 super_admin/admin,viewer -> 403;商家不存在 -> 404;幂等;
  生效后 current_stage -> shop_setup 且 merchant_stage_progress 落 2 行。
- 列表筛选(#PB-24):stage/status 只接受已登记取值,非法 -> 400;空串 = 不筛选;
  可与 keyword/分页 AND 组合;total 为筛选后行数,投影为 9 字段(含 status,#PB-25)。

隔离:临时管理员与临时商家,finally 全部清理。
"""

import uuid

from sqlalchemy import text

from app.core.error_handlers import VALIDATION_MESSAGE
from app.core.security import create_merchant_token, hash_password
from tests.conftest import cleanup_temp_merchant, make_temp_merchant

ADMIN_PASSWORD = "Test@12345"


def _admin_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _merchant_headers(merchant_id: str) -> dict:
    return {"Authorization": f"Bearer {create_merchant_token(merchant_id)}"}


def _make_admin(session, role: str):
    """按角色建临时管理员(conftest.make_temp_admin 固定 role=admin,这里需要 super_admin/viewer)。"""
    username = f"_test_{role}_" + uuid.uuid4().hex[:8]
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


def _make_merchant(session, stage: str = "onboarding") -> str:
    merchant_id = "_test_adminops_" + uuid.uuid4().hex[:8]
    session.execute(
        text("INSERT INTO merchant (merchant_id, nickname, current_stage, status) VALUES (:m, '_test 商家', :s, 1)"),
        {"m": merchant_id, "s": stage},
    )
    session.commit()
    return merchant_id


def _cleanup_merchant(session, merchant_id: str) -> None:
    session.execute(text("DELETE FROM merchant_stage_progress WHERE merchant_id = :m"), {"m": merchant_id})
    session.execute(text("DELETE FROM merchant_task_progress WHERE merchantId = :m"), {"m": merchant_id})
    session.execute(text("DELETE FROM merchant WHERE merchant_id = :m"), {"m": merchant_id})
    session.commit()


def test_admin_merchant_endpoints_require_admin_token(client):
    """无 token -> 401;商家 token -> 401(双 secret 隔离)。"""
    paths = [
        ("GET", "/api/admin/merchant", None),
        ("GET", "/api/admin/merchant/progress?merchantId=x", None),
        ("POST", "/api/admin/merchant/x/unlock-phase1", None),
    ]
    for method, path, payload in paths:
        resp = client.request(method, path, json=payload)
        assert resp.status_code == 401, (method, path, resp.status_code)

    merchant_h = _merchant_headers("mock_merchant_001")
    for method, path, payload in paths:
        resp = client.request(method, path, headers=merchant_h, json=payload)
        assert resp.status_code == 401, (method, path, resp.status_code, resp.text)


def test_admin_merchant_list_shape_and_pagination_bounds(client, session):
    """列表结构 + 分页边界:page_size=101 被夹到 100,page=0 被夹到 1。"""
    username = _make_admin(session, "admin")
    try:
        token = _login(client, username)

        ok = client.get("/api/admin/merchant", params={"page": 1, "page_size": 20}, headers=_admin_headers(token))
        assert ok.status_code == 200, ok.text
        data = ok.json()["data"]
        assert set(("list", "total", "page", "page_size")) <= set(data)
        assert isinstance(data["list"], list)
        assert data["page"] == 1 and data["page_size"] == 20

        clamped = client.get("/api/admin/merchant", params={"page": 0, "page_size": 101}, headers=_admin_headers(token))
        assert clamped.status_code == 200, clamped.text
        assert clamped.json()["data"]["page_size"] == 100
        assert clamped.json()["data"]["page"] == 1
    finally:
        _cleanup_admin(session, username)


def test_unlock_phase1_requires_super_admin_or_admin(client, session):
    """viewer 角色 -> 403;admin 角色 -> 成功。"""
    viewer = _make_admin(session, "viewer")
    admin = _make_admin(session, "admin")
    merchant_id = _make_merchant(session, stage="onboarding")
    try:
        viewer_token = _login(client, viewer)
        denied = client.post(
            f"/api/admin/merchant/{merchant_id}/unlock-phase1", headers=_admin_headers(viewer_token)
        )
        assert denied.status_code == 403, denied.text
        assert denied.json()["code"] == 403

        admin_token = _login(client, admin)
        allowed = client.post(
            f"/api/admin/merchant/{merchant_id}/unlock-phase1", headers=_admin_headers(admin_token)
        )
        assert allowed.status_code == 201, allowed.text
        assert allowed.json()["data"] == {"success": True, "stage2_unlocked": True}
    finally:
        _cleanup_merchant(session, merchant_id)
        _cleanup_admin(session, viewer)
        _cleanup_admin(session, admin)


def test_unlock_phase1_effects_and_idempotency(client, session):
    """解锁生效:current_stage -> shop_setup + stage_progress 2 行;重复调用幂等。"""
    admin = _make_admin(session, "admin")
    merchant_id = _make_merchant(session, stage="onboarding")
    try:
        token = _login(client, admin)
        first = client.post(f"/api/admin/merchant/{merchant_id}/unlock-phase1", headers=_admin_headers(token))
        assert first.status_code == 201, first.text

        session.commit()
        stage = session.execute(
            text("SELECT current_stage FROM merchant WHERE merchant_id = :m"), {"m": merchant_id}
        ).scalar()
        assert stage == "shop_setup", f"current_stage 未更新: {stage}"

        rows = session.execute(
            text("SELECT stage_id, status FROM merchant_stage_progress WHERE merchant_id = :m ORDER BY stage_id"),
            {"m": merchant_id},
        ).mappings().all()
        assert {(r["stage_id"], r["status"]) for r in rows} == {("onboarding", "completed"), ("shop_setup", "unlocked")}, rows

        second = client.post(f"/api/admin/merchant/{merchant_id}/unlock-phase1", headers=_admin_headers(token))
        assert second.status_code == 201, second.text
        session.commit()
        count = session.execute(
            text("SELECT COUNT(*) FROM merchant_stage_progress WHERE merchant_id = :m"), {"m": merchant_id}
        ).scalar()
        assert count == 2, f"重复解锁产生了重复行: {count}"
    finally:
        _cleanup_merchant(session, merchant_id)
        _cleanup_admin(session, admin)


def test_unlock_phase1_unknown_merchant_404(client, session):
    """商家不存在 -> 404(不自动创建)。"""
    admin = _make_admin(session, "admin")
    try:
        token = _login(client, admin)
        resp = client.post(
            "/api/admin/merchant/_test_not_exist_xyz/unlock-phase1", headers=_admin_headers(token)
        )
        assert resp.status_code == 404, resp.text
        assert resp.json()["message"] == "该商家不存在"
    finally:
        _cleanup_admin(session, admin)


# ===== #PB-24:阶段/状态筛选(管理后台「商家清单」页) =====
# 口径(真源 §5.2 API-17):stage ∈ {onboarding, shop_setup}、status ∈ {0, 1, 2};未登记 -> 400;
# 空串/纯空白 = 不筛选;与 keyword/分页 AND 组合;total 为筛选后行数,投影为 9 字段(含 status)。
# 造数按铁律 5:复用 conftest 助手,先记 id 再删(cleanup_temp_merchant 覆盖 6 张 shop_* + 2 张进度表)。

# 管理端商家列表投影的**完整键集**(9 键;含 status = #PB-25 补齐前端「状态」列):
# 断言用「恰好等于」而非「包含」,任何字段增减都必须同步真源 §5.2 API-17 并更新此处。
EXPECTED_LIST_FIELDS = frozenset({
    "merchant_id", "nickname", "merchant_name", "current_stage", "status",
    "jd_merchant_id", "shop_name", "last_login_at", "created_at",
})


def _count_merchants(session, where_sql: str = "1 = 1", params=None) -> int:
    """同库独立对账计数(deleted_at IS NULL):用于断言 total 与筛选条件一致(不依赖真实数据分布)。"""
    return session.execute(
        text("SELECT COUNT(*) FROM merchant WHERE deleted_at IS NULL AND " + where_sql),
        params or {},
    ).scalar()


def _db_status(session, merchant_id: str) -> int:
    """回读库内 merchant.status,与投影字段逐条对账(#PB-25)。"""
    return session.execute(
        text("SELECT status FROM merchant WHERE merchant_id = :m"), {"m": merchant_id}
    ).scalar()


def _list_page(client, token: str, **params) -> dict:
    """取一页列表(page_size=100 保证单页装下筛选结果),返回 data。"""
    resp = client.get(
        "/api/admin/merchant", params={"page_size": 100, **params}, headers=_admin_headers(token)
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def test_admin_merchant_list_filters_by_stage(client, session):
    """stage 精确筛选:各阶段只返回本阶段行;total 与同库计数一致;空串 = 不筛选。"""
    admin = _make_admin(session, "admin")
    onboarding_id = make_temp_merchant(session, current_stage="onboarding")
    shop_setup_id = make_temp_merchant(session, current_stage="shop_setup")
    try:
        token = _login(client, admin)
        for stage, mine, other in (("onboarding", onboarding_id, shop_setup_id),
                                   ("shop_setup", shop_setup_id, onboarding_id)):
            data = _list_page(client, token, stage=stage)
            assert data["total"] == _count_merchants(session, "current_stage = :s", {"s": stage}), data["total"]
            assert data["total"] >= 1, stage
            assert all(r["current_stage"] == stage for r in data["list"]), data["list"]
            ids = {r["merchant_id"] for r in data["list"]}
            assert mine in ids and other not in ids, (stage, mine, other)
            assert len(data["list"]) == min(100, data["total"])
            assert set(data["list"][0]) == EXPECTED_LIST_FIELDS, set(data["list"][0])
        # 空串 = 不筛选(前端「全部」选项),且筛选确实比全量窄
        blank = _list_page(client, token, stage="")
        assert blank["total"] == _count_merchants(session)
        assert blank["total"] >= _list_page(client, token, stage="onboarding")["total"]
    finally:
        cleanup_temp_merchant(session, onboarding_id)
        cleanup_temp_merchant(session, shop_setup_id)
        _cleanup_admin(session, admin)


def test_admin_merchant_list_filters_by_status(client, session):
    """status 精确筛选:0 禁用 / 1 正常 / 2 已退出 各自只命中本状态行;投影 status 与库内逐条一致(#PB-25)。"""
    admin = _make_admin(session, "admin")
    disabled_id = make_temp_merchant(session, current_stage="onboarding", status=0)
    normal_id = make_temp_merchant(session, current_stage="onboarding", status=1)
    exited_id = make_temp_merchant(session, current_stage="shop_setup", status=2)
    try:
        token = _login(client, admin)
        for value, mine, other in ((0, disabled_id, exited_id),
                                   (1, normal_id, disabled_id),
                                   (2, exited_id, disabled_id)):
            data = _list_page(client, token, status=value)
            assert data["total"] == _count_merchants(session, "status = :v", {"v": value}), (value, data["total"])
            assert data["total"] >= 1, value
            assert all(r["status"] == value for r in data["list"]), (value, data["list"])
            ids = {r["merchant_id"] for r in data["list"]}
            assert mine in ids and other not in ids, (value, mine, other)
        assert _list_page(client, token, status="")["total"] == _count_merchants(session)
        # 三种状态逐条回读:投影 status == 库内 status,且键集恰为 9 键(#PB-25)
        for merchant_id, expected in ((disabled_id, 0), (normal_id, 1), (exited_id, 2)):
            data = _list_page(client, token, keyword=merchant_id)
            assert data["total"] == 1 and len(data["list"]) == 1, data
            row = data["list"][0]
            assert row["status"] == expected == _db_status(session, merchant_id), (merchant_id, row)
            assert set(row) == EXPECTED_LIST_FIELDS, set(row)
    finally:
        cleanup_temp_merchant(session, disabled_id)
        cleanup_temp_merchant(session, normal_id)
        cleanup_temp_merchant(session, exited_id)
        _cleanup_admin(session, admin)


def test_admin_merchant_list_filters_combine_with_keyword(client, session):
    """stage + status + keyword 三条件 AND:全中 -> 1 行;任一不符 -> 0 行(证明不是 OR/被忽略)。"""
    admin = _make_admin(session, "admin")
    target = make_temp_merchant(session, current_stage="onboarding", status=2)
    try:
        token = _login(client, admin)
        hit = _list_page(client, token, keyword=target, stage="onboarding", status=2)
        assert hit["total"] == 1 and [r["merchant_id"] for r in hit["list"]] == [target], hit
        assert hit["total"] < _count_merchants(session)
        miss_status = _list_page(client, token, keyword=target, stage="onboarding", status=1)
        assert miss_status["total"] == 0 and miss_status["list"] == [], miss_status
        miss_stage = _list_page(client, token, keyword=target, stage="shop_setup", status=2)
        assert miss_stage["total"] == 0 and miss_stage["list"] == [], miss_stage
    finally:
        cleanup_temp_merchant(session, target)
        _cleanup_admin(session, admin)


def test_admin_merchant_list_rejects_unregistered_filter_values(client, session, caplog):
    """未登记取值 -> 400 + 统一校验文案(不回显取值原文);排障细节只进日志;不返回任何行。"""
    admin = _make_admin(session, "admin")
    try:
        token = _login(client, admin)
        headers = _admin_headers(token)
        for params in ({"stage": "xxx"}, {"stage": "phase-1"}, {"status": "9"},
                       {"status": "-1"}, {"status": "abc"}, {"status": "1.5"}):
            resp = client.get("/api/admin/merchant", params=params, headers=headers)
            assert resp.status_code == 400, (params, resp.status_code, resp.text)
            body = resp.json()
            assert body["code"] == 400, (params, body)
            assert body["message"] == VALIDATION_MESSAGE, (params, body)
            assert body["data"] is None, (params, body)
            assert "xxx" not in body["message"] and "phase-1" not in body["message"]
        # 合法 + 非法组合:校验先于取数,同样 400
        mixed = client.get("/api/admin/merchant", params={"stage": "xxx", "status": "1"}, headers=headers)
        assert mixed.status_code == 400, mixed.text
        # 排障信息不丢:取值与已登记集合进日志(用户可见响应不含)
        assert any("筛选参数非法" in r.getMessage() for r in caplog.records), caplog.text
    finally:
        _cleanup_admin(session, admin)
