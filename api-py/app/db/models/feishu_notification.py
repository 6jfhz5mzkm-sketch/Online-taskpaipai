"""飞书通知实体(表 feishu_notification,一条消息的完整生命周期记录)。

真源:project/scripts/schema.sql 的 feishu_notification(仅补 ORM 声明,不改库结构)。
设计说明:追踪消息从发送到被阅读的全过程,用于频率控制与打开率统计。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FeishuNotification(Base):
    __tablename__ = "feishu_notification"
    # 与真源 project/scripts/schema.sql 的 KEY idx_merchant_id / idx_template_type / idx_sent_at
    # / idx_status / idx_deleted_at 对齐(仅补 ORM 声明,不改库结构)
    __table_args__ = (
        Index("idx_merchant_id", "merchant_id"),
        Index("idx_template_type", "template_type"),
        Index("idx_sent_at", "sent_at"),
        Index("idx_status", "status"),
        Index("idx_deleted_at", "deleted_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id: Mapped[str] = mapped_column(String(64))
    template_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(256))
    content: Mapped[str] = mapped_column(Text)
    h5_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="sent")
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_msg: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
