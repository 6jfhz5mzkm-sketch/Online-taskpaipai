"""阶段配置实体(表 stage_config,商家端阶段列表数据源)。"""
from datetime import datetime

from sqlalchemy import BigInteger, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StageConfig(Base):
    __tablename__ = "stage_config"
    # 反向漂移(#DB-1 对账 §5.1):schema.sql 说明实库无 stage_id 唯一索引、迁移 Phase2TaskSeed 对新建库会补 uk_stage_id(键名 uk_stage_id);
    # ORM 按"迁移目标结构"声明该键(当前 dev 库缺该索引,alembic 报 add_constraint,处置见 #PB-5 汇报)
    __table_args__ = (UniqueConstraint("stage_id", name="uk_stage_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stage_id: Mapped[str] = mapped_column(String(32))
    stage_num: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, nullable=True)
    button_text: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    phase_num: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now, onupdate=datetime.now)
