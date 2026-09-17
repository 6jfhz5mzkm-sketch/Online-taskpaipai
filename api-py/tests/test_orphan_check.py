"""商家标识列孤儿巡检纯函数回归(#DB-15;候选表含驼峰列 #T-20-R4)。

被测:api-py/scripts/check_orphan.py 的 aggregate_rows / exemption_of / classify / summarize /
camel_summary / verdict_of(纯函数,不连库),以及结构性断言:
- 「只读硬约束」:SQL_* 常量必须全部为 SELECT;
- 「单一真源」:候选表来自 scripts/merchant_scope.py,脚本内不得再有第二份清单/窄口径 SQL;
- 「列名参数化」:三条按列过滤的 SQL 模板必须带 {column}(兼容 merchant_id / merchantId)。

覆盖:NULL 不算孤儿 / 策略豁免命中 / 存量登记命中 / 未登记孤儿被识别 / 已登记存量不报 exit 1 /
跨表汇总与退出码 / 驼峰表汇总与纳入判定 / 脚本内不存在写语句。
"""

import importlib.util
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_orphan.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("check_orphan", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


orphan = _load_script_module()


def test_null_merchant_id_is_not_an_orphan():
    """merchant_id IS NULL 不计孤儿:聚合阶段直接丢弃,只可能出现在 null_mid 统计里。"""
    grouped = orphan.aggregate_rows([(None, 159), ("mock_merchant_001", 5)])
    assert set(grouped) == {"mock_merchant_001"}
    outcome = orphan.classify("event_log", list(grouped.values()))
    assert outcome["rows"] == 5
    assert outcome["unregistered_rows"] == 5  # 真实的未登记孤儿(仅用于断言聚合不吞行)
    assert orphan.aggregate_rows([(None, 1)]) == {}


def test_policy_exemption_hit():
    """策略豁免:feishu_notification.merchant_id = 'system' 属已登记(非商家键)。"""
    hit = orphan.exemption_of("feishu_notification", "system")
    assert hit is not None and hit["kind"] == "policy"
    assert hit["registered_at"] and hit["reason"] and hit["removal_condition"]
    outcome = orphan.classify("feishu_notification", [{"merchant_id": "system", "row_count": 6, "sample_ids": [1, 2]}])
    assert outcome["registered_rows"] == 6 and outcome["unregistered_rows"] == 0
    assert orphan.verdict_of(outcome["unregistered_rows"]) == ("PASS", 0)


def test_stock_registration_hit_and_non_hit():
    """存量登记:ai_analysis_log 的 mock_* 命中;其它前缀不命中(防豁免面被悄悄扩大)。"""
    hit = orphan.exemption_of("ai_analysis_log", "mock_merchant_020")
    assert hit is not None and hit["kind"] == "stock"
    assert hit["expected_rows"] == 40
    assert orphan.exemption_of("ai_analysis_log", "real_merchant_001") is None
    assert orphan.exemption_of("merchant_stage_progress", "mock_merchant_020") is None


def test_unregistered_orphan_is_reported_and_fails():
    """未登记孤儿必须被识别,并让门禁 exit 1。"""
    outcome = orphan.classify("merchant_stage_progress", [
        {"merchant_id": "mock_merchant_nonexist_999", "row_count": 2, "sample_ids": [14785, 14786]},
        {"merchant_id": "mock_merchant_nonexist_777", "row_count": 2, "sample_ids": [14791, 14792]},
    ])
    assert outcome["unregistered_rows"] == 4 and outcome["registered_rows"] == 0
    assert [e["merchant_id"] for e in outcome["unregistered"]] == ["mock_merchant_nonexist_999",
                                                                 "mock_merchant_nonexist_777"]
    assert orphan.verdict_of(outcome["unregistered_rows"]) == ("FAIL", 1)


def test_registered_stock_does_not_fail_the_gate():
    """已登记存量(40 行 mock_*)不得触发 exit 1 —— 这正是登记制的意义。"""
    entries = [{"merchant_id": "mock_merchant_0%02d" % i, "row_count": 1, "sample_ids": []} for i in range(40)]
    outcome = orphan.classify("ai_analysis_log", entries)
    assert outcome["registered_rows"] == 40 and outcome["unregistered_rows"] == 0
    assert outcome["rows"] == 40
    assert orphan.verdict_of(outcome["unregistered_rows"]) == ("PASS", 0)


def test_summarize_and_verdict_across_tables():
    """跨表汇总:已登记 + 未登记 分开计,退出码只看未登记。"""
    table_results = {
        "feishu_notification": {"rows": 6, "registered_rows": 6, "unregistered_rows": 0},
        "ai_analysis_log": {"rows": 40, "registered_rows": 40, "unregistered_rows": 0},
    }
    totals = orphan.summarize(table_results)
    assert totals == {"orphan_rows": 46, "registered_rows": 46, "unregistered_rows": 0}
    assert orphan.verdict_of(totals["unregistered_rows"]) == ("PASS", 0)
    table_results["merchant_stage_progress"] = {"rows": 4, "registered_rows": 0, "unregistered_rows": 4}
    totals = orphan.summarize(table_results)
    assert totals["orphan_rows"] == 50 and totals["unregistered_rows"] == 4
    assert orphan.verdict_of(totals["unregistered_rows"]) == ("FAIL", 1)


@pytest.mark.parametrize("name", ["POLICY_EXEMPTIONS", "STOCK_REGISTRATIONS"])
def test_registrations_carry_reason_date_and_removal_condition(name):
    """登记制豁免的每一项都必须带「理由 + 登记日期 + 移除条件」,禁止空放行开关。"""
    table = getattr(orphan, name)
    assert table, name + " 不得为空"
    for key, info in table.items():
        assert info.get("reason"), key
        assert info.get("registered_at"), key
        assert info.get("removal_condition"), key


def test_script_contains_only_select_statements():
    """只读硬约束:脚本内所有 SQL_* 常量必须是 SELECT(杜绝 DELETE/UPDATE/DROP/ALTER/TRUNCATE/INSERT)。"""
    sql_constants = {n: v for n, v in vars(orphan).items() if n.startswith("SQL_") and isinstance(v, str)}
    assert sql_constants, "未找到 SQL_* 常量"
    for name, sql in sql_constants.items():
        assert sql.strip().upper().startswith("SELECT"), name + " 不是 SELECT: " + sql[:60]


# ===== #T-20-R4:camelCase 列(merchant_task_progress.merchantId)纳入候选表 =====


def test_sql_templates_are_column_parameterized():
    """按列过滤的三条 SQL 必须带 {column} —— 否则驼峰表会退回按 merchant_id 过滤(查出 0 行而假绿)。"""
    for name in ("SQL_TABLE_NULL_MID", "SQL_ORPHAN_GROUPS", "SQL_ORPHAN_SAMPLE_IDS"):
        sql = getattr(orphan, name)
        assert "{column}" in sql, name + " 未参数化列名: " + sql[:80]


def test_scope_uses_single_source_of_truth():
    """候选表必须来自 merchant_scope 单一真源;旧的「巡检仅 merchant_id」窄口径 SQL 必须已废止。"""
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "discover_merchant_scope" in source, "未复用 merchant_scope 的发现实现"
    assert "COLUMN_NAME = 'merchant_id'" not in source.replace("'merchant_id','merchantId'", ""), \
        "仍存在巡检专用窄口径 SQL(COLUMN_NAME = 'merchant_id')"
    assert "discover_orphan_scope_tables" not in source, "仍引用已废止的 discover_orphan_scope_tables"
    assert not hasattr(orphan, "SQL_ORPHAN_SCOPE_TABLES"), "窄口径 SQL 常量应已删除"


def test_camel_summary_counts_camel_tables_and_orphans():
    """camel_summary 只统计驼峰表(列名 != merchant_id),不影响其它表的汇总。"""
    results = {
        "event_log": {"column": "merchant_id", "rows": 5, "registered_rows": 0, "unregistered_rows": 5},
        "merchant_task_progress": {"column": "merchantId", "rows": 2, "registered_rows": 0,
                                   "unregistered_rows": 2},
    }
    assert orphan.camel_summary(results) == {"camel_tables_scanned": 1, "camel_orphan_rows": 2}


def test_camel_orphan_is_included_and_fails_the_gate():
    """驼峰孤儿必须计入 unregistered_rows 并触发 exit 1 —— 纳入而非旁路(#T-20-R4 的核心)。"""
    results = {"merchant_task_progress": {"column": "merchantId", "rows": 3, "registered_rows": 0,
                                          "unregistered_rows": 3}}
    totals = orphan.summarize(results)
    assert totals == {"orphan_rows": 3, "registered_rows": 0, "unregistered_rows": 3}
    assert orphan.verdict_of(totals["unregistered_rows"]) == ("FAIL", 1)
    assert orphan.camel_summary(results)["camel_orphan_rows"] == 3


def test_non_camel_tables_are_not_counted_as_camel():
    """对照:全部是 merchant_id 表时 camel_tables_scanned / camel_orphan_rows 均为 0。"""
    results = {"event_log": {"column": "merchant_id", "rows": 7, "registered_rows": 7,
                             "unregistered_rows": 0}}
    assert orphan.camel_summary(results) == {"camel_tables_scanned": 0, "camel_orphan_rows": 0}
