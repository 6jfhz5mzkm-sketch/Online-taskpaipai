"""店铺星级数据(表 shop_star_data,snake_case)。"""
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, Date, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class ShopStarData(Base):
    __tablename__ = "shop_star_data"
    # 与真源 project/scripts/schema.sql 的 UNIQUE KEY uk_merchant_date 与 KEY idx_merchant_id 对齐(仅补 ORM 声明,不改库结构)
    __table_args__ = (
        UniqueConstraint("merchant_id", "data_date", name="uk_merchant_date"),
        Index("idx_merchant_id", "merchant_id"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id: Mapped[str] = mapped_column(String(64))
    shop_star: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    service_score: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    logistics_score: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    after_sale_score: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    product_score: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    data_date: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
