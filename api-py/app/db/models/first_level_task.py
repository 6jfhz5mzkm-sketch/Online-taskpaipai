"""一级任务实体(表 first_level_task,camelCase 列)。"""
from datetime import datetime

from sqlalchemy import BigInteger, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FirstLevelTask(Base):
    __tablename__ = "first_level_task"
    # 与真源 project/scripts/schema.sql 的 UNIQUE KEY IDX_61f121d89996f7548b239af555(taskId) 对齐(仅补 ORM 声明,不改库结构)
    __table_args__ = (UniqueConstraint("taskId", name="IDX_61f121d89996f7548b239af555"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    taskId: Mapped[str] = mapped_column(String(32))
    stageId: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    buttonText: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    sortOrder: Mapped[int] = mapped_column(Integer, default=0)
    createdAt: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now)
    updatedAt: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now, onupdate=datetime.now)
