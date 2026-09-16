"""只读数据编码巡检:检测「UTF-8 字节被按 CP1252 解释后再存为 UTF-8」的双重编码乱码。

背景(#DB-10,2026-09-14):生产库曾出现 5 列 79 行双重编码乱码,例如
`admin_account.realName` 存成 `è¶…çº§ç®¡ç†å‘˜`(应为 `超级管理员`)。根因是**用非 utf8mb4 客户端
字符集导入 UTF-8 数据**(服务器上已存在 9-04 的 `pre_mojibake_fix_*` 备份 → 说明修过又复发)。
该乱码形态经字节级证实是 **CP1252 而非 latin1**:`0x85/0x91/0x98` 等是 CP1252 特有映射,
超出 latin1 范围,故只用 `latin1` 规则会**全部漏检**(#DB-10 实测:latin1 规则命中 0 行)。

本脚本把该巡检固化为可重复运行的**只读**工具:数据导入/迁移后跑一次,期望命中 0。

判定规则(纯函数 detect_mojibake):
  对每个字符型列的值 v —— ① 先按 CP1252 逐字符编回字节(少数 CP1252 未定义位置回退为
  latin1 序值),再按 UTF-8 解码;② 仅当「解码成功」且「cand != v」且「cand 含 CJK
  (一-鿿)」才判为乱码候选。正常中文、正常 URL 查询串(含 `?`)都不会被误判。

用法:
  cd api-py && uv run python scripts/check_data_encoding.py [--report-only] [--max-samples N]

退出码:0 无命中 / 1 有命中(可作门禁) / 2 环境或输入错误(DB 不可达、无字符型列等) —— 绝不静默跳过。
`--report-only` 时恒为 0(仅报告,便于巡检窗口使用)。

凭据纪律:只读查询,不写库;命中敏感列(口令/盐/密钥/票据)时**只报计数、不回显任何值**。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 脚本可独立运行: 把 api-py 根加入 sys.path(与 scripts/check_schema.py 同风格)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

EXIT_OK = 0
EXIT_HITS = 1
EXIT_ENV = 2

CJK_START = "一"
CJK_END = "鿿"

# information_schema.DATA_TYPE 中的字符型列
CHAR_DATA_TYPES = ("char", "varchar", "text", "tinytext", "mediumtext", "longtext")

# 列名命中这些片段即视为敏感列:只报计数,绝不回显值(避免巡检输出泄漏口令/票据)
SENSITIVE_COLUMN_TOKENS = ("password", "salt", "secret", "token", "credential", "private_key", "privatekey")

MAX_SAMPLES_DEFAULT = 3
MAX_PRINT = 60


class DatabaseUnavailable(Exception):
    """实库不可达或 information_schema 读取失败。"""


class SchemaUnreadable(Exception):
    """读不到任何字符型列(库为空或权限不足)。"""


def has_cjk(text: str) -> bool:
    """是否含 CJK 统一表意文字(判定乱码的必要条件之一)。"""
    return any(CJK_START <= ch <= CJK_END for ch in text)


def decode_back(value: str) -> Optional[str]:
    """按 CP1252 编回字节(未定义位置回退 latin1 序值)再按 UTF-8 解码;失败返回 None。"""
    raw = bytearray()
    for ch in value:
        try:
            raw += ch.encode("cp1252")
        except UnicodeEncodeError:
            code = ord(ch)
            if code > 0xFF:
                # 真正的非单字节字符(如正常中文) —— 不是双重编码形态
                return None
            raw.append(code)
    try:
        return bytes(raw).decode("utf-8")
    except UnicodeDecodeError:
        return None


def detect_mojibake(value: Optional[str]) -> Optional[str]:
    """判定单值是否为双重编码乱码:是则返回解码后的正常文本,否则返回 None。

    三个条件同时满足才算候选:① 可编回并成功按 UTF-8 解码;② 解码结果与原值不同;
    ③ 解码结果含 CJK。因此纯 ASCII、正常中文、正常 URL 查询串都不会被误判。
    """
    if not value or not isinstance(value, str):
        return None
    candidate = decode_back(value)
    if candidate is None or candidate == value or not has_cjk(candidate):
        return None
    return candidate


def is_sensitive_column(column: str) -> bool:
    """列名是否属敏感列(只报计数、不回显值)。"""
    lowered = column.lower()
    return any(token in lowered for token in SENSITIVE_COLUMN_TOKENS)


def _quote_identifier(name: str) -> str:
    """反引号包裹标识符(表/列名来自 information_schema,非用户输入;仍拒绝含反引号的名字)。"""
    if "`" in name:
        raise SchemaUnreadable("标识符含反引号,拒绝拼接: " + name)
    return "`" + name + "`"


def read_char_columns(conn: Any) -> List[Tuple[str, str]]:
    """读取当前库的全部字符型列(表名, 列名),按表名/列序排序。"""
    from sqlalchemy import bindparam, text

    rows = conn.execute(
        text(
            "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND DATA_TYPE IN :types "
            "ORDER BY TABLE_NAME, ORDINAL_POSITION"
        ).bindparams(bindparam("types", expanding=True)),
        {"types": tuple(CHAR_DATA_TYPES)},
    ).mappings().all()
    return [(row["TABLE_NAME"], row["COLUMN_NAME"]) for row in rows]


def scan_column(conn: Any, table: str, column: str, max_samples: int) -> Dict[str, Any]:
    """流式扫描单列(stream_results 保证内存有界),返回 {hits, total, samples}。"""
    from sqlalchemy import text

    stmt = text("SELECT " + _quote_identifier(column) + " AS v FROM " + _quote_identifier(table))
    hits = 0
    total = 0
    samples: List[Dict[str, str]] = []
    sensitive = is_sensitive_column(column)
    result = conn.execution_options(stream_results=True).execute(stmt)
    try:
        for row in result:
            total += 1
            value = row[0]
            decoded = detect_mojibake(value if isinstance(value, str) else None)
            if decoded is None:
                continue
            hits += 1
            if samples is not None and len(samples) < max_samples and not sensitive:
                samples.append({"value": value, "decoded": decoded})
    finally:
        result.close()
    return {"hits": hits, "total": total, "samples": samples, "sensitive": sensitive}


def gate_exit_code(hit_rows: int, report_only: bool) -> int:
    """门禁退出码:0 无命中 / 1 有命中;`--report-only` 时恒 0。"""
    if report_only:
        return EXIT_OK
    return EXIT_OK if hit_rows == 0 else EXIT_HITS


def _print_gate(payload: Dict[str, Any]) -> None:
    print("ENCODING_GATE " + json.dumps(payload, ensure_ascii=False))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="只读巡检:检测数据层 UTF-8/CP1252 双重编码乱码(数据导入/迁移后应命中 0)"
    )
    parser.add_argument("--report-only", action="store_true", help="仅报告,退出码恒为 0")
    parser.add_argument("--max-samples", type=int, default=MAX_SAMPLES_DEFAULT,
                        help="每个命中列最多回显的样例数(敏感列恒不回显)")
    args = parser.parse_args(argv)

    try:
        from app.core.config import get_settings
        from app.db.engine import engine

        settings = get_settings()
        meta = {"host": settings.DB_HOST, "port": settings.DB_PORT, "database": settings.DB_NAME}
    except Exception as exc:  # noqa: BLE001 - 统一转结构化环境错误
        print("[ERROR] 配置或引擎初始化失败: " + type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        _print_gate({"result": "ERROR", "reason": "engine_unavailable"})
        return EXIT_ENV

    try:
        with engine.connect() as conn:
            columns = read_char_columns(conn)
            if not columns:
                raise SchemaUnreadable("当前库未发现任何字符型列(char/varchar/text 等)")
            scanned_rows = 0
            hit_columns: List[Dict[str, Any]] = []
            for table, column in columns:
                outcome = scan_column(conn, table, column, max(0, args.max_samples))
                scanned_rows += outcome["total"]
                if outcome["hits"]:
                    hit_columns.append({"table": table, "column": column, **outcome})
    except Exception as exc:  # noqa: BLE001 - DB 不可达/权限不足/读取失败一律 exit 2
        print("[ERROR] 实库不可达或结构读取失败: " + type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        _print_gate({"result": "ERROR", "reason": "database_unavailable"})
        return EXIT_ENV

    hit_rows = sum(item["hits"] for item in hit_columns)

    print("=== 数据编码巡检: UTF-8/CP1252 双重编码乱码 ===")
    print("实库: " + meta["database"] + "@" + str(meta["host"]) + ":" + str(meta["port"]) + " (MySQL)")
    print("扫描: " + str(len(columns)) + " 个字符型列 / " + str(scanned_rows) + " 行")
    if not hit_columns:
        print("[PASS] 未发现双重编码乱码(命中 0)")
    else:
        print("[FAIL] 命中列 " + str(len(hit_columns)) + " 个 / 命中行 " + str(hit_rows))
        for item in hit_columns[:MAX_PRINT]:
            label = item["table"] + "." + item["column"]
            print("    - " + label + ": 命中 " + str(item["hits"]) + "/" + str(item["total"]) + " 行")
            if item["sensitive"]:
                print("        (敏感列,按凭据纪律不回显样例值)")
            for sample in item["samples"]:
                print("        样例: " + repr(sample["value"]) + " -> " + repr(sample["decoded"]))
        if len(hit_columns) > MAX_PRINT:
            print("    ... 另有 " + str(len(hit_columns) - MAX_PRINT) + " 个命中列未打印")
        print("[HINT] 根因通常是用非 utf8mb4 客户端字符集导入 UTF-8 数据;" +
              "请用 --default-character-set=utf8mb4 两端导出/导入后重跑本脚本(见 后端技术方案 §8.3)")

    verdict = "PASS" if hit_rows == 0 else "FAIL"
    _print_gate({
        "result": verdict,
        "scanned_columns": len(columns),
        "scanned_rows": scanned_rows,
        "hit_columns": len(hit_columns),
        "hit_rows": hit_rows,
    })
    return gate_exit_code(hit_rows, args.report_only)


if __name__ == "__main__":
    sys.exit(main())
