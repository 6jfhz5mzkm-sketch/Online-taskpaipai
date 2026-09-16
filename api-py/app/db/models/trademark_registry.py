"""商标注册号实体(表 trademark_registry,brand_name + registration_number 唯一)。"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TrademarkRegistry(Base):
    __tablename__ = "trademark_registry"
    # 与真源 project/scripts/schema.sql 的 UNIQUE KEY uk_brand_number(brand_name, registration_number) 对齐;
    # 仅补齐 ORM 声明(库结构已存在该唯一键,不改库结构),避免 alembic autogenerate 出 schema diff。
    __table_args__ = (UniqueConstraint("brand_name", "registration_number", name="uk_brand_number"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    brand_name: Mapped[str] = mapped_column(String(128))
    registration_number: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)
