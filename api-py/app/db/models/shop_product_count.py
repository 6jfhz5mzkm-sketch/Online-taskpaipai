"""商品数量(表 shop_product_count,snake_case)。"""
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class ShopProductCount(Base):
    __tablename__ = "shop_product_count"
    # 与真源 project/scripts/schema.sql 的 UNIQUE KEY uk_merchant_date 与 KEY idx_merchant_id 对齐(仅补 ORM 声明,不改库结构)
    __table_args__ = (
        UniqueConstraint("merchant_id", "data_date", name="uk_merchant_date"),
        Index("idx_merchant_id", "merchant_id"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id: Mapped[str] = mapped_column(String(64))
    total_count: Mapped[Optional[int]] = mapped_column(nullable=True)
    on_sale_count: Mapped[Optional[int]] = mapped_column(nullable=True)
    off_sale_count: Mapped[Optional[int]] = mapped_column(nullable=True)
    audit_count: Mapped[Optional[int]] = mapped_column(nullable=True)
    data_date: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
