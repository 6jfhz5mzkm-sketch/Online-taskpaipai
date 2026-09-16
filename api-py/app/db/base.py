"""SQLAlchemy ORM 声明基类。

阶段1起在此注册实体,供 Alembic 做结构一致校验(只校验不 alter 生产表)。
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有 ORM 模型基类。"""
