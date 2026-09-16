"""AI 配置修改审计实体(表 admin_ai_config_audit)。

真源:project/scripts/schema.sql v1.7 / P7 v1.1 §3.2(仅补 ORM 声明,不改库结构)。
密钥类字段只留掩码(old/new_display)、长度(old/new_len)与指纹(old/new_fp),
**绝不落密钥原文与密文**;非密钥字段记原值新旧以追责。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AdminAiConfigAudit(Base):
    __tablename__ = "admin_ai_config_audit"
    # 与真源 KEY idx_entry_created(entry, created_at) / idx_admin_created(admin_id, created_at) 对齐
    __table_args__ = (
        Index("idx_entry_created", "entry", "created_at"),
        Index("idx_admin_created", "admin_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entry: Mapped[str] = mapped_column(String(32))
    field: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(16))
    old_display: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    new_display: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    old_len: Mapped[Optional[int]] = mapped_column(nullable=True)
    new_len: Mapped[Optional[int]] = mapped_column(nullable=True)
    old_fp: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    new_fp: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    admin_id: Mapped[int] = mapped_column(BigInteger)
    admin_username: Mapped[str] = mapped_column(String(64))
    ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now)
