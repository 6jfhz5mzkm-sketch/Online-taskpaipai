"""类目资质要求实体(表 category_requirement,每个一级类目一套入驻资质)。

列名策略:snake_case 表按实际列名映射;service 出参时转 camelCase 对齐 NestJS。
"""
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, BigInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CategoryRequirement(Base):
    __tablename__ = "category_requirement"
    # 与真源 project/scripts/schema.sql 的 UNIQUE KEY IDX_d9d61d087ba3eded1ec4086dc0(category_id) 对齐(仅补 ORM 声明,不改库结构)
    __table_args__ = (UniqueConstraint("category_id", name="IDX_d9d61d087ba3eded1ec4086dc0"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    category_id: Mapped[int] = mapped_column(BigInteger, default=0)
    shop_type: Mapped[str] = mapped_column(String(50), default="专营店")
    shop_name_rule: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    requirements: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 列类型 json
    review_focus: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now, onupdate=datetime.now)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DATETIME(fsp=6), nullable=True)
