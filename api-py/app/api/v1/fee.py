"""资费路由(对齐 NestJS fee.controller:/fee/detail)。"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_merchant
from app.core.response import success
from app.db.session import get_db
from app.services.fee import get_fee_detail

router = APIRouter(prefix="/fee", tags=["资费"])


@router.get("/detail", summary="查询资费详情", dependencies=[Depends(get_current_merchant)])
def fee_detail(
    category_id: str = Query(..., description="二级类目ID"),
    brand_name: Optional[str] = Query(default=None, description="品牌名称,查询品牌特殊资费"),
    db: Session = Depends(get_db),
) -> dict:
    cid = int(category_id) if category_id.strip().isdigit() else 0
    return success(get_fee_detail(db, cid, brand_name))
