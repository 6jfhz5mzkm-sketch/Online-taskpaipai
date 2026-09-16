"""商家经营类目实体(表 merchant_category,merchant 与 category 的多对多中间表)。

真源:project/scripts/schema.sql 的 merchant_category(仅补 ORM 声明,不改库结构)。
该表无 UNIQUE KEY/普通 KEY,只有 PRIMARY KEY。
"""
from datetime import datetime

from sqlalchemy import Integer, SmallInteger, String
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MerchantCategory(Base):
    __tablename__ = "merchant_category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    merchant_id: Mapped[str] = mapped_column(String(64))
    category_id: Mapped[int] = mapped_column(Integer)
    is_primary: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now)
