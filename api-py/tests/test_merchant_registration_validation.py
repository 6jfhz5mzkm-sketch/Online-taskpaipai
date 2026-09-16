"""商家登记字段格式校验回归(#PB-23)。

真源:project/docs/后端技术方案.md §5.2 API-20(PUT/GET /api/merchant/registration)。
用户裁决(2026-09-14):京麦商家ID 仅数字、店铺名称 仅汉字;null/空串 = 清空(回落「未登记」);
非法 -> 400 结构化错误且**不回显用户输入原文**;长度上界由 DTO 承载(≤64 / ≤128,与列一致)。
本文件同时守护既有语义:字段缺省不更新、幂等覆盖、GET 预填形状不变、单字段保存可用。

隔离:全程使用临时商家(make_temp_merchant)+ finally 按 merchant_id 删除;不触碰任何既有商家行的登记值。
"""

from sqlalchemy import text

from app.core.error_handlers import VALIDATION_MESSAGE
from app.core.security import create_merchant_token
from tests.conftest import cleanup_temp_merchant, make_temp_merchant

PATH = "/api/merchant/registration"
VALID_ID = "88123456789"
VALID_NAME = "拍拍二手手机专营店"
LONG_ID = "9" * 65        # 列上界 VARCHAR(64)
LONG_NAME = "店" * 129     # 列上界 VARCHAR(128)


def _headers(merchant_id: str) -> dict:
    return {"Authorization": f"Bearer {create_merchant_token(merchant_id)}"}


def _row(session, merchant_id: str):
    """当前已提交的登记值(先结束本会话只读事务:REPEATABLE READ 下否则看到旧快照)。"""
    session.commit()
    row = session.execute(
        text("SELECT jd_merchant_id, shop_name FROM merchant WHERE merchant_id = :m"),
        {"m": merchant_id},
    ).mappings().first()
    return None if row is None else (row["jd_merchant_id"], row["shop_name"])


