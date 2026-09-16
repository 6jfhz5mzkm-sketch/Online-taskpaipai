"""商标查询关键词防御回归(B1)+ 商标表 ORM 唯一约束对齐(M5)。

B1 背景:修复前 search() 只做 trim 不校验空值,且把 % / _ 直接拼进 LIKE:
  - keyword="   " -> LIKE '%%%' 匹配全表(limit 50),返回与关键词无关的数据;
  - keyword="%"   -> 通配符未转义,同样匹配全表。
修复后:trim 后为空返回 400;% / _ / \\ 转义为字面匹配;查询语义与分页行为不变(LIKE %kw%、brand_name ASC、limit 50)。

M5 背景:docstring 与真源 project/scripts/schema.sql 的 UNIQUE KEY uk_brand_number
(brand_name, registration_number),但 ORM 未声明 -> alembic autogenerate 会出 schema diff。

隔离:临时商家(make_temp_merchant)+ 临时商标记录("A%" 前缀 + uuid,finally 删除)。
"""

import uuid

from sqlalchemy import UniqueConstraint, text

from app.core.security import create_merchant_token
from app.db.models.trademark_registry import TrademarkRegistry

from tests.conftest import cleanup_temp_merchant, make_temp_merchant

_TASK_PREFIX = "_test_tm_"


def _headers(merchant_id: str) -> dict:
    return {"Authorization": f"Bearer {create_merchant_token(merchant_id)}"}


def test_trademark_registry_unique_constraint_matches_schema():
    """M5:ORM 必须声明 (brand_name, registration_number) 唯一约束(与 schema.sql 的 uk_brand_number 对齐)。"""
    unique_sets = {
        tuple(sorted(c.name for c in uc.columns))
        for uc in TrademarkRegistry.__table__.constraints
        if isinstance(uc, UniqueConstraint)
    }
    assert ("brand_name", "registration_number") in unique_sets


def test_blank_keyword_rejected(client, session):
    """B1:纯空白关键词不再生成空 LIKE 匹配全表,返回 400。"""
    merchant_id = make_temp_merchant(session)
    try:
        for keyword in ("   ", "\t "):
            resp = client.get("/api/trademark/search", params={"keyword": keyword}, headers=_headers(merchant_id))
            assert resp.status_code == 400, resp.text
            assert resp.json()["code"] == 400
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_like_wildcards_are_escaped(client, session):
    """B1:% / _ 按字面匹配,不再当通配符(修复前搜 "%" 会命中全表)。"""
    merchant_id = make_temp_merchant(session)
    suffix = uuid.uuid4().hex[:8]
    percent_brand = "A%" + suffix
    underscore_brand = "A_" + suffix
    plain_brand = "AB" + suffix
    rows = [(percent_brand, "1001"), (underscore_brand, "1002"), (plain_brand, "1003")]
    try:
        for brand, number in rows:
            session.execute(
                text("INSERT INTO trademark_registry (brand_name, registration_number) VALUES (:b, :n)"),
                {"b": brand, "n": number},
            )
        session.commit()

        # "%" 只应命中字面含 % 的品牌
        resp = client.get("/api/trademark/search", params={"keyword": "%"}, headers=_headers(merchant_id))
        assert resp.status_code == 200, resp.text
        names = [r["brand_name"] for r in resp.json()["data"]]
        assert percent_brand in names
        assert plain_brand not in names
        assert underscore_brand not in names

        # "_" 只应命中字面含 _ 的品牌
        resp = client.get("/api/trademark/search", params={"keyword": "_"}, headers=_headers(merchant_id))
        names = [r["brand_name"] for r in resp.json()["data"]]
        assert underscore_brand in names
        assert plain_brand not in names

        # 正常关键词语义不变(前缀 A + 后缀精确片段)
        resp = client.get("/api/trademark/search", params={"keyword": plain_brand}, headers=_headers(merchant_id))
        names = [r["brand_name"] for r in resp.json()["data"]]
        assert names == [plain_brand]
    finally:
        for brand, _ in rows:
            session.execute(text("DELETE FROM trademark_registry WHERE brand_name = :b"), {"b": brand})
        session.commit()
        cleanup_temp_merchant(session, merchant_id)
