"""ORM 唯一约束(UNIQUE KEY) <-> 真源 schema.sql **自动核对**(#T-18;取代原手抄 EXPECTED 清单)。

同 test_orm_indexes.py:删除「人手抄的第三份副本」,改为直接用 check_schema.py 解析真源并与 ORM 双向核对,
差异指名到表 + 约束名 + 列。口径:唯一键比 (约束名, **列名升序元组**) —— 唯一性语义不依赖列序,
与既有口径一致;因此**纯列序交换**不算漂移,列名增删/改名才算。
"""

from app.db import models as _models  # noqa: F401  注册全部 ORM 模型
from app.db.base import Base
from tests.schema_source_truth import load_source_tables, unique_diffs


def test_orm_unique_constraints_match_schema_sql():
    """ORM 声明的唯一键与真源**双向一致**(缺/多/列不符都指名报出)。"""
    diffs = unique_diffs()
    assert diffs == [], "ORM 唯一约束与真源 schema.sql 不一致(%d 处):\n  - %s" % (
        len(diffs), "\n  - ".join(diffs))


def test_unnamed_column_level_unique_left():
    """列级 unique=True 一律不允许(约束名必须与真源对齐,便于 autogenerate 对账)。"""
    offenders = [(t.name, c.name) for t in Base.metadata.tables.values() for c in t.columns if c.unique]
    assert offenders == [], offenders


def test_source_truth_has_unique_keys():
    """真源确实解析出了唯一键(防「两边都空」假绿;与索引侧的下界断言互为补充)。"""
    tables = load_source_tables()
    total = sum(1 for t in tables.values() for i in t["indexes"] if i["kind"] == "UNIQUE KEY")
    assert total >= 21, "真源唯一键数异常偏少: %d" % total