def test_valid_values_saved_and_prefilled(client, session):
    """合法值 200 落库;GET 预填语义不回归(形状与值不变)。"""
    merchant_id = make_temp_merchant(session)
    try:
        resp = client.put(PATH, headers=_headers(merchant_id),
                          json={"jd_merchant_id": VALID_ID, "shop_name": VALID_NAME})
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"code": 0, "message": "success", "data": {"success": True}}
        assert _row(session, merchant_id) == (VALID_ID, VALID_NAME)

        got = client.get(PATH, headers=_headers(merchant_id))
        assert got.status_code == 200, got.text
        assert got.json()["data"] == {"jd_merchant_id": VALID_ID, "shop_name": VALID_NAME}
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_invalid_merchant_id_rejected(client, session):
    """ID 含字母/空格/汉字/符号/全角数字 -> 400,且不回显原文、不落库。"""
    merchant_id = make_temp_merchant(session)
    try:
        for bad in ("8812A3", "881 23", "八八一二三", "8812-3", "8812.3", "８８１２", " 8812", "8812 "):
            resp = client.put(PATH, headers=_headers(merchant_id), json={"jd_merchant_id": bad})
            assert resp.status_code == 400, (bad, resp.status_code, resp.text)
            body = resp.json()
            assert (body["code"], body["message"], body["data"]) == (400, "京麦商家ID仅支持数字", None)
            assert bad not in resp.text, resp.text          # 不回显用户输入原文
        assert _row(session, merchant_id) == (None, None)   # 非法输入一律未落库
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_invalid_shop_name_rejected(client, session):
    """店名含数字/字母/空格/符号 -> 400,且不回显原文、不落库。"""
    merchant_id = make_temp_merchant(session)
    try:
        for bad in ("旗舰店1", "旗舰店A", "旗舰 店", "旗舰-店", "旗舰店！", "拍拍&二手"):
            resp = client.put(PATH, headers=_headers(merchant_id), json={"shop_name": bad})
            assert resp.status_code == 400, (bad, resp.status_code, resp.text)
            body = resp.json()
            assert (body["code"], body["message"], body["data"]) == (400, "店铺名称仅支持汉字", None)
            assert bad not in resp.text, resp.text
        assert _row(session, merchant_id) == (None, None)
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_null_clears_values(client, session):
    """null = 清空(回落「未登记」),必须放行。"""
    merchant_id = make_temp_merchant(session)
    try:
        assert client.put(PATH, headers=_headers(merchant_id),
                          json={"jd_merchant_id": VALID_ID, "shop_name": VALID_NAME}).status_code == 200
        resp = client.put(PATH, headers=_headers(merchant_id),
                          json={"jd_merchant_id": None, "shop_name": None})
        assert resp.status_code == 200, resp.text
        assert _row(session, merchant_id) == (None, None)
        assert client.get(PATH, headers=_headers(merchant_id)).json()["data"] == {
            "jd_merchant_id": None, "shop_name": None}
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_empty_string_means_clear_not_error(client, session):
    """空串与 null 同义(清空):表单未填时前端提交的就是空串,不能因此 400。"""
    merchant_id = make_temp_merchant(session)
    try:
        client.put(PATH, headers=_headers(merchant_id),
                   json={"jd_merchant_id": VALID_ID, "shop_name": VALID_NAME})
        resp = client.put(PATH, headers=_headers(merchant_id), json={"jd_merchant_id": "", "shop_name": ""})
        assert resp.status_code == 200, resp.text
        assert _row(session, merchant_id) == (None, None)
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_single_field_save_still_works(client, session):
    """#F-25 之前的老前端总是同时提交两个字段(未填的那个是空串):只填一项仍须保存成功。"""
    merchant_id = make_temp_merchant(session)
    try:
        resp = client.put(PATH, headers=_headers(merchant_id),
                          json={"jd_merchant_id": VALID_ID, "shop_name": ""})
        assert resp.status_code == 200, resp.text
        assert _row(session, merchant_id) == (VALID_ID, None)
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_over_length_rejected(client, session):
    """超长 -> 400(DTO 层上界与列一致),同样不回显原文与英文字段名(#PB-24-1-R1)。"""
    merchant_id = make_temp_merchant(session)
    try:
        id_resp = client.put(PATH, headers=_headers(merchant_id), json={"jd_merchant_id": LONG_ID})
        assert id_resp.status_code == 400, id_resp.text
        assert id_resp.json()["message"] == VALIDATION_MESSAGE
        assert "jd_merchant_id" not in id_resp.json()["message"]   # #PB-24-1-R1:英文字段名不再回显
        assert LONG_ID not in id_resp.text

        name_resp = client.put(PATH, headers=_headers(merchant_id), json={"shop_name": LONG_NAME})
        assert name_resp.status_code == 400, name_resp.text
        assert name_resp.json()["message"] == VALIDATION_MESSAGE
        assert "shop_name" not in name_resp.json()["message"]   # #PB-24-1-R1:英文字段名不再回显
        assert LONG_NAME not in name_resp.text

        assert _row(session, merchant_id) == (None, None)
        # 边界内(恰好等于列上界)必须放行
        ok = client.put(PATH, headers=_headers(merchant_id),
                        json={"jd_merchant_id": "9" * 64, "shop_name": "店" * 128})
        assert ok.status_code == 200, ok.text
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_omitted_field_not_modified_and_idempotent(client, session):
    """缺省字段不更新;重复提交同一合法值幂等。"""
    merchant_id = make_temp_merchant(session)
    try:
        client.put(PATH, headers=_headers(merchant_id),
                   json={"jd_merchant_id": VALID_ID, "shop_name": VALID_NAME})
        assert client.put(PATH, headers=_headers(merchant_id), json={}).status_code == 200
        assert _row(session, merchant_id) == (VALID_ID, VALID_NAME)

        for _ in range(2):
            resp = client.put(PATH, headers=_headers(merchant_id), json={"jd_merchant_id": "123456"})
            assert resp.status_code == 200, resp.text
        assert _row(session, merchant_id) == ("123456", VALID_NAME)
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_requires_merchant_token(client):
    """无 token -> 401(鉴权边界不变)。"""
    resp = client.put(PATH, json={"jd_merchant_id": VALID_ID})
    assert resp.status_code == 401, resp.text
