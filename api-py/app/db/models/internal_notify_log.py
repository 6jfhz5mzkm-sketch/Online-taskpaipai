"""内部通知发送记录实体(表 internal_notify_log;可观测、可手工重试)。

真源:project/scripts/schema.sql v1.10 / 任务单 #PL-4 方案 §七 + #DB-19(v1.10 补 dedupe_key 去重键;
仅补 ORM 声明,不改库结构)。
与面向商家的 feishu_notification 分表:后者是商家维度 + template_type 枚举 + 48h 频控。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class InternalNotifyLog(Base):
    __tablename__ = "internal_notify_log"
    # 与真源 project/scripts/schema.sql 的 KEY idx_event_created / idx_merchant / idx_event_dedupe 对齐
    # (仅补 ORM 声明,不改库结构)
    __table_args__ = (
        Index("idx_event_created", "event_type", "created_at"),
        Index("idx_merchant", "merchant_id"),
        Index("idx_event_dedupe", "event_type", "dedupe_key", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(32))
    event_type: Mapped[str] = mapped_column(String(32))
    merchant_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_type: Mapped[str] = mapped_column(String(16))
    target: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16))
    error_message: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # 去重键:merchant_registered=merchant_id;jd 重复登记='jd:<jd_merchant_id>'(24h 窗口)
    dedupe_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now)
