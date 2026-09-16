"""绑定组成员实体(表 merchant_binding_member;解绑=行保留 + active_key 置 NULL)。

真源:project/scripts/schema.sql v1.10 / 任务单 #DB-19 / #PL-7 方案 §4.2(仅补 ORM 声明,不改库结构)。
「一个账号只能在一个活跃组」由 uk_member_active(merchant_id, active_key) 保证;
解绑不删行:active_key 置 NULL + released_at/released_by 留痕(该行即审计)。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Index, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MerchantBindingMember(Base):
    __tablename__ = "merchant_binding_member"
    # 与真源 project/scripts/schema.sql 的 uk_member_active / idx_group_active / idx_merchant_id 对齐
    # (仅补 ORM 声明,不改库结构)
    __table_args__ = (
        UniqueConstraint("merchant_id", "active_key", name="uk_member_active"),
        Index("idx_group_active", "group_id", "active_key"),
        Index("idx_merchant_id", "merchant_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(BigInteger)
    merchant_id: Mapped[str] = mapped_column(String(64))
    active_key: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True, default=1)
    bound_by: Mapped[str] = mapped_column(String(64))
    bound_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now)
    released_at: Mapped[Optional[datetime]] = mapped_column(DATETIME(fsp=6), nullable=True)
    released_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
