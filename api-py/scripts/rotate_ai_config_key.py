"""AI 配置密钥轮换脚本:把 `ai_entry_config.api_key_ciphertext` 从旧密钥重加密为新密钥(P7 v1.1 §3.5.5)。

用法:
  cd api-py && uv run python scripts/rotate_ai_config_key.py --old-key <64位hex> --new-key <64位hex> [--dry-run]

口径:
- 入参**显式传参**,不依赖进程 env(避免「改了 .env 但进程未重启」的歧义);
- **幂等**:逐行先试「新密钥可解」→ 可解即跳过(已轮换);否则旧密钥解密 + 新密钥加密写回;
  重复运行安全(第二次 0 变更);
- **逐行独立事务** + `SELECT ... FOR UPDATE` 锁行:单行失败该行保持不变,脚本继续并输出失败清单,
  **退出码非 0**;
- 只做数据重加密:不改表结构、不碰其它表;**不打印密钥原文/密文/新旧密钥本身**。

退出码:0 全部成功(含 0 变更) / 1 存在失败行 / 2 参数或环境错误。
"""
import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.services import ai_crypto  # noqa: E402

EXIT_OK = 0
EXIT_FAILED_ROWS = 1
EXIT_ENV = 2

SELECT_IDS_SQL = "SELECT id FROM ai_entry_config WHERE api_key_ciphertext IS NOT NULL ORDER BY id"
SELECT_ROW_SQL = "SELECT id, entry, api_key_ciphertext FROM ai_entry_config WHERE id = :id FOR UPDATE"
UPDATE_SQL = "UPDATE ai_entry_config SET api_key_ciphertext = :ct WHERE id = :id"


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI 配置密钥轮换(逐行重加密;幂等;支持 --dry-run;只动 ai_entry_config.api_key_ciphertext)")
    parser.add_argument("--old-key", required=True, help="旧密钥(64 位 hex)")
    parser.add_argument("--new-key", required=True, help="新密钥(64 位 hex)")
    parser.add_argument("--dry-run", action="store_true", help="只输出将变更的行,不写库")
    return parser.parse_args(argv)


def _print_list(title: str, rows: List[Tuple[Any, ...]]) -> None:
    print(f"{title}: {len(rows)} 行")
    for row_id, entry, reason in rows:
        print(f"    - id={row_id} entry={entry} {reason}")


def rotate(old_key: bytes, new_key: bytes, dry_run: bool) -> int:
    """逐行重加密。返回退出码(0 成功 / 1 有失败行)。"""
    from app.db.engine import engine

    rotated: List[Tuple[Any, ...]] = []
    skipped: List[Tuple[Any, ...]] = []
    failed: List[Tuple[Any, ...]] = []

    with engine.connect() as conn:
        rows = conn.execute(text(SELECT_IDS_SQL)).all()
    print("待检查行数: " + str(len(rows)) + ("(dry-run:不写库)" if dry_run else ""))

    for (row_id,) in rows:
        try:
            with engine.begin() as conn:                     # 逐行独立事务
                row = conn.execute(text(SELECT_ROW_SQL), {"id": row_id}).mappings().first()
                if row is None or not row["api_key_ciphertext"]:
                    continue
                ciphertext = row["api_key_ciphertext"]
                entry = row["entry"]

                # 幂等:新密钥已可解 -> 该行已轮换,跳过
                try:
                    ai_crypto.decrypt_secret(ciphertext, [new_key])
                    skipped.append((row_id, entry, "already_rotated"))
                    continue
                except ai_crypto.SecretDecryptError:
                    pass

                try:
                    plaintext = ai_crypto.decrypt_secret(ciphertext, [old_key])
                except ai_crypto.SecretDecryptError as exc:
                    failed.append((row_id, entry, "old_key_failed:" + exc.reason))
                    continue

                if dry_run:
                    rotated.append((row_id, entry, "would_rotate"))
                    continue

                conn.execute(text(UPDATE_SQL),
                             {"ct": ai_crypto.encrypt_secret(plaintext, new_key), "id": row_id})
                rotated.append((row_id, entry, "rotated"))
        except Exception as exc:  # noqa: BLE001 - 单行失败不影响其它行
            failed.append((row_id, "?", "error:" + type(exc).__name__))

    print()
    _print_list("已处理(重加密)" if not dry_run else "将变更(dry-run)", rotated)
    _print_list("跳过(已用新密钥)", skipped)
    _print_list("失败(保持不变)", failed)
    if failed:
        print("RESULT: FAILED(存在未处理行,退出码非 0)")
        return EXIT_FAILED_ROWS
    print("RESULT: OK")
    return EXIT_OK


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    old_key = ai_crypto.parse_enc_key(args.old_key)
    new_key = ai_crypto.parse_enc_key(args.new_key)
    if old_key is None or new_key is None:
        print("[ERROR] --old-key / --new-key 必须是 64 位 hex(openssl rand -hex 32)", file=sys.stderr)
        return EXIT_ENV
    if old_key == new_key:
        print("[ERROR] --old-key 与 --new-key 相同,无需轮换", file=sys.stderr)
        return EXIT_ENV
    try:
        return rotate(old_key, new_key, args.dry_run)
    except Exception as exc:  # noqa: BLE001 - DB 不可达等环境错误
        print("[ERROR] 轮换失败(环境错误): " + type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        return EXIT_ENV


if __name__ == "__main__":
    sys.exit(main())
