"""品牌资费覆盖实体(表 fee_brand_override,部分品牌在特定类目下费率不同)。"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Numeric, String
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FeeBrandOverride(Base):
    __tablename__ = "fee_brand_override"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(BigInteger)
    brand_name: Mapped[str] = mapped_column(String(128))
    operation_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    transaction_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    is_active: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DATETIME(fsp=6), nullable=True)
