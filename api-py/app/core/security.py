"""认证与安全工具。

对齐 NestJS:
- 商家 JWT(secret=JWT_SECRET):payload {merchant_id, role:'merchant'},HS256,过期 JWT_EXPIRES_IN
- 管理员 JWT(secret=ADMIN_JWT_SECRET):payload {sub, username, role},HS256,过期 ADMIN_JWT_EXPIRES_IN
- 密码哈希:pbkdf2-sha512, 10000 迭代, 64 字节(与 backend admin-auth.service 完全一致)
"""
import hashlib
import hmac
import secrets
import time
from typing import Any, Dict, List, Tuple

from jose import jwt

from app.core.config import get_settings

settings = get_settings()

# 密码哈希参数(SEC-04:迭代升级 10000 -> 210000 对齐 OWASP;平滑迁移兼容存量 10000 哈希)
PBKDF2_ALGO = "sha512"
PBKDF2_ITERATIONS = 210000
LEGACY_PBKDF2_ITERATIONS = 10000   # 存量旧格式账号(无版本前缀)用,迁移前(旧代码)写入的哈希
PBKDF2_DKLEN = 64
HASH_PREFIX = "pbkdf2_sha512"       # 冗余字段,供平滑迁移识别


def create_token(
    payload: Dict[str, Any],
    secret: str,
    expires_in: int,
    algorithm: str = "HS256",
) -> str:
    """签发 JWT(payload + iat/exp)。"""
    now = int(time.time())
    data = {**payload, "iat": now, "exp": now + expires_in}
    return jwt.encode(data, secret, algorithm=algorithm)


def create_merchant_token(merchant_id: str) -> str:
    """签发商家 token(secret=JWT_SECRET)。"""
    return create_token(
        {"merchant_id": merchant_id, "role": "merchant"},
        secret=settings.JWT_SECRET,
        expires_in=settings.JWT_EXPIRES_IN,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_admin_token(admin_id: int, username: str, role: str) -> str:
    """签发管理员 token(secret=ADMIN_JWT_SECRET)。"""
    return create_token(
        {"sub": str(admin_id), "username": username, "role": role},
        secret=settings.ADMIN_JWT_SECRET,
        expires_in=settings.ADMIN_JWT_EXPIRES_IN,
        algorithm=settings.ADMIN_JWT_ALGORITHM,
    )


def decode_token(token: str, secret: str, algorithms: List[str]) -> Dict[str, Any]:
    """校验并解析 JWT(带签名与过期校验);失败抛 jose.JWTError。

    注意:NestJS 签发的 admin token 中 sub 为数字(python-jose 默认要求字符串),
    故关闭 sub 类型校验,签名/过期仍严格校验,sub 存在性由调用方自行检查。
    """
    return jwt.decode(token, secret, algorithms=algorithms, options={"verify_sub": False})


def _pbkdf2(password: str, salt: str, iterations: int) -> str:
    """按指定迭代数计算 pbkdf2-sha512(64 字节)hex。"""
    return hashlib.pbkdf2_hmac(
        PBKDF2_ALGO, password.encode("utf-8"), salt.encode("utf-8"),
        iterations, PBKDF2_DKLEN,
    ).hex()


def hash_password(password: str) -> Tuple[str, str]:
    """生成密码哈希,返回 (encoded, salt_hex)。encoded 含版本+迭代数+盐+哈希,供平滑迁移校验。

    格式:pbkdf2_sha512$<iter>$<salt>$<hash>(约 181 字符,passwordHash VARCHAR(256) 足够,无需扩容)。
    """
    salt = secrets.token_hex(16)  # 32 位 hex
    hash_hex = _pbkdf2(password, salt, PBKDF2_ITERATIONS)
    encoded = HASH_PREFIX + "$" + str(PBKDF2_ITERATIONS) + "$" + salt + "$" + hash_hex
    return encoded, salt


def verify_password(password: str, stored: str, salt: str) -> bool:
    """校验密码:按存储哈希实际使用的迭代数重算(平滑迁移)。

    - 新格式(含 pbkdf2_sha512$ 前缀):解析出迭代数/盐/哈希,用该迭代数校验;
    - 旧格式(纯 hex,无前缀):存量账号(10000 迭代写入),用 LEGACY_PBKDF2_ITERATIONS + salt 列校验(不失效)。
    """
    if stored and stored.startswith(HASH_PREFIX + "$"):
        parts = stored.split("$")
        if len(parts) != 4:
            return False
        _prefix, iter_str, h_salt, h_hash = parts
        try:
            iterations = int(iter_str)
        except ValueError:
            return False
        computed = _pbkdf2(password, h_salt, iterations)
        return hmac.compare_digest(computed, h_hash)
    # 旧格式
    computed = _pbkdf2(password, salt, LEGACY_PBKDF2_ITERATIONS)
    return hmac.compare_digest(computed, stored)


def needs_rehash(stored: str) -> bool:
    """平滑升级:旧格式(无前缀)或迭代数 < 当前 -> True,验证成功后应立即用 210000 重哈希升级。"""
    if not stored or not stored.startswith(HASH_PREFIX + "$"):
        return True
    parts = stored.split("$")
    if len(parts) != 4:
        return True
    try:
        return int(parts[1]) < PBKDF2_ITERATIONS
    except ValueError:
        return True
