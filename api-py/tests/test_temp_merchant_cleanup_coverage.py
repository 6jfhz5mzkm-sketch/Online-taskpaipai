"""临时商家清理助手覆盖范围的反漂移回归（#T-20-R1 / 缺陷 D1）。

被测：`tests/conftest.py::cleanup_temp_merchant` 的覆盖范围 + `scripts/merchant_scope.py` 的发现口径。

背景（#T-20 实测）：旧实现硬编码 9 张表（6 张 shop_* + merchant_stage_progress +
merchant_task_progress + merchant），**漏 `event_log`**（页面浏览/登录前埋点）⇒「前端端到端 +
临时商家」验收收尾必然留下未登记孤儿、`ORPHAN_GATE` 变红（与铁律 5 记载的 #PB-24-3 同坑第二次）。

**为什么期望值不取自被测模块**：真值直接来自 `information_schema`
（列名 ∈ {`merchant_id`, `merchantId`}）。一旦覆盖范围被改回硬编码清单，本组用例立即变红并
逐个列出缺失的「表.列」，而不是"实现与期望一起退化"。
"""

import uuid

from sqlalchemy import text

from scripts.merchant_scope import discover_merchant_scope
from tests.conftest import cleanup_temp_merchant, make_temp_merchant

# 真值口径：与被测实现无关的独立查询（两种列名拼写）
TRUTH_SCOPE_SQL = (
    "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS "
    "WHERE TABLE_SCHEMA = DATABASE() AND COLUMN_NAME IN ('merchant_id', 'merchantId')"
)

# 旧硬编码清单（缺陷现场）：仅用于"防退化"断言，不得作为覆盖范围来源
LEGACY_HARDCODED_SCOPE = {
    "shop_star_data", "shop_trade_data", "shop_traffic_data", "shop_product_data",
    "shop_product_count", "shop_health_score", "merchant_stage_progress",
    "merchant_task_progress", "merchant",
}


def _truth_scope(session):
    return {(str(r[0]), str(r[1])) for r in session.execute(text(TRUTH_SCOPE_SQL)).fetchall()}


def _count(session, sql, params):
    session.commit()  # REPEATABLE READ 下先结束当前快照,确保读到其它事务的提交
    return int(session.execute(text(sql), params).scalar())


def test_cleanup_scope_covers_every_merchant_identifier_table(session):
    """清理覆盖集合 ⊇ information_schema 发现的商家标识表集合；缺失时逐表列出。"""
    truth = _truth_scope(session)
    covered = set(discover_merchant_scope(session))
    missing = sorted("%s.%s" % (table, column) for table, column in (truth - covered))
    assert not missing, (
        "cleanup_temp_merchant 的覆盖范围缺少 %d 张含商家标识的表/列：%s（覆盖 %d / 真值 %d）"
        % (len(missing), ", ".join(missing), len(covered), len(truth))
    )


def test_cleanup_scope_covers_camel_case_column(session):
    """`merchant_task_progress` 用驼峰 `merchantId` —— 只按 merchant_id 发现会漏掉它。"""
    covered = set(discover_merchant_scope(session))
    assert ("merchant_task_progress", "merchantId") in covered


def test_cleanup_scope_is_dynamic_not_a_frozen_whitelist(session):
    """防退化：覆盖范围必须**严格多于**旧硬编码清单，且本次踩坑的 event_log 在扩展出来的部分里。"""
    covered = {table for table, _ in discover_merchant_scope(session)}
    extra = sorted(covered - LEGACY_HARDCODED_SCOPE)
    assert extra, "覆盖范围与旧硬编码清单完全一致，动态发现未生效"
    assert "event_log" in extra, "event_log 未被动态发现覆盖（#T-20 D1 的缺陷点）"


def test_cleanup_removes_event_log_rows_and_keeps_null_rows(session):
    """行为级：清理必须删掉该商家的 event_log 行，且**不得**触碰 merchant_id IS NULL 的行。"""
    mid = make_temp_merchant(session)
    null_marker = "t20r1-null-probe-" + uuid.uuid4().hex[:8]
    try:
        session.execute(
            text("INSERT INTO event_log (merchant_id, event_type, page_name) VALUES (:m, 'page_view', :p)"),
            {"m": mid, "p": "t20-r1-probe"},
        )
        session.execute(
            text("INSERT INTO event_log (merchant_id, event_type, page_name) VALUES (NULL, 'page_view', :p)"),
            {"p": null_marker},
        )
        session.commit()

        assert _count(session, "SELECT COUNT(*) FROM event_log WHERE merchant_id = :m", {"m": mid}) == 1
        assert _count(session, "SELECT COUNT(*) FROM event_log WHERE page_name = :p", {"p": null_marker}) == 1

        cleanup_temp_merchant(session, mid)

        assert _count(session, "SELECT COUNT(*) FROM event_log WHERE merchant_id = :m", {"m": mid}) == 0, \
            "event_log 未被清理（D1 未修复）"
        assert _count(session, "SELECT COUNT(*) FROM merchant WHERE merchant_id = :m", {"m": mid}) == 0, \
            "merchant 主表未被清理"
        assert _count(session, "SELECT COUNT(*) FROM event_log WHERE page_name = :p", {"p": null_marker}) == 1, \
            "误删了 merchant_id IS NULL 的行（登录前埋点）"

        cleanup_temp_merchant(session, mid)  # 幂等：重复清理不得报错
    finally:
        session.execute(text("DELETE FROM event_log WHERE page_name = :p"), {"p": null_marker})
        session.execute(text("DELETE FROM event_log WHERE merchant_id = :m"), {"m": mid})
        session.execute(text("DELETE FROM merchant WHERE merchant_id = :m"), {"m": mid})
        session.commit()
