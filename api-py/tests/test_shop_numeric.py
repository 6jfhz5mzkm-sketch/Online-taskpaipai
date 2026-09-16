"""店铺数值解析/格式化回归测试(B4)。

背景:shop.py 的 _dec 原实现直接 f"{v:.Nf}";当传入 str 形态数值(如 '4.5')时抛
ValueError(Unknown format code 'f' for object of type 'str'),使 GET /api/shop/summary 500。
修复原则:数值解析收敛到唯一 owner parse_number,_to_num/_dec 只保留各自的失败策略。

隔离:纯函数用例零副作用;端到端用例使用临时商家,finally 清理 star 数据
(conftest.cleanup_temp_merchant 未覆盖 shop_star_data,故此处自行清理)。
"""

from decimal import Decimal

import pytest
from sqlalchemy import text

from app.core.security import create_merchant_token
from app.services.shop import NumberParseError, _dec, parse_number

from tests.conftest import cleanup_temp_merchant, make_temp_merchant


def _headers(merchant_id: str) -> dict:
    return {"Authorization": f"Bearer {create_merchant_token(merchant_id)}"}


# ---------- parse_number:数值解析唯一 owner ----------

def test_parse_number_normalizes_types():
    """类型归一与脏字符清理:None/空串 -> None,数值类型与字符串统一到 Decimal。"""
    assert parse_number(None) is None
    assert parse_number("") is None
    assert parse_number("   ") is None
    assert parse_number(5) == Decimal("5")
    assert parse_number(5.5) == Decimal("5.5")
    assert parse_number(Decimal("4.50")) == Decimal("4.50")
    assert parse_number("4.5") == Decimal("4.5")
    assert parse_number(" 4.5 ") == Decimal("4.5")
    assert parse_number("1,234.56") == Decimal("1234.56")   # ASCII 千分位
    assert parse_number("1，234") == Decimal("1234")         # 全角逗号
    assert parse_number("10%") == Decimal("10")              # 百分号


def test_parse_number_rejects_dirty_values():
    """非空且无法解析 -> 抛 NumberParseError(由调用方决定跳过或输出 null)。"""
    for dirty in ("abc", "约10万", "N/A", "-"):
        with pytest.raises(NumberParseError):
            parse_number(dirty)
    with pytest.raises(NumberParseError):
        parse_number(["4.5"])


# ---------- _dec:读路径格式化(原 B4 缺陷点) ----------

def test_dec_accepts_string_payloads():
    """str 形态取值(列被建成 VARCHAR / 驱动返回字符串)不再抛异常,输出与 DECIMAL 形态一致。"""
    assert _dec("4.5", 1) == "4.5"
    assert _dec("4.50", 2) == "4.50"
    assert _dec("95.50", 2) == "95.50"
    assert _dec("1,234.56", 1) == "1234.6"


def test_dec_accepts_numeric_payloads():
    assert _dec(Decimal("4.5"), 1) == "4.5"
    assert _dec(4.5, 1) == "4.5"
    assert _dec(5, 1) == "5.0"


def test_dec_empty_and_dirty_return_none():
    """空值与脏值输出 None(不抛异常),避免单条脏数据把 /api/shop/summary 打成 500。"""
    assert _dec(None, 1) is None
    assert _dec("", 1) is None
    assert _dec("   ", 1) is None
    assert _dec("abc", 1) is None
    assert _dec("N/A", 2) is None
    assert _dec(["4.5"], 1) is None


# ---------- 端到端:表单落库(str -> DECIMAL) -> summary 读取 ----------

def test_summary_star_read_path(client, session):
    """上传星级(服务层 str() 落库)后 GET /api/shop/summary 正常返回字符串形态数值。"""
    merchant_id = make_temp_merchant(session)
    try:
        up = client.post(
            "/api/shop/star",
            headers=_headers(merchant_id),
            json={"shopStar": 4.5, "serviceScore": 9.2, "dataDate": "2026-09-01"},
        )
        assert up.status_code == 201, up.text

        resp = client.get("/api/shop/summary", params={"time_range": "7d"}, headers=_headers(merchant_id))
        assert resp.status_code == 200, resp.text
        star = resp.json()["data"]["star"]
        assert star["shop_star"] == "4.5"
        assert star["service_score"] == "9.2"
        assert star["data_date"] == "2026-09-01"
    finally:
        session.execute(text("DELETE FROM shop_star_data WHERE merchant_id = :m"), {"m": merchant_id})
        session.commit()
        cleanup_temp_merchant(session, merchant_id)
