"""资费配置实体(表 fee_config,一个二级类目一套基础资费)。"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FeeConfig(Base):
    __tablename__ = "fee_config"
    # 与真源 project/scripts/schema.sql 的 UNIQUE KEY uk_category(category_id) 对齐
    # (一个二级类目只有一套基础资费;仅补 ORM 声明,不改库结构)
    __table_args__ = (UniqueConstraint("category_id", name="uk_category"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(BigInteger)
    operation_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    transaction_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    deposit_gmv_lt_5w: Mapped[int] = mapped_column(Integer, default=0)
    deposit_gmv_5w_10w: Mapped[int] = mapped_column(Integer, default=0)
    deposit_gmv_10w_30w: Mapped[int] = mapped_column(Integer, default=0)
    deposit_gmv_gte_30w: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DATETIME(fsp=6), nullable=True)
