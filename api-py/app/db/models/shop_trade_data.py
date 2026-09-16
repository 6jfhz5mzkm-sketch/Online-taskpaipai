"""交易数据(表 shop_trade_data,snake_case)。"""
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class ShopTradeData(Base):
    __tablename__ = "shop_trade_data"
    # 与真源 project/scripts/schema.sql 的 UNIQUE KEY uk_merchant_date_range 与 KEY idx_merchant_id 对齐(仅补 ORM 声明,不改库结构)
    __table_args__ = (
        UniqueConstraint("merchant_id", "data_date", "time_range", name="uk_merchant_date_range"),
        Index("idx_merchant_id", "merchant_id"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id: Mapped[str] = mapped_column(String(64))
    trade_amount: Mapped[Optional[float]] = mapped_column(nullable=True)
    trade_orders: Mapped[Optional[int]] = mapped_column(nullable=True)
    trade_customers: Mapped[Optional[int]] = mapped_column(nullable=True)
    shop_visitors: Mapped[Optional[int]] = mapped_column(nullable=True)
    shop_page_views: Mapped[Optional[int]] = mapped_column(nullable=True)
    trade_items: Mapped[Optional[int]] = mapped_column(nullable=True)
    conversion_rate: Mapped[Optional[float]] = mapped_column(nullable=True)
    customer_unit_price: Mapped[Optional[float]] = mapped_column(nullable=True)
    avg_stay_duration: Mapped[Optional[float]] = mapped_column(nullable=True)
    cart_customers: Mapped[Optional[int]] = mapped_column(nullable=True)
    cart_items: Mapped[Optional[int]] = mapped_column(nullable=True)
    cart_conversion_rate: Mapped[Optional[float]] = mapped_column(nullable=True)
    data_date: Mapped[str] = mapped_column(String(10))
    time_range: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
