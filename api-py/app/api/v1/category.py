"""类目路由(对齐 NestJS category.controller:/category/list + /category/:id)。"""
from typing import Dict, Optional

from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session

from app.api.deps import get_current_merchant
from app.core.response import success
from app.db.session import get_db
from app.services.category import get_category_detail, get_category_list
from app.services.category_requirement import find_by_category_id as find_category_requirement

router = APIRouter(prefix="/category", tags=["类目"])


@router.get("/list", summary="查询类目列表", dependencies=[Depends(get_current_merchant)])
def category_list(
    parent_id: Optional[str] = Query(default=None, description="父类目ID,不传返回一级,传了返回二级"),
    db: Session = Depends(get_db),
) -> dict:
    pid: Optional[int] = None
    if parent_id is not None and parent_id.strip().isdigit():
        pid = int(parent_id)
    return success(get_category_list(db, pid))


@router.get("/requirement/{categoryId}", summary="获取类目入驻资质要求(API-16)", dependencies=[Depends(get_current_merchant)])
def category_requirement(categoryId: int = Path(..., description="类目ID"), db: Session = Depends(get_db)) -> dict:
    return success(find_category_requirement(db, categoryId))


@router.get("/{id}", summary="查询类目详情", dependencies=[Depends(get_current_merchant)])
def category_detail(id: int = Path(..., description="类目ID"), db: Session = Depends(get_db)) -> dict:
    return success(get_category_detail(db, id))
