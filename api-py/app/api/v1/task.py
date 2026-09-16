"""商家端任务路由(对齐 NestJS task.controller: stages/progress)。"""
from typing import Any, Dict, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_merchant
from app.core.response import success, success_response
from app.db.session import get_db
from app.services.task import get_progress, get_stages
from app.services.task_progress import update_progress

router = APIRouter(prefix="/task", tags=["商家端任务"])


class UpdateProgressBody(BaseModel):
    taskId: str = Field(..., min_length=1)
    status: Literal["pending", "completed"]


@router.get("/stages", summary="获取阶段和任务列表(按商家进度隔离阶段二)")
def stages(
    merchant: Dict[str, Any] = Depends(get_current_merchant),
    db: Session = Depends(get_db),
) -> dict:
    return success(get_stages(db, merchant["merchant_id"]))


@router.get("/progress", summary="获取当前商家任务进度(含阶段二解锁状态)")
def progress(
    merchant: Dict[str, Any] = Depends(get_current_merchant),
    db: Session = Depends(get_db),
) -> dict:
    return success(get_progress(db, merchant["merchant_id"]))


@router.post("/progress", summary="更新任务进度(完成/取消完成)")
def update(
    body: UpdateProgressBody,
    merchant: Dict[str, Any] = Depends(get_current_merchant),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(update_progress(db, merchant["merchant_id"], body.taskId, body.status), status_code=201)
