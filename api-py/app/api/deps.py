"""FastAPI 鉴权依赖。

对齐 NestJS:
- get_current_merchant: 商家 token(JWT_SECRET),payload {merchant_id, role}
- get_current_admin: 管理员 token(ADMIN_JWT_SECRET),并校验库中管理员存在且启用(status=1)
- require_roles: 角色守卫(对齐 AdminRolesGuard + @Roles),角色不匹配抛 403
"""
from typing import Any, Callable, Dict, Optional

from fastapi import Depends, Header
from jose import JWTError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ApiException
from app.core.security import decode_token
from app.db.session import get_db

settings = get_settings()


def _extract_bearer(authorization: Optional[str]) -> str:
    """从 Authorization: Bearer <token> 中取 token;缺失/格式错误抛 401。"""
    if not authorization:
        raise ApiException("未登录或 Token 已过期", code=401, status_code=401)
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise ApiException("未登录或 Token 已过期", code=401, status_code=401)
    return parts[1].strip()


def get_current_merchant(
    authorization: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """商家鉴权:解析 Bearer token,校验 JWT_SECRET 签名与过期,返回 {merchant_id, role}。"""
    token = _extract_bearer(authorization)
    try:
        payload = decode_token(token, settings.JWT_SECRET, [settings.JWT_ALGORITHM])
    except JWTError:
        raise ApiException("未登录或 Token 已过期", code=401, status_code=401)
    merchant_id = payload.get("merchant_id")
    if not merchant_id:
        raise ApiException("Token 无效", code=401, status_code=401)
    return {"merchant_id": merchant_id, "role": payload.get("role", "merchant")}


def get_current_admin(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """管理员鉴权:解析 Bearer token,校验 ADMIN_JWT_SECRET 签名与过期,并核对库中管理员存在且启用。"""
    token = _extract_bearer(authorization)
    try:
        payload = decode_token(token, settings.ADMIN_JWT_SECRET, [settings.ADMIN_JWT_ALGORITHM])
    except JWTError:
        raise ApiException("未登录或 Token 已过期", code=401, status_code=401)
    sub = payload.get("sub")
    if sub is None:
        raise ApiException("Token 无效", code=401, status_code=401)
    try:
        admin_id = int(sub)
    except (TypeError, ValueError):
        raise ApiException("Token 无效", code=401, status_code=401)
    # 对齐 NestJS AdminJwtStrategy.validateToken:按 id 查库并校验 status=1
    # deletedAt IS NULL:软删除的管理员(见 DELETE /api/admin/account/{id})不得继续持旧 token 通行
    row = db.execute(
        text("SELECT id, username, role, status, realName FROM admin_account "
             "WHERE id = :id AND deletedAt IS NULL"),
        {"id": admin_id},
    ).mappings().first()
    if row is None or row["status"] != 1:
        raise ApiException("管理员不存在或已禁用", code=401, status_code=401)
    return {
        "sub": row["id"],
        "username": row["username"],
        "role": row["role"],
        "realName": row["realName"],
    }


def require_roles(*allowed_roles: str) -> Callable:
    """角色守卫(对齐 AdminRolesGuard + @Roles)。

    返回一个 FastAPI 依赖:先 get_current_admin 做认证,再校验 role ∈ allowed_roles,
    否则抛 403。调用方式: Depends(require_roles("super_admin", "admin"))。
    """
    def _guard(admin: Dict[str, Any] = Depends(get_current_admin)) -> Dict[str, Any]:
        if admin["role"] not in allowed_roles:
            raise ApiException("无权限执行该操作", code=403, status_code=403)
        return admin
    return _guard
