"""店铺数据聚合(summary)数值类型契约回归:与 NestJS TypeORM decimal -> string 对齐。

背景:修复前仅 star/health_score 走 _dec 字符串化,trade/traffic/product 的 DECIMAL 字段
直接透传 Decimal,经 jsonable_encoder 变 JSON number(实测 trade_amount=1000.5);而 NestJS
同列为 TypeORM decimal -> string(如 "1000.50"),同一响应内 star 与 trade 类型语义分裂。

真源:project/scripts/schema.sql 的 DECIMAL 列(shop_trade_data/shop_traffic_data/shop_product_data
全部 scale=2,shop_star_data scale=1,shop_health_score.avg_score scale=2);
基准:backend/src/modules/shop/entities/*.entity.ts(TypeORM decimal 列)。
隔离:临时商家 + raw SQL 造数,finally 清理 5 张 shop_* 表。
"""

import uuid

from sqlalchemy import Float, String, text

from app.core.security import create_merchant_token
from app.db.models.shop_health_score import ShopHealthScore
from app.db.models.shop_product_data import ShopProductData
from app.db.models.shop_star_data import ShopStarData
from app.db.models.shop_trade_data import ShopTradeData
from app.db.models.shop_traffic_data import ShopTrafficData
from app.services.shop import DECIMAL_SCALES

from tests.conftest import cleanup_temp_merchant, make_temp_merchant

_TABLES = ("shop_star_data", "shop_trade_data", "shop_traffic_data", "shop_product_data", "shop_health_score")


def _headers(merchant_id: str) -> dict:
    return {"Authorization": f"Bearer {create_merchant_token(merchant_id)}"}


def _float_columns(model) -> set:
    return {c.name for c in model.__table__.columns if isinstance(c.type, Float)}


def _decimal_columns_declared_as_string(model) -> set:
    """star/health_score 模型的 DECIMAL 列被声明为 String(16)(既有漂移,PB-1 已上报),按列名排除非数值列。"""
    skip = {"merchant_id", "data_date"}
    return {c.name for c in model.__table__.columns if isinstance(c.type, String) and c.name not in skip}


def test_decimal_scales_cover_all_decimal_columns():
    """序列化规格必须覆盖全部 DECIMAL 列(新增 decimal 字段忘记登记时立即失败)。"""
    assert _float_columns(ShopTradeData) == set(DECIMAL_SCALES["trade"])
    assert _float_columns(ShopTrafficData) == set(DECIMAL_SCALES["traffic"])
    assert _float_columns(ShopProductData) == set(DECIMAL_SCALES["product"])
    assert _decimal_columns_declared_as_string(ShopStarData) == set(DECIMAL_SCALES["star"])
    assert _decimal_columns_declared_as_string(ShopHealthScore) == set(DECIMAL_SCALES["health_score"])


def test_summary_decimal_fields_are_strings(client, session):
    """DECIMAL 字段统一输出字符串(固定小数位);INT 字段保持 number;未上传字段为 null。"""
    merchant_id = make_temp_merchant(session)
    try:
        session.execute(text(
            "INSERT INTO shop_trade_data (merchant_id, data_date, time_range, trade_amount, conversion_rate, trade_orders, customer_unit_price) "
            "VALUES (:m, '2026-09-01', '7d', 1000.50, 3.2, 5, -12.30)"), {"m": merchant_id})
        session.execute(text(
            "INSERT INTO shop_traffic_data (merchant_id, data_date, time_range, uv_value, trade_amount, shop_visitors) "
            "VALUES (:m, '2026-09-01', '7d', 12.3, 1000.50, 88)"), {"m": merchant_id})
        session.execute(text(
            "INSERT INTO shop_product_data (merchant_id, data_date, time_range, spu_active_rate, cart_amount, trade_items) "
            "VALUES (:m, '2026-09-01', '7d', 66.67, 0, 7)"), {"m": merchant_id})
        session.execute(text(
            "INSERT INTO shop_star_data (merchant_id, data_date, shop_star, service_score) VALUES (:m, '2026-09-01', 4.5, 9.25)"),
            {"m": merchant_id})
        session.execute(text(
            "INSERT INTO shop_health_score (merchant_id, data_date, avg_score) VALUES (:m, '2026-09-01', 95.5)"),
            {"m": merchant_id})
        session.commit()

        resp = client.get("/api/shop/summary", params={"time_range": "7d"}, headers=_headers(merchant_id))
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]

        # DECIMAL -> string(列 scale 固定小数位)
        assert data["trade"]["trade_amount"] == "1000.50"
        assert data["trade"]["conversion_rate"] == "3.20"
        assert data["trade"]["customer_unit_price"] == "-12.30"      # 负数
        assert data["traffic"]["uv_value"] == "12.30"
        assert data["traffic"]["trade_amount"] == "1000.50"
        assert data["product"]["spu_active_rate"] == "66.67"
        assert data["product"]["cart_amount"] == "0.00"              # 0
        assert data["star"]["shop_star"] == "4.5"                    # scale=1
        assert data["star"]["service_score"] == "9.3"                # 9.25 按列 scale=1 存储
        assert data["health_score"]["avg_score"] == "95.50"

        # 未上传字段 -> null(不伪造 0)
        assert data["trade"]["cart_conversion_rate"] is None
        assert data["star"]["logistics_score"] is None

        # INT 列保持 number(与 NestJS int 列一致)
        assert data["trade"]["trade_orders"] == 5
        assert data["traffic"]["shop_visitors"] == 88
        assert data["product"]["trade_items"] == 7

        # 类型语义一致:同响应内 4 组的 DECIMAL 字段必须都是字符串
        for group in ("star", "trade", "traffic", "product"):
            for key in DECIMAL_SCALES[group]:
                value = data[group][key]
                assert isinstance(value, (str, type(None))), (group, key, value, type(value).__name__)
    finally:
        for table in _TABLES:
            session.execute(text("DELETE FROM " + table + " WHERE merchant_id = :m"), {"m": merchant_id})
        session.commit()
        cleanup_temp_merchant(session, merchant_id)
