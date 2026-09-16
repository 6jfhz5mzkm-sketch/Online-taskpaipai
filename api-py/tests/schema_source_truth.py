"""ORM 声明 <-> 真源解析 的唯一对账入口(#T-18;测试专用,非产品代码)。

真源 = project/scripts/schema.sql,经 **api-py/scripts/check_schema.py::parse_schema_sql** 解析
(复用既有解析器,不另写一套)。判断依据**只有真源解析结果**,绝不从 ORM 反推「应该有什么」。

口径:
- 普通索引 KEY:比 (索引名, **按声明序列的列元组**) —— 列序或列名变化都算漂移;
- 唯一键 UNIQUE KEY:比 (约束名, **列名升序元组**) —— 与既有用例的语义口径一致(唯一性不依赖列序);
- 真源路径可用环境变量 ORM_SOURCE_SCHEMA_PATH 覆盖(仅用于反证/自检;默认指向真源)。

例外清单(ALLOWED_DIFFS)默认为空:本仓真源 30 张表全部有 ORM 模型,无需例外。
若将来确需例外,必须写在此处,并由 test_orm_indexes.py 断言「每条例外都能在真源中找到对应条目」,
不允许例外清单成为新的漂移源。
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
CHECK_SCHEMA_PATH = REPO_ROOT / "api-py" / "scripts" / "check_schema.py"

# 真源规模下界(当前真源 = 30 表 / 39 KEY / 21 UNIQUE KEY):解析为空或缩水必须红,不得假绿。
MIN_TABLES = 30
MIN_KEYS = 39
MIN_UNIQUES = 21

# 允许的差异白名单(默认空)。条目形如 (table, kind, name, reason);kind ∈ {"KEY", "UNIQUE KEY"}。
ALLOWED_DIFFS: Tuple[Tuple[str, str, str, str], ...] = ()


def _load_check_schema() -> Any:
    """以文件路径加载 check_schema.py(它没有 __main__ 副作用,可安全导入)。"""
    spec = importlib.util.spec_from_file_location("t18_check_schema", CHECK_SCHEMA_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - 环境异常
        raise RuntimeError("无法加载真源解析器: " + str(CHECK_SCHEMA_PATH))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECK_SCHEMA = _load_check_schema()
SchemaParseError = CHECK_SCHEMA.SchemaParseError


def schema_path() -> Path:
    """生效真源路径(环境变量可覆盖,仅供反证/自检使用)。"""
    override = (os.environ.get("ORM_SOURCE_SCHEMA_PATH") or "").strip()
    return Path(override) if override else Path(CHECK_SCHEMA.DEFAULT_SCHEMA_PATH)


def load_source_tables(path: Path = None) -> Dict[str, Dict[str, Any]]:
    """解析真源;文件缺失/无法解析/解析为空 -> 抛 SchemaParseError(调用方不得吞掉)。"""
    return CHECK_SCHEMA.parse_schema_sql(path or schema_path())


def source_totals(tables: Dict[str, Dict[str, Any]]) -> Tuple[int, int, int]:
    """(表数, KEY 数, UNIQUE KEY 数)。"""
    keys = sum(1 for t in tables.values() for i in t["indexes"] if i["kind"] == "KEY")
    uniques = sum(1 for t in tables.values() for i in t["indexes"] if i["kind"] == "UNIQUE KEY")
    return len(tables), keys, uniques


def _source_index_maps(tables):
    keys, uniques = {}, {}
    for table, info in tables.items():
        keys[table] = {i["name"]: tuple(i["columns"]) for i in info["indexes"] if i["kind"] == "KEY"}
        uniques[table] = {i["name"]: tuple(sorted(i["columns"])) for i in info["indexes"] if i["kind"] == "UNIQUE KEY"}
    return keys, uniques


def _orm_maps():
    from app.db import models as _models  # noqa: F401  注册全部模型
    from app.db.base import Base

    keys, uniques = {}, {}
    for table in Base.metadata.tables.values():
        keys[table.name] = {ix.name: tuple(col.name for col in ix.columns) for ix in table.indexes}
        uniques[table.name] = {
            c.name: tuple(sorted(col.name for col in c.columns))
            for c in table.constraints
            if c.__class__.__name__ == "UniqueConstraint"
        }
    return keys, uniques


def _diff(schema_map: Dict[str, Dict[str, Any]], orm_map: Dict[str, Dict[str, Any]],
          kind: str, allowed: Tuple[Tuple[str, str, str, str], ...] = ()) -> List[str]:
    """双向差异:真源为准。返回逐条**指名到表与条目**的中文差异描述;白名单条目(表+名称)跳过。"""
    allowed_pairs = {(t, n) for t, k, n, _ in allowed if k == kind}
    diffs: List[str] = []
    for table in sorted(set(schema_map) | set(orm_map)):
        expected = schema_map.get(table, {})
        declared = orm_map.get(table, {})
        if table not in schema_map:
            if declared:
                diffs.append("%s: ORM 有此表但真源无(真源无依据的声明): %s" % (table, sorted(declared)))
            continue
        if table not in orm_map:
            if expected:
                diffs.append("%s: 真源有索引/唯一键但无 ORM 模型: %s" % (table, sorted(expected)))
            continue
        for name in sorted(set(expected) - set(declared)):
            if (table, name) in allowed_pairs:
                continue
            diffs.append("%s: ORM 缺少声明 [%s] %s" % (table, name, list(expected[name])))
        for name in sorted(set(declared) - set(expected)):
            if (table, name) in allowed_pairs:
                continue
            diffs.append("%s: ORM 多出声明(真源无) [%s] %s" % (table, name, list(declared[name])))
        for name in sorted(set(expected) & set(declared)):
            if (table, name) in allowed_pairs:
                continue
            if expected[name] != declared[name]:
                diffs.append("%s: [%s] 列不符 真源=%s ORM=%s" % (table, name, list(expected[name]), list(declared[name])))
    return diffs


def index_diffs(tables=None) -> List[str]:
    """普通索引 KEY 的双向差异(保序比列)。"""
    tables = tables if tables is not None else load_source_tables()
    source_keys, _ = _source_index_maps(tables)
    orm_keys, _ = _orm_maps()
    return _diff(source_keys, orm_keys, "KEY", ALLOWED_DIFFS)


def unique_diffs(tables=None) -> List[str]:
    """唯一键 UNIQUE KEY 的双向差异(列名升序比)。"""
    tables = tables if tables is not None else load_source_tables()
    _, source_uniques = _source_index_maps(tables)
    _, orm_uniques = _orm_maps()
    return _diff(source_uniques, orm_uniques, "UNIQUE KEY", ALLOWED_DIFFS)
