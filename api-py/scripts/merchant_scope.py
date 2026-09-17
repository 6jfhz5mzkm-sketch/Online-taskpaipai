"""商家标识列 / 表的动态发现（唯一真源，#T-20-R1）。

**放置理由（为什么是 `scripts/`）**：
- 本口径有**两个消费方** —— ① `tests/conftest.py::cleanup_temp_merchant`（临时实体清理必须覆盖
  **全部**含商家标识的表，漏一张就留孤儿）；② `scripts/check_orphan.py`（孤儿巡检的候选表发现）。
  两者必须同源：铁律 5 记载的历史事故（#PB-24-3 漏删 `event_log` / `merchant_stage_progress`
  → 16 行孤儿、`ORPHAN_GATE` 变红）与本次 **#T-20 D1**（清理助手硬编码 9 张表、漏 `event_log`）
  都是"两处各写一份表清单"的后果。
- **不放进 `app/**`**：它不是业务规则、也不是数据访问层，而是**库表事实口径**（运维 / 测试共用）；
  且 #T-20-R1 边界明确禁止改业务代码。
- **不放进 `tests/`**：`scripts/check_orphan.py` 也要用。`api-py` 根下两处都能 import 本模块 ——
  tests 侧有 `tests/__init__.py` 且 pytest 把 rootdir 加入 `sys.path`；scripts 侧由
  `check_orphan.py` 的 `sys.path.insert(0, api-py 根)` 保证。故 `scripts/` 是两边都自然的落点。

**两侧已是同一集合（#T-20-R4 起；门禁语义变更经用户 2026-09-16 批准）**：
临时商家清理助手与孤儿巡检**共用本模块的 `discover_merchant_scope()`** —— 列名 ∈
{`merchant_id`, `merchantId`}，当前库 **16 张**（15 张 `merchant_id` + 1 张驼峰
`merchant_task_progress.merchantId`）。R1 时期"巡检仅扫 `merchant_id`"的**窄口径已废止**
（那是盲区：驼峰表恰是账号绑定进度表），本模块不再保留第二份"巡检专用"SQL。

**边界（#T-20-R3 起）**：本模块提供两件事 ——
① **发现**：`discover_merchant_scope`（清理助手与孤儿巡检**共用同一集合**）；
② **按精确值清理一个商家的全部作用域行**：`purge_merchant_rows`（**单一实现**，供
`tests/conftest.py` 的 `cleanup_temp_merchant` 与 `scripts/**` 的验证脚本共用，避免任何一处
再自写表清单或自写删除循环）。

仍然**禁止宽泛谓词**（如 `LIKE 'mock_%'`），**绝不触碰 `merchant_id IS NULL`** 的行（登录前埋点，
设计使然），本模块不含任何 DDL / UPDATE。
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

# 商家标识列的两种拼写（驼峰拼写来自 merchant_task_progress）
MERCHANT_ID_COLUMNS: Tuple[str, ...] = ("merchant_id", "merchantId")

# 清理助手口径：全部含商家标识列的表 + 各自真实列名（逐表返回列名，调用方无需猜拼写）
SQL_MERCHANT_SCOPE_TABLES = (
    "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS "
    "WHERE TABLE_SCHEMA = DATABASE() AND COLUMN_NAME IN ('merchant_id', 'merchantId') "
    "ORDER BY TABLE_NAME"
)

def discover_merchant_scope(conn: Any) -> List[Tuple[str, str]]:
    """返回 [(表名, 商家标识列名), ...]（列名 ∈ {merchant_id, merchantId}，按表名排序）。

    `conn` 可以是 SQLAlchemy `Session` 或 `Connection`（两者都支持 `execute(text(...))`）。
    """
    from sqlalchemy import text

    rows = conn.execute(text(SQL_MERCHANT_SCOPE_TABLES)).fetchall()
    return [(str(row[0]), str(row[1])) for row in rows]


# 按精确值删除一个商家在单张表中的行（表名/列名均来自发现结果，不做字符串拼接用户输入）
SQL_DELETE_BY_MERCHANT = "DELETE FROM `{table}` WHERE `{column}` = :merchant_id"


def purge_merchant_rows(conn: Any, merchant_id: str) -> Dict[str, int]:
    """删除某商家在**全部**作用域表中的行（单一事务提交，幂等），返回 {`表名`: 删除行数}。

    口径：
    - 表与列名**一律来自** `discover_merchant_scope()`（当前库 16 张，含驼峰
      `merchant_task_progress.merchantId`），禁止任何硬编码清单；
    - 逐表按**精确值** `WHERE <col> = :merchant_id`（**禁止 `LIKE`**）；
    - **绝不删除 `merchant_id IS NULL`** 的行（登录前埋点，设计使然）；
    - `merchant` 主表**最后**删（语义清晰；本库无外键，顺序不影响正确性）；
    - 发现为空时**结构化抛错**（绝不静默跳过，否则会假装"已清理"）；
    - 重复调用幂等（第二次返回的行数全为 0）。

    `conn` 可以是 SQLAlchemy `Session` 或 `Connection`。
    """
    from sqlalchemy import text

    scopes = discover_merchant_scope(conn)
    if not scopes:
        raise RuntimeError("merchant_scope 发现为空：information_schema 未返回任何含商家标识列的表")
    deleted: Dict[str, int] = {}
    for table, column in sorted(scopes, key=lambda item: (item[0] == "merchant", item[0])):
        result = conn.execute(
            text(SQL_DELETE_BY_MERCHANT.format(table=table, column=column)),
            {"merchant_id": merchant_id},
        )
        deleted[table] = int(result.rowcount or 0)
    conn.commit()
    return deleted
