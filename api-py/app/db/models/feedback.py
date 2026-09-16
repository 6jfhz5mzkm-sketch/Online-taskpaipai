"""商家反馈实体(表 feedback,snake_case 列 -> 响应 camelCase)。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Feedback(Base):
    __tablename__ = "feedback"
    # 与真源 project/scripts/schema.sql 的 KEY idx_merchant_id / idx_status / idx_category / idx_created_at 对齐(仅补 ORM 声明,不改库结构)
    __table_args__ = (
        Index("idx_merchant_id", "merchant_id"),
        Index("idx_status", "status"),
        Index("idx_category", "category"),
        Index("idx_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    content: Mapped[str] = mapped_column(String(1000))
    category: Mapped[str] = mapped_column(String(16), default="其他")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    admin_reply: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    handler_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
