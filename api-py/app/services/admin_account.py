"""管理员账号服务(对齐 backend admin-account.service:M1/M3 + #PB-7 追加的 CRUD/重置密码)。"""
import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiException
from app.core.security import hash_password
from app.core.timeutil import to_iso_utc
from app.db.models.admin_account import AdminAccount

_PWD_UPPER = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_PWD_LOWER = "abcdefghijkmnpqrstuvwxyz"
_PWD_DIGITS = "23456789"
_PWD_SYMBOLS = "!@#$%^&*"


def _generate_strong_password() -> str:
    all_chars = _PWD_UPPER + _PWD_LOWER + _PWD_DIGITS + _PWD_SYMBOLS
    chars = [secrets.choice(_PWD_UPPER), secrets.choice(_PWD_LOWER),
             secrets.choice(_PWD_DIGITS), secrets.choice(_PWD_SYMBOLS)]
    while len(chars) < 12:
        chars.append(secrets.choice(all_chars))
    # Fisher-Yates shuffle(对齐 NestJS crypto.randomInt)
    for i in range(len(chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]
    return "".join(chars)


def _row(a: AdminAccount) -> Dict[str, Any]:
    return {
        "id": str(a.id),
        "username": a.username,
        "realName": a.realName,
        "phone": a.phone,
        "email": a.email,
        "role": a.role,
        "status": a.status,
        "lastLoginAt": to_iso_utc(a.lastLoginAt),
        "createdAt": to_iso_utc(a.createdAt),
    }


def find_all(db: Session) -> List[Dict[str, Any]]:
    rows = db.execute(
        select(AdminAccount).where(AdminAccount.deletedAt.is_(None))
        .order_by(AdminAccount.createdAt.asc())
    ).scalars().all()
    return [_row(a) for a in rows]


def _get_entity(db: Session, id: int) -> AdminAccount:
    """取未软删除的管理员实体;不存在抛 404(与 find_one 同口径)。"""
    a = db.execute(
        select(AdminAccount).where(AdminAccount.id == id, AdminAccount.deletedAt.is_(None))
    ).scalar_one_or_none()
    if a is None:
        raise ApiException(f"管理员 {id} 不存在", code=404, status_code=404)
    return a


def find_one(db: Session, id: int) -> Dict[str, Any]:
    return _row(_get_entity(db, id))


def create(db: Session, username: str, password: str, real_name: Optional[str] = None,
           phone: Optional[str] = None, email: Optional[str] = None,
           role: Optional[str] = None) -> Dict[str, Any]:
    """创建管理员(明文密码仅入参,库内只存 hash+salt;对齐 NestJS admin-account.service.create)。"""
    existing = db.execute(select(AdminAccount).where(AdminAccount.username == username)).scalar_one_or_none()
    if existing is not None:
        raise ApiException(f"用户名 {username} 已存在", code=400, status_code=400)
    hash_hex, salt = hash_password(password)
    a = AdminAccount(username=username, passwordHash=hash_hex, salt=salt,
                     realName=real_name or "", phone=phone, email=email,
                     role=role or "admin", status=1)
    db.add(a)
    db.commit()
    db.refresh(a)
    return {"id": str(a.id), "username": a.username, "realName": a.realName, "role": a.role}


# 可更新字段 -> ORM 属性;phone/email 可置 null,其余 NOT NULL 列拒绝显式 null
_UPDATE_FIELDS = {"realName": "realName", "phone": "phone", "email": "email",
                  "role": "role", "status": "status"}
_NULLABLE_FIELDS = ("phone", "email")


def update(db: Session, id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """更新管理员(含角色/状态);只更新请求中出现的键(对齐 NestJS Partial 语义)。"""
    for key, value in data.items():
        if value is None and key not in _NULLABLE_FIELDS:
            raise ApiException(f"管理员字段 {key} 不能为 null", code=400, status_code=400)
    a = _get_entity(db, id)
    for key, attr in _UPDATE_FIELDS.items():
        if key in data:
            setattr(a, attr, data[key])
    db.commit()
    db.refresh(a)
    return _row(a)


def remove(db: Session, id: int) -> Dict[str, Any]:
    """软删除管理员(写 deletedAt,对齐 NestJS softDelete;列表/详情按 deletedAt IS NULL 过滤)。"""
    a = _get_entity(db, id)
    a.deletedAt = datetime.now()
    db.commit()
    return {"success": True}


def reset_password(db: Session, id: int, password: str) -> Dict[str, Any]:
    """重置密码(super_admin 操作;明文不落库)。"""
    a = _get_entity(db, id)
    hash_hex, salt = hash_password(password)
    a.passwordHash = hash_hex
    a.salt = salt
    db.commit()
    return {"success": True}


def generate(db: Session, username: str, realName: Optional[str] = None, phone: Optional[str] = None,
             email: Optional[str] = None, role: Optional[str] = None) -> Dict[str, Any]:
    existing = db.execute(select(AdminAccount).where(AdminAccount.username == username)).scalar_one_or_none()
    if existing is not None:
        raise ApiException(f"用户名 {username} 已存在", code=400, status_code=400)
    password = _generate_strong_password()
    hash_hex, salt = hash_password(password)
    a = AdminAccount(username=username, passwordHash=hash_hex, salt=salt,
                     realName=realName or "", phone=phone, email=email,
                     role=role or "admin", status=1)
    db.add(a)
    db.commit()
    db.refresh(a)
    return {
        "id": str(a.id),
        "username": a.username,
        "realName": a.realName,
        "role": a.role,
        "password": password,
        "note": "密码仅返回一次，请立即保存",
    }
