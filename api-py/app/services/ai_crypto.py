"""AI 后台配置的密钥加密封装(AES-256-GCM;P7 v1.1 §3.5)——唯一实现。

密文格式:`v1:` + base64( nonce(12) ‖ tag(16) ‖ ciphertext ),单列自包含。
密钥来源:env `AI_CONFIG_ENC_KEY`(64 位 hex = 32 字节);轮换窗口的旧密钥槽位 `AI_CONFIG_ENC_KEY_PREVIOUS`。
读取:按 主密钥 → 前一密钥 顺序尝试解密;全部失败时按原因枚举抛 `SecretDecryptError`,
      由调用方(ai_config 服务层)**回落 env**(绝不 500、绝不在读取路径抛给用户)。
写入:密钥不可用时由服务层拒绝(400「加密密钥未配置或非法，无法保存密钥」),不写库、不写审计。

凭据纪律:本模块任何返回值/日志都不得包含密钥原文、密文、ENC key 或其 hash(掩码与指纹除外)。
"""
import base64
import hashlib
import logging
import os
import re
from typing import List, Optional, Sequence

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger("api")

CIPHERTEXT_PREFIX = "v1:"
NONCE_BYTES = 12
TAG_BYTES = 16
MIN_CIPHERTEXT_BYTES = NONCE_BYTES + TAG_BYTES

ENC_KEY_ENV = "AI_CONFIG_ENC_KEY"
ENC_KEY_PREVIOUS_ENV = "AI_CONFIG_ENC_KEY_PREVIOUS"

# 64 位 hex = 32 字节(与项目既有 JWT secret 口径一致:openssl rand -hex 32)
_ENC_KEY_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
# 掩码形态(前 ≤8 任意 + 4 星 + 后 ≤8):用于拒绝把掩码当新 key 写回
MASK_PATTERN = re.compile(r"^.{0,8}\*{4}.{0,8}$")

# 失败原因枚举(日志与接口 apiKeyStatus 统一使用)
REASON_KEY_MISSING = "enc_key_missing"
REASON_KEY_INVALID = "enc_key_invalid"
REASON_TAG_MISMATCH = "auth_tag_mismatch"
REASON_FORMAT_INVALID = "format_invalid"
REASON_OK = "ok"


class SecretDecryptError(Exception):
    """解密失败。`reason` ∈ {enc_key_missing, enc_key_invalid, auth_tag_mismatch, format_invalid}。"""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def is_valid_enc_key(value: Optional[str]) -> bool:
    """是否形如 64 位 hex(非空且匹配)。"""
    return bool(value) and bool(_ENC_KEY_PATTERN.match(str(value).strip()))


def parse_enc_key(value: Optional[str]) -> Optional[bytes]:
    """把 64 位 hex 解析为 32 字节密钥;非法返回 None(不抛,交由调用方按原因降级)。"""
    if not is_valid_enc_key(value):
        return None
    try:
        key = bytes.fromhex(str(value).strip())
    except ValueError:
        return None
    return key if len(key) == 32 else None


def load_enc_keys() -> List[bytes]:
    """按 主密钥 → 前一密钥 顺序返回**可用**密钥(缺失/非法的槽位跳过)。"""
    from app.core.config import get_settings

    settings = get_settings()
    keys: List[bytes] = []
    for raw in (settings.AI_CONFIG_ENC_KEY, settings.AI_CONFIG_ENC_KEY_PREVIOUS):
        key = parse_enc_key(raw)
        if key is not None:
            keys.append(key)
    return keys


def enc_key_state() -> str:
    """主密钥槽位状态:`ok` / `enc_key_missing` / `enc_key_invalid`(写路径据此拒绝并给原因)。"""
    from app.core.config import get_settings

    raw = get_settings().AI_CONFIG_ENC_KEY
    if raw is None or not str(raw).strip():
        return REASON_KEY_MISSING
    return REASON_OK if parse_enc_key(raw) is not None else REASON_KEY_INVALID


def encrypt_secret(plaintext: str, key: bytes) -> str:
    """加密为 `v1:` + base64(nonce‖tag‖ciphertext);同一原文两次加密结果不同(随机 nonce)。"""
    nonce = os.urandom(NONCE_BYTES)
    sealed = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    body, tag = sealed[:-TAG_BYTES], sealed[-TAG_BYTES:]
    return CIPHERTEXT_PREFIX + base64.b64encode(nonce + tag + body).decode("ascii")


def decrypt_secret(ciphertext: str, keys: Sequence[bytes]) -> str:
    """按给定密钥顺序解密;失败抛 `SecretDecryptError`(带原因枚举)。"""
    if not ciphertext or not str(ciphertext).startswith(CIPHERTEXT_PREFIX):
        raise SecretDecryptError(REASON_FORMAT_INVALID)
    if not keys:
        raise SecretDecryptError(REASON_KEY_MISSING)
    try:
        raw = base64.b64decode(str(ciphertext)[len(CIPHERTEXT_PREFIX):], validate=True)
    except Exception:  # noqa: BLE001 - base64 非法一律归格式错误
        raise SecretDecryptError(REASON_FORMAT_INVALID)
    if len(raw) < MIN_CIPHERTEXT_BYTES:
        raise SecretDecryptError(REASON_FORMAT_INVALID)

    nonce = raw[:NONCE_BYTES]
    tag = raw[NONCE_BYTES:NONCE_BYTES + TAG_BYTES]
    body = raw[NONCE_BYTES + TAG_BYTES:]
    last_reason = REASON_TAG_MISMATCH
    for key in keys:
        try:
            return AESGCM(key).decrypt(nonce, body + tag, None).decode("utf-8")
        except InvalidTag:
            last_reason = REASON_TAG_MISMATCH
        except Exception:  # noqa: BLE001 - 其它异常视为格式/内容异常
            last_reason = REASON_FORMAT_INVALID
    raise SecretDecryptError(last_reason)


def plaintext_length_from_ciphertext(ciphertext: Optional[str]) -> Optional[int]:
    """由密文长度反推原文长度(纯长度运算,**不需要密钥、不接触原文**)。

    封装为 nonce(12) ‖ tag(16) ‖ ciphertext,故 原文长度 = 解码后字节数 - 28。
    用途:审计 `old_len`(口径 ④ 允许记录长度);非法/缺失返回 None。
    """
    if not ciphertext or not str(ciphertext).startswith(CIPHERTEXT_PREFIX):
        return None
    try:
        raw_len = len(base64.b64decode(str(ciphertext)[len(CIPHERTEXT_PREFIX):], validate=True))
    except Exception:  # noqa: BLE001
        return None
    length = raw_len - MIN_CIPHERTEXT_BYTES
    return length if length >= 0 else None


def fingerprint(plaintext: str) -> str:
    """`sha256(原文)` 前 16 位 hex(不可逆;仅用于同一性判断与轮换排障)。"""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()[:16]


def mask_secret(value: Optional[str]) -> Optional[str]:
    """密钥掩码:长度 ≥12 保留前 3 + `****` + 后 4;否则固定 `****`(不暴露任何字符)。"""
    if not value:
        return None
    return (value[:3] + "****" + value[-4:]) if len(value) >= 12 else "****"


def looks_like_mask(value: str) -> bool:
    """是否形如掩码(用于拒绝把掩码当新 key 写回)。"""
    return bool(MASK_PATTERN.match(value or ""))
