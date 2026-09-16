"""阶段0连库自检:验证 SQLAlchemy 引擎能连上数据库(不 alter,只读)。

用法: cd api-py && uv run python scripts/check_db.py
"""
import sys
from pathlib import Path

from sqlalchemy import text

# 脚本可独立运行:把 api-py 根加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.engine import engine
from app.core.config import get_settings

settings = get_settings()


def main() -> None:
    with engine.connect() as conn:
        version = conn.execute(text("SELECT VERSION()")).scalar()
        rows = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = :schema ORDER BY table_name"
            ),
            {"schema": settings.DB_NAME},
        ).fetchall()
    tables = [r[0] for r in rows]
    print(f"DB_CONNECT_OK host={settings.DB_HOST} port={settings.DB_PORT} db={settings.DB_NAME}")
    print(f"MySQL version = {version}")
    print(f"table_count   = {len(tables)}")
    for t in tables:
        print(f"  - {t}")


if __name__ == "__main__":
    main()
