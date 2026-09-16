"""管理端阶段路由(对齐 admin/src/api/stage.ts + NestJS stage.controller)。

自总控裁决(#PB-7):契约以「前端真实调用 + NestJS 既有实现」为准,即
GET /list、GET /{id}、POST /create、PUT /{id}、DELETE /{id},而非文档 §6.3 的 detail/update/delete 形式。
"""
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, require_roles
from app.core.response import success, success_response
from app.db.session import get_db
from app.services.admin_task_config import (
    create_stage,
    delete_stage,
    get_stage,
    list_stages,
    update_stage,
)

router = APIRouter(prefix="/admin/stage", tags=["管理端阶段管理"])


class StageCreateBody(BaseModel):
    stageId: str = Field(..., min_length=1, max_length=32)
    stageNum: int = Field(..., ge=1)
    title: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = None
    buttonText: Optional[str] = Field(default=None, max_length=64)
    sortOrder: Optional[int] = Field(default=None, ge=0)
    phaseNum: Optional[Literal[1, 2]] = None


class StageUpdateBody(BaseModel):
    stageId: Optional[str] = Field(default=None, min_length=1, max_length=32)
    stageNum: Optional[int] = Field(default=None, ge=1)
    title: Optional[str] = Field(default=None, min_length=1, max_length=128)
    description: Optional[str] = None
    buttonText: Optional[str] = Field(default=None, max_length=64)
    sortOrder: Optional[int] = Field(default=None, ge=0)
    phaseNum: Optional[Literal[1, 2]] = None


@router.get("/list", summary="获取阶段列表")
def stage_list(
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(get_current_admin),
) -> dict:
    return success(list_stages(db))


@router.post("/create", summary="创建阶段(仅 super_admin/admin)")
def stage_create(
    body: StageCreateBody,
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(require_roles("super_admin", "admin")),
) -> dict:
    return success_response(create_stage(db, body.model_dump(exclude_unset=True)), status_code=201)


@router.get("/{id}", summary="获取阶段详情")
def stage_detail(
    id: int,
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(get_current_admin),
) -> dict:
    return success(get_stage(db, id))


@router.put("/{id}", summary="更新阶段(仅 super_admin/admin)")
def stage_update(
    id: int,
    body: StageUpdateBody,
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(require_roles("super_admin", "admin")),
) -> dict:
    return success(update_stage(db, id, body.model_dump(exclude_unset=True)))


@router.delete("/{id}", summary="删除阶段(仅 super_admin/admin)")
def stage_delete(
    id: int,
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(require_roles("super_admin", "admin")),
) -> dict:
    return success(delete_stage(db, id))
