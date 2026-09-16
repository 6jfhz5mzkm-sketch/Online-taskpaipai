"""清除店铺数据范围回归(P0 数据·破坏性接口)。

真源:POST /api/shop/clear-data 语义(services/shop.py clear_merchant_data 文档字符串)。
正确性口径(破坏性接口必须逐项锁定范围):
- 6 张 shop_* 表该商家的行被删除,cleared 计数与预置行数一致;
- merchant_task_progress 中 T2.5.% 的 completed 被重置为 pending(reset_tasks > 0);
- ai_analysis_log **保留**(不清);
- merchant.data_center_unlocked **保留**(不改);
- 其它商家的数据不受影响。

隔离:临时商家 + 显式清理 ai_analysis_log / 进度行。
"""

from sqlalchemy import text

from app.core.security import create_merchant_token
from tests.conftest import cleanup_temp_merchant, make_temp_merchant

SHOP_TABLES = (
    "shop_star_data", "shop_trade_data", "shop_traffic_data",
    "shop_product_data", "shop_product_count", "shop_health_score",
)


def _headers(merchant_id: str) -> dict:
    return {"Authorization": f"Bearer {create_merchant_token(merchant_id)}"}


def _count(session, table: str, merchant_id: str) -> int:
    session.commit()
    return int(session.execute(
        text(f"SELECT COUNT(*) FROM {table} WHERE merchant_id = :m"), {"m": merchant_id}
    ).scalar())


def _cleanup_extra(session, merchant_id: str) -> None:
    for table in SHOP_TABLES:
        session.execute(text(f"DELETE FROM {table} WHERE merchant_id = :m"), {"m": merchant_id})
    session.execute(text("DELETE FROM ai_analysis_log WHERE merchant_id = :m"), {"m": merchant_id})
    session.execute(text("DELETE FROM merchant_task_progress WHERE merchantId = :m"), {"m": merchant_id})
    session.commit()


def test_clear_data_scope_is_exact(client, session):
    """清除范围:shop_* 清空 + T2.5 重置,但 AI 日志与数据专区解锁保留。"""
    merchant_id = make_temp_merchant(session)
    other_id = make_temp_merchant(session)
    try:
        # 预置:1 行星级数据(走接口)
        resp = client.post(
            "/api/shop/star", headers=_headers(merchant_id),
            json={"shopStar": 4.5, "dataDate": "2026-08-05"},
        )
        assert resp.status_code == 201, resp.text
        # 预置:另一商家的星级数据(必须不受影响)
        resp_other = client.post(
            "/api/shop/star", headers=_headers(other_id),
            json={"shopStar": 3.0, "dataDate": "2026-08-05"},
        )
        assert resp_other.status_code == 201, resp_other.text

        session.execute(
            text("INSERT INTO ai_analysis_log (merchant_id, type, status) VALUES (:m, 'analysis', 'success')"),
            {"m": merchant_id},
        )
        session.execute(
            text("INSERT INTO merchant_task_progress (merchantId, taskId, status) VALUES (:m, 'T2.5.1', 'completed')"),
            {"m": merchant_id},
        )
        session.execute(
            text("UPDATE merchant SET data_center_unlocked = 1 WHERE merchant_id = :m"), {"m": merchant_id}
        )
        session.commit()

        resp = client.post("/api/shop/clear-data", headers=_headers(merchant_id))
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["success"] is True
        assert data["cleared"]["star"] == 1, f"cleared 计数不正确: {data['cleared']}"
        assert data["reset_tasks"] >= 1, f"T2.5 未重置: {data['reset_tasks']}"

        # 6 张表该商家清空
        for table in SHOP_TABLES:
            assert _count(session, table, merchant_id) == 0, f"{table} 未清空"
        # 另一商家数据保留
        assert _count(session, "shop_star_data", other_id) == 1, "误删了其它商家的数据"
        # AI 日志保留
        assert _count(session, "ai_analysis_log", merchant_id) == 1, "AI 日志被误删"
        # 数据专区解锁保留
        session.commit()
        unlocked = session.execute(
            text("SELECT data_center_unlocked FROM merchant WHERE merchant_id = :m"), {"m": merchant_id}
        ).scalar()
        assert int(unlocked) == 1, "数据专区解锁被误清"
        # T2.5 进度重置为 pending
        status = session.execute(
            text("SELECT status FROM merchant_task_progress WHERE merchantId = :m AND taskId = 'T2.5.1'"),
            {"m": merchant_id},
        ).scalar()
        assert status == "pending", f"T2.5 进度未重置: {status}"
    finally:
        _cleanup_extra(session, merchant_id)
        cleanup_temp_merchant(session, merchant_id)
        cleanup_temp_merchant(session, other_id)


def test_clear_data_requires_merchant_token(client):
    """无 token -> 401。"""
    resp = client.post("/api/shop/clear-data")
    assert resp.status_code == 401, resp.text


def test_clear_data_is_idempotent(client, session):
    """重复清除:第二次 cleared 计数为 0,不报错。"""
    merchant_id = make_temp_merchant(session)
    try:
        client.post("/api/shop/star", headers=_headers(merchant_id),
                    json={"shopStar": 4.5, "dataDate": "2026-08-05"})
        first = client.post("/api/shop/clear-data", headers=_headers(merchant_id))
        assert first.status_code == 201, first.text
        assert first.json()["data"]["cleared"]["star"] == 1

        second = client.post("/api/shop/clear-data", headers=_headers(merchant_id))
        assert second.status_code == 201, second.text
        assert second.json()["data"]["cleared"]["star"] == 0
    finally:
        _cleanup_extra(session, merchant_id)
        cleanup_temp_merchant(session, merchant_id)
