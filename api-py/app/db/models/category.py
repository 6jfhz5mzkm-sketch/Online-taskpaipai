"""类目实体(表 category,两级结构,parent_id=0 为一级)。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, SmallInteger, String
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Category(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = mapped_column(BigInteger, default=0)
    name: Mapped[str] = mapped_column(String(128))
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    is_active: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DATETIME(fsp=6), nullable=True)
