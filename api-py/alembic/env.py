"""Alembic 迁移环境。

只用于「结构一致校验」(对比 ORM 元数据与数据库),不 alter 生产表(除非新增)。
DB URL 复用 app.core.config 的设置(读 .env),保证与 SQLAlchemy 引擎一致。
"""
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# 确保 api-py 根目录在 sys.path,便于 import app.*
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db import models as _models  # noqa: E402,F401  注册全部 ORM 模型到 Base.metadata(供 Alembic 结构校验)

# Alembic Config 对象,提供 .ini 内配置
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 用应用配置的 DB URL(与 SQLAlchemy 引擎一致)
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

# ORM 元数据(Alembic autogenerate 对照基准;阶段0为空,阶段1起映射实体)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式:仅凭 URL 生成脚本,不连库。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式:连库执行。阶段0仅用于校验,不 alter 生产表。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
