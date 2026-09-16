"""二级任务实体(表 second_level_task,camelCase 列)。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SecondLevelTask(Base):
    __tablename__ = "second_level_task"
    # 与真源 project/scripts/schema.sql 的 UNIQUE KEY IDX_827dce5e14d27c57b8bc5d1cb5(taskId) 对齐(仅补 ORM 声明,不改库结构)
    __table_args__ = (UniqueConstraint("taskId", name="IDX_827dce5e14d27c57b8bc5d1cb5"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    taskId: Mapped[str] = mapped_column(String(32))
    firstLevelTaskId: Mapped[str] = mapped_column(String(32))
    stageId: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    detail: Mapped[str] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(16))
    completionType: Mapped[str] = mapped_column(String(16))
    actionText: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    actionUrl: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    tag: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    defaultCompleted: Mapped[int] = mapped_column(SmallInteger, default=0)
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    sortOrder: Mapped[int] = mapped_column(Integer, default=0)
    createdAt: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now, onupdate=datetime.now)
