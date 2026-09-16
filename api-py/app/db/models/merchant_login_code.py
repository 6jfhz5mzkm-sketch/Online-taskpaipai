"""商家手机号登录验证码实体(表 merchant_login_code;发送/校验审计 + 频控计数)。

真源:project/scripts/schema.sql v1.9 / 任务单 #DB-14(短信改走阿里云 PNVS 短信认证;仅补 ORM 声明,不改库结构)。
验证码由阿里云生成与校验(SendSmsVerifyCode / CheckSmsVerifyCode,ReturnVerifyCode=false,我方不接收明文码),
本表只留发送/校验审计与频控计数,不再存验证码哈希/盐/失效时间。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Index, String
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MerchantLoginCode(Base):
    __tablename__ = "merchant_login_code"
    # 与真源 project/scripts/schema.sql 的 KEY idx_phone_created / idx_ip_created / idx_created 对齐
    # (仅补 ORM 声明,不改库结构)
    __table_args__ = (
        Index("idx_phone_created", "phone", "created_at"),
        Index("idx_ip_created", "ip", "created_at"),
        Index("idx_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String(20))
    biz_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    out_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    attempts: Mapped[int] = mapped_column(default=0)
    used_at: Mapped[Optional[datetime]] = mapped_column(DATETIME(fsp=6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=datetime.now)
