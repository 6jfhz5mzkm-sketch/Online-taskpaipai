"""ORM 普通索引(KEY) <-> 真源 schema.sql **自动核对**(#T-18;取代原手抄 EXPECTED 清单)。

为什么要改:原实现把真源的索引抄成**第三份副本**(真源 / ORM 声明 / 清单各一份),它自己会漂移 ——
同类事故已发生 3 次(#PB-23 -> #DB-19 -> #T-17),每次真源加表/索引都让全链验证变红,且断言失败不指认该补哪一项。
现在**删除该副本**:测试直接复用 api-py/scripts/check_schema.py::parse_schema_sql 解析真源,
与 ORM 声明做**双向核对**(缺项 / 多项 / 列不符),差异逐条**指名到表 + 条目 + 列**。

硬约束(#T-18):
1. 判断依据**只有真源解析结果**,不从 ORM 反推期望;
2. **解析失败/解析为空必须红** —— 显式断言下界(当前真源 30 表 / 39 KEY / 21 UNIQUE KEY),
   且解析器抛 SchemaParseError 时用例直接失败(不 catch、不降级);
3. **不做任何自动对齐/自动改写** —— 真源变更仍让测试红,只是报错直接指认差异。

口径:普通索引按**声明序**比列(列序/列名变化都算漂移);唯一键见 test_orm_unique_constraints.py(列名升序)。
真源路径可用环境变量 ORM_SOURCE_SCHEMA_PATH 覆盖(仅用于反证/自检)。
"""

from app.db import models as _models  # noqa: F401  注册全部 ORM 模型
from app.db.base import Base
from tests.schema_source_truth import (
    ALLOWED_DIFFS,
    MIN_KEYS,
    MIN_TABLES,
    MIN_UNIQUES,
    index_diffs,
    load_source_tables,
    schema_path,
    source_totals,
)


def test_source_truth_parses_and_meets_lower_bounds():
    """真源必须可解析且规模不低于下界 —— 解析失败/为空/缩水一律红,绝不因「两边都空」假绿。"""
    tables = load_source_tables()          # 文件缺失/无法解析 -> SchemaParseError -> 本用例红
    table_count, key_count, unique_count = source_totals(tables)
    assert table_count >= MIN_TABLES, "真源表数异常偏少: %d < %d(%s)" % (table_count, MIN_TABLES, schema_path())
    assert key_count >= MIN_KEYS, "真源普通索引数异常偏少: %d < %d" % (key_count, MIN_KEYS)
    assert unique_count >= MIN_UNIQUES, "真源唯一键数异常偏少: %d < %d" % (unique_count, MIN_UNIQUES)
    assert tables, "真源解析结果为空"


def test_orm_indexes_match_schema_sql():
    """ORM 声明的普通索引与真源**双向一致**(缺/多/列不符都指名报出)。"""
    diffs = index_diffs()
    assert diffs == [], "ORM 普通索引与真源 schema.sql 不一致(%d 处):\n  - %s" % (
        len(diffs), "\n  - ".join(diffs))


def test_allowed_diff_exceptions_exist_in_source():
    """例外清单(默认空)中的每一条都必须在真源里找得到 —— 例外不得成为新的漂移源。"""
    tables = load_source_tables()
    entries = {(t, i["kind"], i["name"]) for t, info in tables.items() for i in info["indexes"]}
    for table, kind, name, reason in ALLOWED_DIFFS:
        assert (table, kind, name) in entries, "例外条目在真源中不存在: %s/%s/%s(%s)" % (table, kind, name, reason)


def test_declared_indexes_are_not_unique():
    """普通索引不得声明 unique=True(唯一性由 UniqueConstraint 承载,避免重复语义)。"""
    offenders = [(t.name, ix.name) for t in Base.metadata.tables.values() for ix in t.indexes if ix.unique]
    assert offenders == [], offenders


def test_indexes_are_declared_via_index_objects_not_column_flag():
    """禁止用 index=True 列级声明:索引名须与实库一致,列级声明无法指定名称。"""
    offenders = [(t.name, c.name) for t in Base.metadata.tables.values() for c in t.columns if c.index]
    assert offenders == [], offenders
