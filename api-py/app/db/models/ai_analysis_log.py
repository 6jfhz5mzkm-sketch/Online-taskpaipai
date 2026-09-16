"""AI 调用审计/限流日志(表 ai_analysis_log,snake_case)。"""
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class AiAnalysisLog(Base):
    __tablename__ = "ai_analysis_log"
    # 与真源 project/scripts/schema.sql 的 KEY idx_merchant_created / idx_type_merchant_created 对齐(仅补 ORM 声明,不改库结构)
    __table_args__ = (
        Index("idx_merchant_created", "merchant_id", "created_at"),
        Index("idx_type_merchant_created", "type", "merchant_id", "created_at"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id: Mapped[str] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(16), default="analysis")
    status: Mapped[str] = mapped_column(String(16))
    error_message: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
