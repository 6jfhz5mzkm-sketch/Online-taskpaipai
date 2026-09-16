"""埋点事件实体(表 event_log,snake_case 列)。"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EventLog(Base):
    __tablename__ = "event_log"
    # 与真源 project/scripts/schema.sql 的 KEY idx_merchant_id / idx_event_type / idx_created_at / idx_page_name / idx_task_key 对齐(仅补 ORM 声明,不改库结构)
    __table_args__ = (
        Index("idx_merchant_id", "merchant_id"),
        Index("idx_event_type", "event_type"),
        Index("idx_created_at", "created_at"),
        Index("idx_page_name", "page_name"),
        Index("idx_task_key", "task_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64))
    page_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    task_key: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    stage_key: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    element: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    # 原为 mapped_column("meta", nullable=True)(无类型参数 -> String(),length=None),
    # 是 compare_type=True 下 CompileError 的最后根因(#PB-13 / R2);真源列类型为 JSON,
    # 应用侧一直以 JSON 文本写入(event_core.track 先 json.dumps),故声明 Text 保持行为不变。
    meta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
