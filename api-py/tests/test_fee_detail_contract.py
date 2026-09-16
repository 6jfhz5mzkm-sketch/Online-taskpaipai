"""资费查询契约回归(P0 资金口径)。

真源:project/docs/后端技术方案.md §5.2 API-06 /fee/detail 与 §6.3 类目资费查询规则。
正确性口径(不只 200):
- operation_rate / transaction_rate 输出为两位小数字符串;
- 品牌特殊资费优先于基础资费,且**只覆盖费率**;
- 四档保证金始终取基础资费(fee_brand_override 不存保证金);
- 未知/非法 category_id -> 404;缺参 -> 400;无 token -> 401。

隔离:读路径复用种子 fee_config;品牌覆盖用例插入 _test_ 前缀临时行,finally 删除。
"""

import uuid
from decimal import Decimal

from sqlalchemy import text

from app.core.security import create_merchant_token

PATH = "/api/fee/detail"


def _headers(merchant_id: str = "mock_merchant_001") -> dict:
    return {"Authorization": f"Bearer {create_merchant_token(merchant_id)}"}


def _base_config(session):
    """取一条启用的种子基础资费(只读)。"""
    session.commit()
    row = session.execute(
        text(
            "SELECT category_id, operation_rate, transaction_rate, deposit_gmv_lt_5w, "
            "deposit_gmv_5w_10w, deposit_gmv_10w_30w, deposit_gmv_gte_30w "
            "FROM fee_config WHERE is_active = 1 ORDER BY category_id LIMIT 1"
        )
    ).mappings().first()
    assert row is not None, "种子 fee_config 缺失,无法验证基础资费口径"
    return row


def _fmt(value) -> str:
    """接口口径:两位小数字符串。"""
    return f"{Decimal(str(value)):.2f}"


def test_fee_detail_base_rates_and_deposits(client, session):
    """无品牌:费率=基础配置(两位小数字符串),四档保证金=基础配置,is_brand_override 为假。"""
    cfg = _base_config(session)
    cid = int(cfg["category_id"])

    resp = client.get(PATH, params={"category_id": str(cid)}, headers=_headers())
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["category_id"] == cid
    assert data["brand_name"] is None
    assert data["operation_rate"] == _fmt(cfg["operation_rate"])
    assert data["transaction_rate"] == _fmt(cfg["transaction_rate"])
    assert data["deposit_gmv_lt_5w"] == int(cfg["deposit_gmv_lt_5w"])
    assert data["deposit_gmv_5w_10w"] == int(cfg["deposit_gmv_5w_10w"])
    assert data["deposit_gmv_10w_30w"] == int(cfg["deposit_gmv_10w_30w"])
    assert data["deposit_gmv_gte_30w"] == int(cfg["deposit_gmv_gte_30w"])
    assert data["is_brand_override"] is False


def test_fee_detail_brand_override_only_overrides_rates(client, session):
    """有品牌覆盖:费率取覆盖值,保证金仍取基础值,is_brand_override 为真。"""
    cfg = _base_config(session)
    cid = int(cfg["category_id"])
    brand = "_test_brand_" + uuid.uuid4().hex[:8]

    session.execute(
        text(
            "INSERT INTO fee_brand_override (category_id, brand_name, operation_rate, transaction_rate, is_active) "
            "VALUES (:c, :b, :o, :t, 1)"
        ),
        {"c": cid, "b": brand, "o": Decimal("1.23"), "t": Decimal("4.56")},
    )
    session.commit()
    try:
        resp = client.get(PATH, params={"category_id": str(cid), "brand_name": brand}, headers=_headers())
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]

        assert data["brand_name"] == brand
        assert data["is_brand_override"] is True
        assert data["operation_rate"] == "1.23"
        assert data["transaction_rate"] == "4.56"
        # 保证金必须仍来自基础资费
        assert data["deposit_gmv_lt_5w"] == int(cfg["deposit_gmv_lt_5w"])
        assert data["deposit_gmv_gte_30w"] == int(cfg["deposit_gmv_gte_30w"])
    finally:
        session.execute(
            text("DELETE FROM fee_brand_override WHERE category_id = :c AND brand_name = :b"),
            {"c": cid, "b": brand},
        )
        session.commit()


def test_fee_detail_brand_without_override_falls_back_to_base(client, session):
    """品牌存在但无覆盖:回落基础费率,is_brand_override 为假。"""
    cfg = _base_config(session)
    cid = int(cfg["category_id"])
    brand = "_test_nobrand_" + uuid.uuid4().hex[:8]

    resp = client.get(PATH, params={"category_id": str(cid), "brand_name": brand}, headers=_headers())
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["is_brand_override"] is False
    assert data["operation_rate"] == _fmt(cfg["operation_rate"])
    assert data["brand_name"] == brand


def test_fee_detail_unknown_category_404(client):
    """不存在的类目 -> 404 该类目暂无资费信息。"""
    resp = client.get(PATH, params={"category_id": "900719925474099"}, headers=_headers())
    assert resp.status_code == 404, resp.text
    assert resp.json() == {"code": 404, "message": "该类目暂无资费信息", "data": None}


def test_fee_detail_non_numeric_category_id_404(client):
    """非法 category_id(0/负数/非数字/科学计数/空串)-> 归 0 -> 404,不得 500。"""
    for raw in ("0", "-1", "abc", "1e3", ""):
        resp = client.get(PATH, params={"category_id": raw}, headers=_headers())
        assert resp.status_code == 404, (raw, resp.status_code, resp.text)


def test_fee_detail_missing_category_id_400(client):
    """缺 category_id -> 400(参数校验),不是 500。"""
    resp = client.get(PATH, headers=_headers())
    assert resp.status_code == 400, resp.text
    assert resp.json()["code"] == 400


def test_fee_detail_requires_merchant_token(client):
    """无 token -> 401。"""
    resp = client.get(PATH, params={"category_id": "1"})
    assert resp.status_code == 401, resp.text
    assert resp.json()["code"] == 401
