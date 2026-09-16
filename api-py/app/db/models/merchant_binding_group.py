"""账号绑定组实体(表 merchant_binding_group;1 个京麦商家ID ↔ N 个商家账号,只共享进度)。

真源:project/scripts/schema.sql v1.10 / 任务单 #DB-19 / #PL-7 方案 §4.2(仅补 ORM 声明,不改库结构)。
「一个 jd_merchant_id 只能有一个活跃组」由 uk_group_active(jd_merchant_id, active_key) 保证:
active_key=1 活跃 / NULL 已关闭(MySQL 唯一索引允许多个 NULL → 保留历史组行)。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Index, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MerchantBindingGroup(Base):
    __tablename__ = "merchant_binding_group"
    # 与真源 project/scripts/schema.sql 的 uk_group_active / idx_jd_merchant_id 对齐
    # (仅补 ORM 声明,不改库结构)
    __table_args__ = (
        UniqueConstraint("jd_merchant_id", "active_key", name="uk_group_active"),
        Index("idx_jd_merchant_id", "jd_merchant_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    jd_merchant_id: Mapped[str] = mapped_column(String(64))
    active_key: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True, default=1)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DATETIME(fsp=6), nullable=True)
    closed_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
