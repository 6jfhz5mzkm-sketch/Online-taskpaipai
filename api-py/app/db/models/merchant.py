"""商家实体(表 merchant,登录时 upsert)。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Merchant(Base):
    __tablename__ = "merchant"
    # 与真源 project/scripts/schema.sql 的 UNIQUE KEY uk_merchant_id / uk_feishu_open_id / uk_phone
    # 与 KEY idx_feishu_user_id / idx_status / idx_deleted_at 对齐(仅补 ORM 声明,不改库结构)
    __table_args__ = (
        UniqueConstraint("merchant_id", name="uk_merchant_id"),
        UniqueConstraint("feishu_open_id", name="uk_feishu_open_id"),
        UniqueConstraint("phone", name="uk_phone"),
        Index("idx_feishu_user_id", "feishu_user_id"),
        Index("idx_status", "status"),
        Index("idx_deleted_at", "deleted_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id: Mapped[str] = mapped_column(String(64))
    nickname: Mapped[str] = mapped_column(String(128), default="")
    avatar: Mapped[str] = mapped_column(String(512), default="")
    merchant_name: Mapped[str] = mapped_column(String(256), default="")
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    feishu_open_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    feishu_union_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    feishu_user_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    current_stage: Mapped[str] = mapped_column(String(32), default="onboarding")
    tour_seen: Mapped[int] = mapped_column(default=0)
    welcome_sent: Mapped[int] = mapped_column(default=0)
    data_center_unlocked: Mapped[int] = mapped_column(default=0)
    jd_merchant_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    shop_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[int] = mapped_column(default=1)
    registered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
