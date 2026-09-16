"""商家阶段进度实体(表 merchant_stage_progress,snake_case 列)。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MerchantStageProgress(Base):
    __tablename__ = "merchant_stage_progress"
    # 与真源 project/scripts/schema.sql 的 UNIQUE KEY uk_merchant_stage
    # 与 KEY idx_merchant_id / idx_stage_id / idx_status 对齐(仅补 ORM 声明,不改库结构)
    __table_args__ = (
        UniqueConstraint("merchant_id", "stage_id", name="uk_merchant_stage"),
        Index("idx_merchant_id", "merchant_id"),
        Index("idx_stage_id", "stage_id"),
        Index("idx_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id: Mapped[str] = mapped_column(String(64))
    stage_id: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="locked")
    unlocked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
