"""商标路由(对齐 NestJS trademark.controller:/trademark/search,需阶段二解锁)。"""
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_merchant
from app.core.response import success
from app.db.session import get_db
from app.services.trademark import search

router = APIRouter(prefix="/trademark", tags=["商标查询"])


@router.get("/search", summary="模糊搜索商标注册号")
def trademark_search(
    keyword: str = Query(..., min_length=1, description="搜索关键词"),
    merchant: Dict[str, Any] = Depends(get_current_merchant),
    db: Session = Depends(get_db),
) -> dict:
    return success(search(db, keyword, merchant["merchant_id"]))
