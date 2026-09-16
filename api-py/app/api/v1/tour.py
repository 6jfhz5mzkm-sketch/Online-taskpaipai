"""新手引导路由(对齐 NestJS tour.controller)。"""
from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_merchant
from app.core.response import success, success_response
from app.db.session import get_db
from app.services.tour import get_seen, mark_seen, reset_seen

router = APIRouter(prefix="/tour", tags=["新手引导"])


@router.get("/seen", summary="查询是否已看新手引导")
def seen(merchant: Dict[str, Any] = Depends(get_current_merchant), db: Session = Depends(get_db)):
    return success(get_seen(db, merchant["merchant_id"]))


@router.post("/seen", summary="标记已看", dependencies=[Depends(get_current_merchant)])
def seen_post(merchant: Dict[str, Any] = Depends(get_current_merchant), db: Session = Depends(get_db)):
    return success_response(mark_seen(db, merchant["merchant_id"]), status_code=200)


@router.post("/seen/reset", summary="重置为未看", dependencies=[Depends(get_current_merchant)])
def seen_reset(merchant: Dict[str, Any] = Depends(get_current_merchant), db: Session = Depends(get_db)):
    return success_response(reset_seen(db, merchant["merchant_id"]), status_code=200)
