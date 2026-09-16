"""SQLAlchemy 引擎与会话工厂。

连接参数来自 app.core.config(读 .env:DB_HOST/DB_PORT/DB_USER/DB_PASS/DB_NAME)。
"""
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()

# pool_pre_ping: 连接前 ping,避免 MySQL 空闲断开;pool_recycle: 定期回收。
engine: Engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.DB_ECHO,
    # 显式指定连接字符集 utf8mb4(仅 URL ?charset 在 PyMySQL 下可能不生效,必须 connect_args 传入,否则中文读出双重编码乱码)
    connect_args={"charset": "utf8mb4"},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
