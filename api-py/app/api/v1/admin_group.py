"""管理端一级任务路由(对齐 admin/src/api/first-level-task.ts + NestJS first-level-task.controller)。

契约(总控 #PB-7 裁决):GET /list?stageId=、GET /{id}、POST /create、PUT /{id}、DELETE /{id}。
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, require_roles
from app.core.response import success, success_response
from app.db.session import get_db
from app.services.admin_task_config import (
    create_group,
    delete_group,
    get_group,
    list_groups,
    update_group,
)

router = APIRouter(prefix="/admin/group", tags=["管理端一级任务管理"])


class GroupCreateBody(BaseModel):
    taskId: str = Field(..., min_length=1, max_length=32)
    stageId: str = Field(..., min_length=1, max_length=32)
    title: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = None
    buttonText: Optional[str] = Field(default=None, max_length=64)
    sortOrder: Optional[int] = Field(default=None, ge=0)


class GroupUpdateBody(BaseModel):
    taskId: Optional[str] = Field(default=None, min_length=1, max_length=32)
    stageId: Optional[str] = Field(default=None, min_length=1, max_length=32)
    title: Optional[str] = Field(default=None, min_length=1, max_length=128)
    description: Optional[str] = None
    buttonText: Optional[str] = Field(default=None, max_length=64)
    sortOrder: Optional[int] = Field(default=None, ge=0)


@router.get("/list", summary="获取一级任务列表(可按 stageId 过滤)")
def group_list(
    stageId: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(get_current_admin),
) -> dict:
    return success(list_groups(db, stageId))


@router.post("/create", summary="创建一级任务(仅 super_admin/admin)")
def group_create(
    body: GroupCreateBody,
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(require_roles("super_admin", "admin")),
) -> dict:
    return success_response(create_group(db, body.model_dump(exclude_unset=True)), status_code=201)


@router.get("/{id}", summary="获取一级任务详情")
def group_detail(
    id: int,
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(get_current_admin),
) -> dict:
    return success(get_group(db, id))


@router.put("/{id}", summary="更新一级任务(仅 super_admin/admin)")
def group_update(
    id: int,
    body: GroupUpdateBody,
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(require_roles("super_admin", "admin")),
) -> dict:
    return success(update_group(db, id, body.model_dump(exclude_unset=True)))


@router.delete("/{id}", summary="删除一级任务(仅 super_admin/admin)")
def group_delete(
    id: int,
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(require_roles("super_admin", "admin")),
) -> dict:
    return success(delete_group(db, id))
