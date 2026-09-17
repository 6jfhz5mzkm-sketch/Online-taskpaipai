"""商家标识列孤儿巡检(只读登记,不删除;候选表含 camelCase 列,#T-20-R4)。

背景(#DB-14,2026-09-15,开发库 merchant_task 全库体检):本库**无外键约束**,删除商家不会连带清理子表,
孤儿只能靠体检发现。当时结论:ai_analysis_log 40 行孤儿(11 个 merchant_id 全为 mock_*,2026-08-20~27
开发期探针残留)、feishu_notification 6 行 merchant_id='system'(月度资费同步的运维发送审计记录,
设计使然)、其余 11 张表 0 行;event_log 的 merchant_id IS NULL 为登录前埋点,不算孤儿。

口径(唯一真源):
  1. 候选表**动态发现**:information_schema 中 COLUMN_NAME ∈ {'merchant_id','merchantId'} 的表
     (禁止硬编码表名清单;**单一真源 = scripts/merchant_scope.py::discover_merchant_scope**,与
     tests/conftest.py 的临时商家清理助手**共用同一集合**;当前库 16 张 = 15 张 merchant_id
     + 1 张驼峰 merchant_task_progress.merchantId)。驼峰列自 #T-20-R4 起纳入(用户 2026-09-16
     批准的门禁语义变更);驼峰表的孤儿同样计入未登记孤儿并触发 exit 1;
  2. 孤儿 = merchant_id IS NOT NULL 且该值不在 merchant.merchant_id 中;
  3. merchant_id IS NULL 单独统计为 null_mid,仅供参考,不参与判定;
  4. 登记制豁免:策略豁免(非商家键,设计使然)与存量登记(开发期探针残留)见下方常量,每项带
     理由 + 登记日期 + 移除条件;登记项只打印、不计入未登记孤儿;
  5. 退出码:0 无未登记孤儿 / 1 发现未登记孤儿(逐表列出 表名/merchant_id/行数/样例 id) /
     2 环境错误(DB 不可达、information_schema 读不到) —— 绝不静默跳过、绝不 exit 0。

⚠️ 本脚本**只登记、不删除**:脚本内不含任何 DELETE/UPDATE/DROP/ALTER/TRUNCATE/INSERT 语句,
   全部 SQL 仅 SELECT。清理孤儿必须走铁律 5 的「先按主键 id 记录并备份 → 按 id 精确删除 →
   前后计数校验」并要求用户批准(禁止按 merchant_id LIKE 'mock_%' 之类宽泛谓词删除)。

用法: cd api-py && uv run python scripts/check_orphan.py
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# 脚本可独立运行: 把 api-py 根加入 sys.path(与 scripts/check_schema.py 同风格)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

EXIT_OK = 0
EXIT_UNREGISTERED = 1
EXIT_ENV = 2

# ---- 登记制豁免: 每条必须带 理由 + 登记日期 + 移除条件(禁止写成空的放行开关) ----
POLICY_EXEMPTIONS: Dict[Tuple[str, str], Dict[str, Any]] = {
    ("feishu_notification", "system"): {
        "reason": "非商家键:运维自动化(月度资费同步 fee_sync)通知的接收方占位,不对应 merchant 行,设计使然",
        "registered_at": "2026-09-15",
        "removal_condition": "若 feishu_notification 改为只记录真实商家键(或为占位接收方另建类型/表),删除本项",
    },
}

STOCK_REGISTRATIONS: Dict[str, Dict[str, Any]] = {
    "ai_analysis_log": {
        "merchant_id_prefix": "mock_",
        "expected_rows": 40,
        "reason": "2026-08-20~27 AI 功能开发期探针残留:11 个 merchant_id 全为 mock_*,对应商家行已删(#DB-14 体检)",
        "registered_at": "2026-09-15",
        "removal_condition": "用户批准清理该批存量孤儿后删除本项;届时按 #DB-14 报告给出的 id 清单精确删除",
    },
}

# ---- 只读 SQL(全部 SELECT;测试会断言不存在写语句) ----
# 候选表发现口径的**单一真源** = scripts/merchant_scope.py(与 tests/conftest.py 的临时商家清理
# 助手共用**同一集合**:列名 ∈ {merchant_id, merchantId},当前库 16 张;#T-20-R4 起驼峰列已纳入,
# 两侧不再有任何口径差异)。
SQL_ID_COLUMN_DISCOVERY = (
    "SELECT TABLE_NAME FROM information_schema.COLUMNS "
    "WHERE TABLE_SCHEMA = DATABASE() AND COLUMN_NAME = 'id'"
)
SQL_TABLE_TOTAL = "SELECT COUNT(*) AS c FROM `{table}`"
# 列名由候选表发现结果提供(merchant_id / merchantId),故模板参数化 {column}(#T-20-R4)
SQL_TABLE_NULL_MID = "SELECT COUNT(*) AS c FROM `{table}` WHERE `{column}` IS NULL"
SQL_ORPHAN_GROUPS = (
    "SELECT x.`{column}` AS merchant_id, COUNT(*) AS row_count FROM `{table}` x "
    "LEFT JOIN merchant m ON m.merchant_id = x.`{column}` "
    "WHERE x.`{column}` IS NOT NULL AND m.id IS NULL GROUP BY x.`{column}` ORDER BY row_count DESC"
)
SQL_ORPHAN_SAMPLE_IDS = "SELECT id FROM `{table}` WHERE `{column}` = :mid ORDER BY id LIMIT {limit}"

# 非驼峰的默认列名;凡列名 != 此值的表即「驼峰表」,在人读输出中单独分组(#T-20-R4)
DEFAULT_MERCHANT_COLUMN = "merchant_id"


def aggregate_rows(rows: Sequence[Tuple[Optional[str], int]]) -> Dict[str, Dict[str, Any]]:
    """把 (merchant_id, 行数) 序列聚合成 {merchant_id: {row_count}};merchant_id 为 None 的一律忽略。"""
    grouped: Dict[str, Dict[str, Any]] = {}
    for merchant_id, row_count in rows:
        if merchant_id is None:
            continue
        grouped[merchant_id] = {"merchant_id": merchant_id, "row_count": int(row_count), "sample_ids": []}
    return grouped


def exemption_of(table: str, merchant_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """返回该 (表, merchant_id) 命中的登记项(策略豁免优先于存量登记);未命中返回 None。"""
    if merchant_id is None:
        return None
    policy = POLICY_EXEMPTIONS.get((table, merchant_id))
    if policy is not None:
        return {"kind": "policy", **policy}
    stock = STOCK_REGISTRATIONS.get(table)
    if stock is not None and merchant_id.startswith(stock.get("merchant_id_prefix", "")):
        return {"kind": "stock", **stock}
    return None


def classify(table: str, entries: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """把一张表的孤儿分组分成「已登记(豁免/存量)」与「未登记」,并统计行数。"""
    registered: List[Dict[str, Any]] = []
    unregistered: List[Dict[str, Any]] = []
    for entry in entries:
        hit = exemption_of(table, entry.get("merchant_id"))
        if hit is None:
            unregistered.append(dict(entry))
        else:
            registered.append({**entry, "exemption_kind": hit["kind"], "exemption": hit})
    return {
        "registered": registered,
        "unregistered": unregistered,
        "rows": sum(int(e["row_count"]) for e in entries),
        "registered_rows": sum(int(e["row_count"]) for e in registered),
        "unregistered_rows": sum(int(e["row_count"]) for e in unregistered),
    }


def summarize(table_results: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    """跨表汇总:orphan/registered/unregistered 行数。"""
    return {
        "orphan_rows": sum(r["rows"] for r in table_results.values()),
        "registered_rows": sum(r["registered_rows"] for r in table_results.values()),
        "unregistered_rows": sum(r["unregistered_rows"] for r in table_results.values()),
    }


def camel_summary(table_results: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    """驼峰表(列名 != DEFAULT_MERCHANT_COLUMN)的数量与孤儿行数(#T-20-R4)。

    仅用于门禁 JSON 的可观测字段与人读分组;**不参与** verdict 判定 —— 驼峰表的孤儿已在
    `summarize()` 中计入 `unregistered_rows`,与其它表同权(纳入而非旁路)。
    """
    camel_tables = {
        table: row for table, row in table_results.items()
        if row.get("column") != DEFAULT_MERCHANT_COLUMN
    }
    return {
        "camel_tables_scanned": len(camel_tables),
        "camel_orphan_rows": sum(int(row["rows"]) for row in camel_tables.values()),
    }


def verdict_of(unregistered_rows: int) -> Tuple[str, int]:
    """由「未登记孤儿行数」决定结果串与退出码。"""
    if unregistered_rows > 0:
        return "FAIL", EXIT_UNREGISTERED
    return "PASS", EXIT_OK


def _is_env_error(exc: BaseException) -> bool:
    """区分「环境不可达」(连接/网络/权限) 与「巡检本身失败」(SQL/结构异常);两者都 exit 2,但原因不同。"""
    from sqlalchemy import exc as sqlalchemy_exc

    env_types = (
        sqlalchemy_exc.OperationalError,
        sqlalchemy_exc.InterfaceError,
        sqlalchemy_exc.InternalError,
        ConnectionError,
        OSError,
    )
    return isinstance(exc, env_types)


def _print_gate(payload: Dict[str, Any]) -> None:
    print("ORPHAN_GATE " + json.dumps(payload, ensure_ascii=False))


def _read_scope(conn: Any) -> List[Tuple[str, str]]:
    """候选表发现:复用 scripts/merchant_scope.py 的**单一实现**(16 张,含驼峰列;#T-20-R4)。

    与 `tests/conftest.py::cleanup_temp_merchant` 的清理范围**同一集合** —— 不再有第二份清单,
    也不再保留「巡检仅 merchant_id」的窄口径。
    """
    from scripts.merchant_scope import discover_merchant_scope

    return discover_merchant_scope(conn)


def _scan_table(conn: Any, table: str, column: str, has_id: bool) -> Dict[str, Any]:
    from sqlalchemy import text

    total = conn.execute(text(SQL_TABLE_TOTAL.format(table=table))).scalar()
    null_mid = conn.execute(text(SQL_TABLE_NULL_MID.format(table=table, column=column))).scalar()
    groups = conn.execute(text(SQL_ORPHAN_GROUPS.format(table=table, column=column))).mappings().all()
    entries = aggregate_rows([(g["merchant_id"], g["row_count"]) for g in groups])
    for entry in entries.values():
        if has_id:
            rows = conn.execute(
                text(SQL_ORPHAN_SAMPLE_IDS.format(table=table, column=column, limit=5)),
                {"mid": entry["merchant_id"]},
            ).fetchall()
            entry["sample_ids"] = [r[0] for r in rows]
        else:
            entry["sample_ids"] = []
    outcome = classify(table, list(entries.values()))
    outcome.update({
        "table": table,
        "column": column,
        "total_rows": int(total or 0),
        "null_mid": int(null_mid or 0),
    })
    return outcome


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="merchant_id 孤儿巡检(只读登记,不删除)")
    parser.parse_args(argv)

    checked_at = datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        from sqlalchemy import text

        from app.core.config import get_settings
        from app.db.engine import engine

        settings = get_settings()
        target_db = settings.DB_NAME
        host, port = settings.DB_HOST, settings.DB_PORT
    except Exception as exc:  # noqa: BLE001 - 统一转结构化环境错误
        print("[ERROR] 配置或引擎初始化失败: " + type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        _print_gate({"result": "ERROR", "reason": "engine_unavailable", "checked_at": checked_at})
        return EXIT_ENV

    print("=== merchant_id 孤儿巡检(只读登记,不删除) ===")
    print("目标库: " + str(target_db) + " @ " + str(host) + ":" + str(port))
    print("检查时间: " + checked_at)
    try:
        with engine.connect() as conn:
            scope = _read_scope(conn)
            if not scope:
                raise RuntimeError("information_schema 未返回任何含商家标识列(merchant_id/merchantId)的表")
            id_tables = {row[0] for row in conn.execute(text(SQL_ID_COLUMN_DISCOVERY)).fetchall()}
            results = {t: _scan_table(conn, t, c, t in id_tables) for t, c in scope}
    except Exception as exc:  # noqa: BLE001 - DB 不可达/结构读取/查询失败一律 exit 2,绝不 exit 0
        reason = "database_unavailable" if _is_env_error(exc) else "inspection_failed"
        print("[ERROR] 实库不可达或 information_schema 读取失败: " + type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        _print_gate({"result": "ERROR", "reason": reason, "target_db": target_db, "checked_at": checked_at})
        return EXIT_ENV

    totals = summarize(results)
    camel = camel_summary(results)
    print("扫描: " + str(len(scope)) + " 张含商家标识列的表(merchant_id "
          + str(len(scope) - camel["camel_tables_scanned"]) + " 张 + camelCase "
          + str(camel["camel_tables_scanned"]) + " 张)")
    print("-- 已登记 / 豁免(只登记,不告警) --")
    printed_registered = False
    printed_reasons = set()
    for table in sorted(results):
        for entry in results[table]["registered"]:
            printed_registered = True
            info = entry["exemption"]
            print("  " + table + "." + str(entry["merchant_id"]) + " | 行数 " + str(entry["row_count"])
                  + " | id 样例 " + str(entry["sample_ids"]) + " | 类型 " + info["kind"]
                  + " | 登记日期 " + info["registered_at"])
            if info["reason"] not in printed_reasons:
                printed_reasons.add(info["reason"])
                print("      理由: " + info["reason"])
                print("      移除条件: " + info["removal_condition"])
    if not printed_registered:
        print("  (无)")

    print("-- 未登记孤儿(告警对象) --")
    if totals["unregistered_rows"] == 0:
        print("  (无)")
    for table in sorted(results):
        for entry in results[table]["unregistered"]:
            print("  " + table + "." + str(entry["merchant_id"]) + " | 行数 " + str(entry["row_count"])
                  + " | id 样例 " + str(entry["sample_ids"]))

    print("-- camelCase 列的表(单独分组,便于人工核对;#T-20-R4) --")
    camel_tables = [
        table for table in sorted(results) if results[table]["column"] != DEFAULT_MERCHANT_COLUMN
    ]
    if not camel_tables:
        print("  (无)")
    for table in camel_tables:
        row = results[table]
        print("  " + table + " | 列 " + row["column"] + " | 总行数 " + str(row["total_rows"])
              + " | 孤儿 " + str(row["rows"]) + " | 已登记 " + str(row["registered_rows"])
              + " | 未登记 " + str(row["unregistered_rows"]))

    print("-- 参考(不参与判定) --")
    for table in sorted(results):
        if results[table]["null_mid"]:
            print("  " + table + "." + results[table]["column"] + " IS NULL: "
                  + str(results[table]["null_mid"]) + " 行")

    result, code = verdict_of(totals["unregistered_rows"])
    print("统计: 孤儿 " + str(totals["orphan_rows"]) + " 行 = 已登记 " + str(totals["registered_rows"])
          + " + 未登记 " + str(totals["unregistered_rows"]))
    print("[提示] 本脚本只登记不删除;清理须走铁律 5(先备份 → 按主键 id 精确删除 → 前后计数校验)并由用户批准")
    _print_gate({
        "result": result,
        "target_db": target_db,
        "target_host": str(host) + ":" + str(port),
        "checked_at": checked_at,
        "tables_scanned": len(scope),
        "camel_tables_scanned": camel["camel_tables_scanned"],
        "camel_orphan_rows": camel["camel_orphan_rows"],
        "orphan_rows": totals["orphan_rows"],
        "registered_rows": totals["registered_rows"],
        "unregistered_rows": totals["unregistered_rows"],
    })
    return code


if __name__ == "__main__":
    sys.exit(main())
