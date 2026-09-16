"""AI 分入口配置实体(表 ai_entry_config;密钥密文存储,缺省字段回落 env)。

真源:project/scripts/schema.sql v1.7 / P7 v1.1 §3.1(仅补 ORM 声明,不改库结构)。
一入口一行(UNIQUE KEY uk_entry);字段为 NULL = 回落 env 同名字段;
密钥**只存密文 + 不可逆指纹**,不存在明文列。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AiEntryConfig(Base):
    __tablename__ = "ai_entry_config"
    # 与真源 project/scripts/schema.sql 的 UNIQUE KEY uk_entry(entry) 对齐(仅补 ORM 声明,不改库结构)
    __table_args__ = (UniqueConstraint("entry", name="uk_entry"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entry: Mapped[str] = mapped_column(String(32))
    enabled: Mapped[int] = mapped_column(SmallInteger, default=1)
    api_key_ciphertext: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    api_key_fingerprint: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    base_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    timeout_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    max_tokens: Mapped[Optional[int]] = mapped_column(nullable=True)
    daily_limit: Mapped[Optional[int]] = mapped_column(nullable=True)
    updated_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now, onupdate=datetime.now)
