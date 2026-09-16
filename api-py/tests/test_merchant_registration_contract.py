"""商家登记契约回归(P1 数据)。

真源:project/docs/后端技术方案.md §5.2 登记接口 + services/merchant.py _normalize_registration。
正确性口径:
- 三态语义:字段缺省(未传)不更新;null/空串 -> 清空;非空串 -> 覆盖;
- 格式:京麦商家ID 仅数字、店铺名称 仅汉字,违规 400 且文案不回显用户输入;
- 长度上界由 DTO 承载(≤64 / ≤128),超长 400。

隔离:临时商家(make_temp_merchant)+ finally 清理。
"""

from sqlalchemy import text

from app.core.security import create_merchant_token
from tests.conftest import cleanup_temp_merchant, make_temp_merchant

PATH = "/api/merchant/registration"


def _headers(merchant_id: str) -> dict:
    return {"Authorization": f"Bearer {create_merchant_token(merchant_id)}"}


def _row(session, merchant_id):
    session.commit()
    return session.execute(
        text("SELECT jd_merchant_id, shop_name FROM merchant WHERE merchant_id = :m"),
        {"m": merchant_id},
    ).mappings().first()


def test_registration_absent_field_does_not_update(client, session):
    """缺省字段不更新:传空对象后,原值保持不变。"""
    merchant_id = make_temp_merchant(session)
    try:
        session.execute(
            text("UPDATE merchant SET jd_merchant_id = '123456', shop_name = '测试店铺' WHERE merchant_id = :m"),
            {"m": merchant_id},
        )
        session.commit()

        resp = client.put(PATH, headers=_headers(merchant_id), json={})
        assert resp.status_code == 200, resp.text
        row = _row(session, merchant_id)
        assert row["jd_merchant_id"] == "123456"
        assert row["shop_name"] == "测试店铺"
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_registration_null_clears_field(client, session):
    """null -> 清空该字段。"""
    merchant_id = make_temp_merchant(session)
    try:
        session.execute(
            text("UPDATE merchant SET jd_merchant_id = '123456', shop_name = '测试店铺' WHERE merchant_id = :m"),
            {"m": merchant_id},
        )
        session.commit()

        resp = client.put(PATH, headers=_headers(merchant_id), json={"jd_merchant_id": None})
        assert resp.status_code == 200, resp.text
        row = _row(session, merchant_id)
        assert row["jd_merchant_id"] is None
        assert row["shop_name"] == "测试店铺", "未传字段不应被清空"
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_registration_empty_string_clears_field(client, session):
    """空串与 null 同义(表单未填即空串):清空而非 400。"""
    merchant_id = make_temp_merchant(session)
    try:
        session.execute(
            text("UPDATE merchant SET shop_name = '测试店铺' WHERE merchant_id = :m"), {"m": merchant_id}
        )
        session.commit()

        resp = client.put(PATH, headers=_headers(merchant_id), json={"shop_name": ""})
        assert resp.status_code == 200, resp.text
        assert _row(session, merchant_id)["shop_name"] is None
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_registration_valid_values_overwrite(client, session):
    """合法值覆盖:商家ID 数字、店铺名汉字。"""
    merchant_id = make_temp_merchant(session)
    try:
        resp = client.put(
            PATH, headers=_headers(merchant_id), json={"jd_merchant_id": "987654321", "shop_name": "美好二手店"}
        )
        assert resp.status_code == 200, resp.text
        row = _row(session, merchant_id)
        assert row["jd_merchant_id"] == "987654321"
        assert row["shop_name"] == "美好二手店"
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_registration_rejects_non_digit_merchant_id(client, session):
    """商家ID 含字母 -> 400,且不落库。"""
    merchant_id = make_temp_merchant(session)
    try:
        resp = client.put(PATH, headers=_headers(merchant_id), json={"jd_merchant_id": "abc123"})
        assert resp.status_code == 400, resp.text
        assert resp.json()["message"] == "京麦商家ID仅支持数字"
        assert _row(session, merchant_id)["jd_merchant_id"] is None
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_registration_rejects_non_chinese_shop_name(client, session):
    """店铺名含非汉字 -> 400,且不落库。"""
    merchant_id = make_temp_merchant(session)
    try:
        resp = client.put(PATH, headers=_headers(merchant_id), json={"shop_name": "shop2026"})
        assert resp.status_code == 400, resp.text
        assert resp.json()["message"] == "店铺名称仅支持汉字"
        assert _row(session, merchant_id)["shop_name"] is None
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_registration_length_boundary(client, session):
    """长度上界:商家ID 64 位通过 / 65 位 400;店铺名 128 汉字通过 / 129 汉字 400。"""
    merchant_id = make_temp_merchant(session)
    try:
        ok = client.put(
            PATH,
            headers=_headers(merchant_id),
            json={"jd_merchant_id": "9" * 64, "shop_name": "店" * 128},
        )
        assert ok.status_code == 200, ok.text

        too_long_id = client.put(PATH, headers=_headers(merchant_id), json={"jd_merchant_id": "9" * 65})
        assert too_long_id.status_code == 400, too_long_id.text

        too_long_name = client.put(PATH, headers=_headers(merchant_id), json={"shop_name": "店" * 129})
        assert too_long_name.status_code == 400, too_long_name.text
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_registration_requires_merchant_token(client):
    """无 token -> 401。"""
    resp = client.put(PATH, json={"shop_name": "测试店铺"})
    assert resp.status_code == 401, resp.text
