"""商家反馈路由(对齐 NestJS feedback.controller)。"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_current_merchant, require_roles
from app.core.response import success, success_response
from app.db.session import get_db
from app.services.feedback import FEEDBACK_CATEGORIES, create, handle, list_feedback

router = APIRouter(tags=["商家反馈"])


class CreateFeedbackBody(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)
    category: Optional[str] = Field(default=None, max_length=16)


class UpdateFeedbackBody(BaseModel):
    status: Optional[str] = Field(default=None)
    adminReply: Optional[str] = Field(default=None, max_length=1000)


@router.post("/feedback", summary="商家提交反馈(静默写)", dependencies=[Depends(get_current_merchant)])
def create_feedback(
    body: CreateFeedbackBody,
    merchant: Dict[str, Any] = Depends(get_current_merchant),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(create(db, merchant["merchant_id"], body.content, body.category), status_code=201)


@router.get("/admin/feedback", summary="反馈列表(管理端筛选)", dependencies=[Depends(require_roles("super_admin", "admin"))])
def feedback_list(
    status: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    page: int = Query(default=1),
    page_size: int = Query(default=20),
    db: Session = Depends(get_db),
) -> dict:
    return success(list_feedback(db, {
        "status": status, "category": category,
        "start_date": start_date, "end_date": end_date,
        "page": page, "page_size": page_size,
    }))


@router.patch("/admin/feedback/{id}", summary="处理反馈(更新 status + admin_reply)", dependencies=[Depends(require_roles("super_admin", "admin"))])
def feedback_handle(
    id: int,
    body: UpdateFeedbackBody,
    admin: Dict[str, Any] = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    return success(handle(db, id, body.status, body.adminReply, admin["sub"]))
