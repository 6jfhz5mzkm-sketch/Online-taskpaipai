"""管理员账号实体(表 admin_account,camelCase 列)。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdminAccount(Base):
    __tablename__ = "admin_account"
    # 与真源 project/scripts/schema.sql 的 UNIQUE KEY IDX_a6a5b15c5c225de1b4ecbfef9e(username) 对齐(仅补 ORM 声明,不改库结构)
    __table_args__ = (UniqueConstraint("username", name="IDX_a6a5b15c5c225de1b4ecbfef9e"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64))
    passwordHash: Mapped[str] = mapped_column(String(256))
    salt: Mapped[str] = mapped_column(String(64))
    realName: Mapped[str] = mapped_column(String(64), default="")
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    role: Mapped[str] = mapped_column(String(16), default="admin")
    status: Mapped[int] = mapped_column(default=1)
    lastLoginAt: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    lastLoginIp: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now, onupdate=datetime.now)
    deletedAt: Mapped[Optional[datetime]] = mapped_column(DATETIME(fsp=6), nullable=True)
