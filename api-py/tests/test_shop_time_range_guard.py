"""数据看板 `time_range` 入参守卫(#PB-30)。

背景:真源 §5.2 API-14 记「`time_range` 枚举 `yesterday/7d/30d`,非法 400」,但实现无校验(传 `abc` 也 200)
(`GET /api/shop/summary`);`POST /api/shop/analysis` 同一语义的 400 文案是英文 NestJS 遗留
(`time_range must be one of the following values: ...`),违反真源 §4.3.1「用户可见文案一律中文」。
本用例锁死终态:两个入口共用同一中文专句常量(`app/services/shop.py::TIME_RANGE_INVALID_MESSAGE`),
`summary` 保留默认 `7d`,`analysis` 仍为必填;文案不得回显英文枚举原文。

隔离:仅创建/清理临时商家,不写任何 shop_* 业务数据;analysis 的非法入参在调用大模型**之前**即返回,不外呼。
"""
from app.core.security import create_merchant_token
from app.services.shop import TIME_RANGE_INVALID_MESSAGE, TIME_RANGE_VALUES

from tests.conftest import cleanup_temp_merchant, make_temp_merchant


def _headers(merchant_id: str) -> dict:
    return {"Authorization": f"Bearer {create_merchant_token(merchant_id)}"}


def test_summary_time_range_enum_and_default(client, session):
    """合法枚举 200;不传 → 默认 7d 200;非法 → 400 中文专句(不回显英文枚举)。"""
    merchant_id = make_temp_merchant(session)
    try:
        headers = _headers(merchant_id)
        for value in TIME_RANGE_VALUES:
            ok = client.get("/api/shop/summary", params={"time_range": value}, headers=headers)
            assert ok.status_code == 200, ok.text
            assert ok.json()["data"]["time_range"] == value

        default = client.get("/api/shop/summary", headers=headers)
        assert default.status_code == 200, default.text
        assert default.json()["data"]["time_range"] == "7d"

        bad = client.get("/api/shop/summary", params={"time_range": "abc"}, headers=headers)
        assert bad.status_code == 400, bad.text
        body = bad.json()
        assert body["code"] == 400 and body["data"] is None
        assert body["message"] == TIME_RANGE_INVALID_MESSAGE
        for english in ("yesterday", "7d", "30d"):
            assert english not in body["message"]
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_analysis_time_range_invalid_copy_is_chinese(client, session):
    """非法/缺失入参均 400,且与 /summary 完全同句(单一真源);不触达大模型。"""
    merchant_id = make_temp_merchant(session)
    try:
        headers = _headers(merchant_id)
        invalid = client.post("/api/shop/analysis", params={"time_range": "abc"}, headers=headers)
        assert invalid.status_code == 400, invalid.text
        assert invalid.json()["message"] == TIME_RANGE_INVALID_MESSAGE

        missing = client.post("/api/shop/analysis", headers=headers)
        assert missing.status_code == 400, missing.text      # 必填:不传同样 400(行为不变)
        assert missing.json()["message"] == TIME_RANGE_INVALID_MESSAGE
    finally:
        cleanup_temp_merchant(session, merchant_id)
