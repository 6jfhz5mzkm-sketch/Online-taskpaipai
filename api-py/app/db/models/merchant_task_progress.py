"""商家任务进度实体(表 merchant_task_progress,camelCase 列)。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MerchantTaskProgress(Base):
    __tablename__ = "merchant_task_progress"
    # 与真源 project/scripts/schema.sql 的 UNIQUE KEY uk_merchant_task(merchantId, taskId) 对齐
    # (schema.sql v1.3 / #DB-1 新增键:保证一个商家对一个二级任务只有一条进度记录;仅补 ORM 声明,不改库结构)
    __table_args__ = (UniqueConstraint("merchantId", "taskId", name="uk_merchant_task"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    merchantId: Mapped[str] = mapped_column(String(64))
    taskId: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    completedAt: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now, onupdate=datetime.now)
