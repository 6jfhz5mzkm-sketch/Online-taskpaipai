"""埋点统计守卫回归(P1 数据)。

真源:API-11 /api/event/stats —— 管理员 JWT、日期范围 ≤90 天、group_by ∈ {day, week}。
口径:
- 无 token / 商家 token -> 401;
- 日期格式非法 -> 400;end < start -> 400;跨度 90 天通过 / 91 天 400;
- group_by 非白名单 -> 400;
- 正常查询返回 {date_range, summary, trend, page_distribution, task_stats} 结构。

隔离:只读统计,不写库;临时管理员 finally 清理。
"""

from sqlalchemy import text

from app.core.security import create_merchant_token
from tests.conftest import cleanup_temp_admin, make_temp_admin

PATH = "/api/event/stats"


def _admin_token(client, session):
    username, password = make_temp_admin(session)
    resp = client.post("/api/admin/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return username, resp.json()["data"]["token"]


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_event_stats_requires_admin_token(client):
    """无 token -> 401。"""
    resp = client.get(PATH, params={"start_date": "2026-08-01", "end_date": "2026-08-07"})
    assert resp.status_code == 401, resp.text


def test_event_stats_rejects_merchant_token(client):
    """商家 token 用另一个 secret -> 401。"""
    headers = {"Authorization": f"Bearer {create_merchant_token('mock_merchant_001')}"}
    resp = client.get(PATH, params={"start_date": "2026-08-01", "end_date": "2026-08-07"}, headers=headers)
    assert resp.status_code == 401, resp.text


def test_event_stats_span_boundary(client, session):
    """跨度边界:恰好 90 天通过;91 天 400。"""
    username, token = _admin_token(client, session)
    try:
        ok = client.get(PATH, params={"start_date": "2026-06-01", "end_date": "2026-08-30"}, headers=_h(token))
        assert ok.status_code == 200, ok.text

        too_long = client.get(PATH, params={"start_date": "2026-05-31", "end_date": "2026-08-30"}, headers=_h(token))
        assert too_long.status_code == 400, too_long.text
        assert too_long.json()["message"] == "查询范围不能超过90天"
    finally:
        cleanup_temp_admin(session, username)


def test_event_stats_rejects_reversed_range(client, session):
    """end_date 早于 start_date -> 400。"""
    username, token = _admin_token(client, session)
    try:
        resp = client.get(PATH, params={"start_date": "2026-08-10", "end_date": "2026-08-01"}, headers=_h(token))
        assert resp.status_code == 400, resp.text
    finally:
        cleanup_temp_admin(session, username)


def test_event_stats_rejects_bad_date_format(client, session):
    """日期格式非法 -> 400。"""
    username, token = _admin_token(client, session)
    try:
        resp = client.get(PATH, params={"start_date": "2026-13-01", "end_date": "2026-13-05"}, headers=_h(token))
        assert resp.status_code == 400, resp.text
        assert resp.json()["message"] == "日期格式不合法"
    finally:
        cleanup_temp_admin(session, username)


def test_event_stats_group_by_whitelist(client, session):
    """group_by 只允许 day/week;month -> 400。"""
    username, token = _admin_token(client, session)
    try:
        ok = client.get(PATH, params={"start_date": "2026-08-01", "end_date": "2026-08-07", "group_by": "day"}, headers=_h(token))
        assert ok.status_code == 200, ok.text

        bad = client.get(PATH, params={"start_date": "2026-08-01", "end_date": "2026-08-07", "group_by": "month"}, headers=_h(token))
        assert bad.status_code == 400, bad.text
    finally:
        cleanup_temp_admin(session, username)


def test_event_stats_response_shape(client, session):
    """正常查询:返回结构完整,分母为 0 时完成率为 0(不是 None/NaN)。"""
    username, token = _admin_token(client, session)
    try:
        resp = client.get(PATH, params={"start_date": "2000-01-01", "end_date": "2000-01-07"}, headers=_h(token))
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["date_range"] == {"start_date": "2000-01-01", "end_date": "2000-01-07"}
        assert set(("pv", "uv", "task_complete_count", "task_complete_rate")) <= set(data["summary"])
        assert isinstance(data["trend"], list)
        assert isinstance(data["page_distribution"], list)
        assert isinstance(data["task_stats"], list)
        assert data["summary"]["task_complete_rate"] == 0
    finally:
        cleanup_temp_admin(session, username)
