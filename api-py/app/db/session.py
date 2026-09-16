"""FastAPI 依赖:数据库会话。

在路由/服务里注入 `db: Session = Depends(get_db)`,请求结束自动关闭。
"""
from typing import Generator

from sqlalchemy.orm import Session

from app.db.engine import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
