"""验证码 2.0 每日调用计数实体(表 captcha_daily_counter;成本闸 C7)。

真源:project/scripts/schema.sql v1.8 / 任务单 #PL-4 方案 §五 C7 + §十四 G-4
(仅补 ORM 声明,不改库结构)。G-4 裁定不建 append-only 调用日志,改为按天聚合:
靠 INSERT ... ON DUPLICATE KEY UPDATE used = used + 1 原子自增;1 行/天、天然有界、无需清理任务。
"""
from datetime import date, datetime

from sqlalchemy import Date
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CaptchaDailyCounter(Base):
    __tablename__ = "captcha_daily_counter"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    used: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now, onupdate=datetime.now)
