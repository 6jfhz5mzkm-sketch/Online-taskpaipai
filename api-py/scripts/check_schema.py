"""只读结构对账门禁: schema.sql(表结构真源) ↔ 实库。

背景(任务单 #DB-6 / P-4 §T0): npm run verify:db 原先只跑 alembic current,而 api-py/alembic/versions
为空、实库无 alembic_version 表 -> 该命令只打印两行 INFO 并 exit 0,DB 段门禁长期空转。
本脚本用「解析 schema.sql + 读 information_schema」做真正的结构化对账,并以退出码表达结论。

硬门禁(任一命中即 exit 1):
  1. 表集合不一致(仅真源有 / 仅实库有)
  2. 列集合或列序不一致
  3. 列类型/精度不一致
  4. 列空性不一致(真源未写 NOT NULL 而实库 NOT NULL,或反之)
  5. 列注释不一致
  6. 表注释不一致

已知例外(显式打印, 不阻断):
  COLLATION 差异 —— 见 KNOWN_COLLATION_EXCEPTIONS(P-4 (4) 批次 B 完成前不清空)。
  清单外的 COLLATION 差异按硬失败处理。

建议态(显式打印, 不阻断):
  ORM 声明(api-py/app/db/models)与真源的唯一键/普通索引覆盖差异、无 ORM 模型的真源表。
  刻意不引入 alembic.autogenerate.compare_metadata 作为硬门禁: compare_type=True 会因 6 个
  无长度 String 列抛 CompileError(#DB-1 6.3),且 diff 数值随 ORM 并发改动而变(#DB-2 7)。

退出码:
  0 通过 / 1 结构漂移 / 2 环境或输入错误(DB 不可达、schema.sql 缺失或无法解析) —— 绝不静默跳过。

用法:
  cd api-py && uv run python scripts/check_schema.py
  uv run python scripts/check_schema.py --self-test     # 自检: 注入合成差异,断言各类检查都能检出
  uv run python scripts/check_schema.py --schema <path> # 指定真源(默认 project/scripts/schema.sql)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 脚本可独立运行: 把 api-py 根加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA_PATH = REPO_ROOT / "project" / "scripts" / "schema.sql"

EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_ENV = 2

TARGET_COLLATION = "utf8mb4_0900_ai_ci"
# COLLATION 已知例外(P-4 (4) 批次 B)。
# 2026-09-11 #DB-7 第 2 部分已完成 4 张表(admin_account / first_level_task /
# merchant_task_progress / second_level_task)的 CONVERT TO utf8mb4_0900_ai_ci,
# 全库已是单一 collation, 故清单清空 —— collation 差异自此为硬失败。
# 仅当再次出现"真源已定义目标态、实库因历史原因尚未转换"的**已登记**差异时才可临时加入,
# 且必须同时登记移除条件(参照 P-4 (4) 的两步绑定口径)。
KNOWN_COLLATION_EXCEPTIONS = frozenset()
MAX_PRINT = 60

_TYPE_KEYWORDS = ("NOT NULL", "DEFAULT", "COMMENT", "AUTO_INCREMENT", "ON UPDATE")
_INDEX_LINE = re.compile(r"^(PRIMARY KEY|UNIQUE KEY|KEY|CONSTRAINT|INDEX)\b", re.I)
_CREATE_TABLE = re.compile(r"CREATE TABLE\s+(\w+)\s*\(")
_COLUMN_LINE = re.compile(r"^\s*(\w+)\s+(.*?),?$")
_INDEX_DEF = re.compile(r"^(PRIMARY KEY|UNIQUE KEY|KEY)\s+(\w+)?\s*\(([^)]*)\)", re.I)


class SchemaParseError(Exception):
    """schema.sql 无法解析(缺文件、无 CREATE TABLE、列定义非法)。"""


class DatabaseUnavailable(Exception):
    """实库不可达或 information_schema 查询失败。"""


def _split_type(definition: str) -> str:
    upper, cut = definition.upper(), len(definition)
    for keyword in _TYPE_KEYWORDS:
        pos = upper.find(keyword)
        if pos != -1:
            cut = min(cut, pos)
    return re.sub(r"\s+", " ", definition[:cut]).strip().lower()


def parse_schema_sql(path: Path) -> Dict[str, Dict[str, Any]]:
    """解析 schema.sql 为 {table: {columns, indexes, options, table_comment, declared_collation}}。"""
    if not path.is_file():
        raise SchemaParseError("真源文件不存在: " + str(path))
    lines = path.read_text(encoding="utf-8").splitlines()
    tables: Dict[str, Dict[str, Any]] = {}
    current: Optional[Dict[str, Any]] = None
    for lineno, line in enumerate(lines, start=1):
        match = _CREATE_TABLE.match(line)
        if match:
            current = {"line": lineno, "columns": [], "indexes": [], "options": ""}
            tables[match.group(1)] = current
            continue
        if current is None:
            continue
        if line.startswith(")"):
            current["options"] = line.strip().rstrip(";")
            comment = re.search(r"COMMENT='([^']*)'", current["options"])
            current["table_comment"] = comment.group(1) if comment else ""
            collate = re.search(r"COLLATE=(\w+)", current["options"])
            current["declared_collation"] = collate.group(1) if collate else TARGET_COLLATION
            current = None
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        if _INDEX_LINE.match(stripped):
            index = _INDEX_DEF.match(stripped)
            if index:
                current["indexes"].append(
                    {
                        "kind": index.group(1).upper(),
                        "name": index.group(2) or "",
                        "columns": [c.strip() for c in index.group(3).split(",")],
                    }
                )
            continue
        column = _COLUMN_LINE.match(line)
        if column:
            definition = column.group(2)
            comment = re.search(r"COMMENT\s+'([^']*)'", definition)
            current["columns"].append(
                {
                    "name": column.group(1),
                    "line": lineno,
                    "type": _split_type(definition),
                    "not_null": bool(re.search(r"\bNOT NULL\b", definition, re.I)),
                    "comment": comment.group(1) if comment else "",
                }
            )
    if not tables:
        raise SchemaParseError("真源中未解析到任何 CREATE TABLE: " + str(path))
    return tables


def read_live_schema() -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Any]]:
    """只读读取实库结构; 失败抛 DatabaseUnavailable(绝不静默跳过)。"""
    from app.core.config import get_settings
    from app.db.engine import engine

    settings = get_settings()
    meta = {
        "host": settings.DB_HOST,
        "port": settings.DB_PORT,
        "database": settings.DB_NAME,
    }
    try:
        with engine.connect() as conn:
            column_rows = conn.execute(
                text(
                    "SELECT TABLE_NAME, COLUMN_NAME, ORDINAL_POSITION, COLUMN_TYPE, IS_NULLABLE, COLUMN_COMMENT "
                    "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = :schema "
                    "ORDER BY TABLE_NAME, ORDINAL_POSITION"
                ),
                {"schema": settings.DB_NAME},
            ).mappings().all()
            table_rows = conn.execute(
                text(
                    "SELECT TABLE_NAME, TABLE_COLLATION, TABLE_COMMENT FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA = :schema"
                ),
                {"schema": settings.DB_NAME},
            ).mappings().all()
    except Exception as exc:  # noqa: BLE001 - 统一转成结构化环境错误
        raise DatabaseUnavailable(type(exc).__name__ + ": " + str(exc)) from exc

    tables: Dict[str, Dict[str, Any]] = {}
    for row in table_rows:
        tables[row["TABLE_NAME"]] = {
            "collation": row["TABLE_COLLATION"],
            "table_comment": row["TABLE_COMMENT"] or "",
            "columns": [],
        }
    for row in column_rows:
        table = tables.get(row["TABLE_NAME"])
        if table is None:
            continue
        table["columns"].append(
            {
                "name": row["COLUMN_NAME"],
                "position": row["ORDINAL_POSITION"],
                "type": (row["COLUMN_TYPE"] or "").lower(),
                "not_null": row["IS_NULLABLE"] == "NO",
                "comment": row["COLUMN_COMMENT"] or "",
            }
        )
    if not tables:
        raise DatabaseUnavailable("实库 " + settings.DB_NAME + " 中没有任何表")
    return tables, meta


def compare(
    schema_tables: Dict[str, Dict[str, Any]],
    live_tables: Dict[str, Dict[str, Any]],
    known_collation_exceptions: frozenset = KNOWN_COLLATION_EXCEPTIONS,
) -> Dict[str, Any]:
    """结构化对账; 返回 failures(硬门禁) / exceptions(已知例外) / notes(提示)。"""
    failures: Dict[str, List[str]] = {}
    exceptions: List[str] = []
    notes: List[str] = []

    def add(kind: str, message: str) -> None:
        failures.setdefault(kind, []).append(message)

    schema_only = sorted(set(schema_tables) - set(live_tables))
    db_only = sorted(set(live_tables) - set(schema_tables))
    for name in schema_only:
        add("table_set", "仅真源有表: " + name)
    for name in db_only:
        add("table_set", "仅实库有表: " + name)

    for name in sorted(set(schema_tables) & set(live_tables)):
        expected_columns = schema_tables[name]["columns"]
        actual_columns = live_tables[name]["columns"]
        expected_names = [c["name"] for c in expected_columns]
        actual_names = [c["name"] for c in actual_columns]
        if set(expected_names) != set(actual_names):
            add(
                "columns",
                name + ": 列集合不一致; 仅真源有=" + str(sorted(set(expected_names) - set(actual_names)))
                + " 仅实库有=" + str(sorted(set(actual_names) - set(expected_names))),
            )
        elif expected_names != actual_names:
            add("column_order", name + ": 列序不一致; 真源=" + str(expected_names) + " 实库=" + str(actual_names))
        actual_by_name = {c["name"]: c for c in actual_columns}
        for expected in expected_columns:
            actual = actual_by_name.get(expected["name"])
            if actual is None:
                continue
            if expected["type"] != actual["type"]:
                add(
                    "column_type",
                    name + "." + expected["name"] + ": 真源=" + expected["type"] + " 实库=" + actual["type"],
                )
            if expected["not_null"] != actual["not_null"]:
                add(
                    "column_nullability",
                    name + "." + expected["name"] + ": 真源 " + ("NOT NULL" if expected["not_null"] else "NULL")
                    + " / 实库 " + ("NOT NULL" if actual["not_null"] else "NULL"),
                )
            if expected["comment"] != actual["comment"]:
                add(
                    "column_comment",
                    name + "." + expected["name"] + ": 真源=" + repr(expected["comment"])
                    + " 实库=" + repr(actual["comment"]),
                )
        if schema_tables[name]["table_comment"] != live_tables[name]["table_comment"]:
            add(
                "table_comment",
                name + ": 真源=" + repr(schema_tables[name]["table_comment"])
                + " 实库=" + repr(live_tables[name]["table_comment"]),
            )
        declared = schema_tables[name]["declared_collation"]
        actual_collation = live_tables[name]["collation"]
        if declared != actual_collation:
            message = name + ": 真源=" + declared + " 实库=" + actual_collation
            if name in known_collation_exceptions:
                exceptions.append(message)
            else:
                add("collation", message)

    matched_exceptions = sorted(
        name
        for name in known_collation_exceptions
        if name in schema_tables
        and name in live_tables
        and schema_tables[name]["declared_collation"] == live_tables[name]["collation"]
    )
    if matched_exceptions:
        notes.append(
            "COLLATION 已知例外清单中已有 " + str(len(matched_exceptions)) + " 张表不再存在差异,可移出清单: "
            + ", ".join(matched_exceptions)
        )
    return {"failures": failures, "exceptions": exceptions, "notes": notes}


def orm_advisory(schema_tables: Dict[str, Dict[str, Any]]) -> Tuple[List[str], Optional[str]]:
    """建议态: ORM 声明的唯一键/索引与真源的覆盖差异(不阻断)。"""
    try:
        from app.db import models as _models  # noqa: F401  注册全部模型
        from app.db.base import Base
    except Exception as exc:  # noqa: BLE001 - 建议态失败不影响门禁
        return [], "ORM 元数据不可用: " + type(exc).__name__ + ": " + str(exc)

    advisories: List[str] = []
    metadata_tables = set(Base.metadata.tables)
    for name in sorted(set(schema_tables) - metadata_tables):
        advisories.append("真源表无 ORM 模型: " + name)
    for name in sorted(metadata_tables - set(schema_tables)):
        advisories.append("ORM 表不在真源中: " + name)
    for name in sorted(set(schema_tables) & metadata_tables):
        table = Base.metadata.tables[name]
        declared_unique = {
            (constraint.name, tuple(sorted(col.name for col in constraint.columns)))
            for constraint in table.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        }
        declared_indexes = {
            (index.name, tuple(sorted(col.name for col in index.columns))) for index in table.indexes
        }
        expected_unique = {
            (item["name"], tuple(sorted(item["columns"])))
            for item in schema_tables[name]["indexes"]
            if item["kind"] == "UNIQUE KEY"
        }
        expected_indexes = {
            (item["name"], tuple(sorted(item["columns"])))
            for item in schema_tables[name]["indexes"]
            if item["kind"] == "KEY"
        }
        for missing in sorted(expected_unique - declared_unique):
            advisories.append(name + ": ORM 未声明唯一键 " + str(missing))
        for missing in sorted(expected_indexes - declared_indexes):
            advisories.append(name + ": ORM 未声明普通索引 " + str(missing))
        for extra in sorted(declared_unique - expected_unique):
            advisories.append(name + ": ORM 声明了真源中不存在的唯一键 " + str(extra))
        for extra in sorted(declared_indexes - expected_indexes):
            advisories.append(name + ": ORM 声明了真源中不存在的索引 " + str(extra))
    return advisories, None


def _print_bucket(title: str, items: List[str], prefix: str) -> None:
    print(prefix + " " + title + ": " + ("一致" if not items else str(len(items)) + " 项"))
    for item in items[:MAX_PRINT]:
        print("    - " + item)
    if len(items) > MAX_PRINT:
        print("    ... 另有 " + str(len(items) - MAX_PRINT) + " 项未打印")


def report(result: Dict[str, Any], schema_path: Path, schema_tables: Dict[str, Any],
           live_tables: Dict[str, Any], meta: Dict[str, Any], advisories: List[str],
           advisory_note: Optional[str]) -> int:
    failures = result["failures"]
    total_failures = sum(len(v) for v in failures.values())
    total_columns = sum(len(t["columns"]) for t in schema_tables.values())

    print("=== 结构对账: schema.sql (真源) <-> 实库 ===")
    print("真源: " + str(schema_path))
    print("实库: " + meta["database"] + "@" + str(meta["host"]) + ":" + str(meta["port"])
          + "(MySQL, " + str(len(live_tables)) + " 张表)")
    print("真源: " + str(len(schema_tables)) + " 张表 / " + str(total_columns) + " 列")
    print("-- 硬门禁 --")
    if total_failures == 0:
        print("[PASS] 表集合 / 列集合与列序 / 类型与精度 / 空性 / 列注释 / 表注释: 全部一致")
    for kind in sorted(failures):
        _print_bucket(kind, failures[kind], "[FAIL]")
    print("-- 已知例外(不阻断) --")
    _print_bucket(
        "COLLATION(清单内, 待 P-4 (4) 批次 B 转换)",
        result["exceptions"],
        "[EXCEPTION]",
    )
    for note in result["notes"]:
        print("[NOTE] " + note)
    print("-- 建议态(不阻断) --")
    if advisory_note:
        print("[ADVISORY] " + advisory_note)
    _print_bucket("ORM 声明与真源的差异", advisories, "[ADVISORY]")

    verdict = "PASS" if total_failures == 0 else "FAIL"
    summary = {
        "result": verdict,
        "failures": total_failures,
        "failure_kinds": {k: len(v) for k, v in sorted(failures.items())},
        "known_exceptions": len(result["exceptions"]),
        "advisories": len(advisories),
    }
    print("SCHEMA_GATE " + json.dumps(summary, ensure_ascii=False))
    return EXIT_OK if verdict == "PASS" else EXIT_DRIFT


def _selftest() -> int:
    """自检: 构造合成差异, 断言每一类检查都能被检出(证明门禁不是空转)。"""
    base_schema = {
        "t": {
            "columns": [
                {"name": "id", "type": "bigint unsigned", "not_null": True, "comment": ""},
                {"name": "name", "type": "varchar(64)", "not_null": True, "comment": "名称"},
                {"name": "created_at", "type": "datetime(6)", "not_null": True, "comment": "创建时间"},
            ],
            "indexes": [],
            "table_comment": "示例表",
            "declared_collation": TARGET_COLLATION,
        }
    }
    base_live = {
        "t": {
            "columns": [
                {"name": "id", "type": "bigint unsigned", "not_null": True, "comment": ""},
                {"name": "name", "type": "varchar(64)", "not_null": True, "comment": "名称"},
                {"name": "created_at", "type": "datetime(6)", "not_null": True, "comment": "创建时间"},
            ],
            "table_comment": "示例表",
            "collation": TARGET_COLLATION,
        }
    }

    def mutate(fn):
        import copy

        schema = copy.deepcopy(base_schema)
        live = copy.deepcopy(base_live)
        fn(schema, live)
        return schema, live

    def set_nullability(schema, live):
        live["t"]["columns"][1]["not_null"] = False

    def set_type(schema, live):
        live["t"]["columns"][2]["type"] = "datetime"

    def set_comment(schema, live):
        live["t"]["columns"][1]["comment"] = "别的注释"

    def set_table_comment(schema, live):
        live["t"]["table_comment"] = "别的表注释"

    def swap_order(schema, live):
        live["t"]["columns"][1], live["t"]["columns"][2] = live["t"]["columns"][2], live["t"]["columns"][1]

    def drop_column(schema, live):
        live["t"]["columns"].pop()

    def add_db_table(schema, live):
        live["extra"] = {"columns": [], "table_comment": "", "collation": TARGET_COLLATION}

    def drop_db_table(schema, live):
        live.pop("t")

    def set_collation(schema, live):
        live["t"]["collation"] = "utf8mb4_unicode_ci"

    cases = [
        ("空性差异", set_nullability, "column_nullability"),
        ("类型/精度差异", set_type, "column_type"),
        ("列注释差异", set_comment, "column_comment"),
        ("表注释差异", set_table_comment, "table_comment"),
        ("列序差异", swap_order, "column_order"),
        ("列集合差异", drop_column, "columns"),
        ("仅实库有表", add_db_table, "table_set"),
        ("仅真源有表", drop_db_table, "table_set"),
        ("清单外 collation 差异", set_collation, "collation"),
    ]
    print("=== check_schema.py --self-test (反证门禁非空转) ===")
    baseline = compare(base_schema, base_live)
    ok = sum(len(v) for v in baseline["failures"].values()) == 0
    print(("PASS" if ok else "FAIL") + "  基线(无差异)应判定为通过")
    failures = 0 if ok else 1
    for title, mutate_fn, expected_kind in cases:
        schema, live = mutate(mutate_fn)
        outcome = compare(schema, live)
        detected = expected_kind in outcome["failures"]
        print(("PASS" if detected else "FAIL") + "  " + title + " -> 期望命中检查项 '" + expected_kind + "'")
        if not detected:
            failures += 1
    exception_schema, exception_live = mutate(set_collation)
    exception_case = compare(exception_schema, exception_live, known_collation_exceptions=frozenset({"t"}))
    in_list = bool(exception_case["exceptions"]) and not exception_case["failures"]
    print(("PASS" if in_list else "FAIL") + "  清单内 collation 差异 -> 记为已知例外且不阻断")
    if not in_list:
        failures += 1
    print("SELFTEST " + json.dumps({"result": "PASS" if failures == 0 else "FAIL", "failed_cases": failures}))
    return EXIT_OK if failures == 0 else EXIT_DRIFT


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="schema.sql <-> 实库 只读结构对账门禁")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA_PATH), help="表结构真源路径")
    parser.add_argument("--self-test", action="store_true", help="注入合成差异, 验证各类检查可检出")
    args = parser.parse_args(argv)

    if args.self_test:
        return _selftest()

    schema_path = Path(args.schema)
    try:
        schema_tables = parse_schema_sql(schema_path)
    except SchemaParseError as exc:
        print("[ERROR] schema.sql 解析失败: " + str(exc), file=sys.stderr)
        print("SCHEMA_GATE " + json.dumps({"result": "ERROR", "reason": "schema_parse"}, ensure_ascii=False))
        return EXIT_ENV

    try:
        live_tables, meta = read_live_schema()
    except DatabaseUnavailable as exc:
        print("[ERROR] 实库不可达或 information_schema 读取失败: " + str(exc), file=sys.stderr)
        print("SCHEMA_GATE " + json.dumps({"result": "ERROR", "reason": "database_unavailable"}, ensure_ascii=False))
        return EXIT_ENV

    result = compare(schema_tables, live_tables)
    advisories, advisory_note = orm_advisory(schema_tables)
    return report(result, schema_path, schema_tables, live_tables, meta, advisories, advisory_note)


if __name__ == "__main__":
    sys.exit(main())
