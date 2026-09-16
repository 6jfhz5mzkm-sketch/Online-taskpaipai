"""管理端二级任务路由(对齐 admin/src/api/second-level-task.ts + NestJS second-level-task.controller)。

契约(总控 #PB-7 裁决):GET /list?firstLevelTaskId=&stageId=、GET /{id}、POST /create、PUT /{id}、DELETE /{id}。
type/completionType 枚举取自 NestJS CreateSecondLevelTaskDto 的 @IsIn,并写入 schema.sql 的列注释。
"""
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, require_roles
from app.core.response import success, success_response
from app.db.session import get_db
from app.services.admin_task_config import (
    create_task,
    delete_task,
    get_task,
    list_tasks,
    update_task,
)

router = APIRouter(prefix="/admin/task", tags=["管理端二级任务管理"])

TaskType = Literal["mandatory", "suggested", "guide"]
CompletionType = Literal["system_check", "manual_submit", "click_read"]


class TaskCreateBody(BaseModel):
    taskId: str = Field(..., min_length=1, max_length=32)
    firstLevelTaskId: str = Field(..., min_length=1, max_length=32)
    stageId: str = Field(..., min_length=1, max_length=32)
    title: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = None
    detail: Optional[str] = None
    type: TaskType
    completionType: CompletionType
    actionText: Optional[str] = Field(default=None, max_length=64)
    actionUrl: Optional[str] = Field(default=None, max_length=512)
    tag: Optional[str] = Field(default=None, max_length=32)
    defaultCompleted: Optional[int] = Field(default=None, ge=0)
    sortOrder: Optional[int] = Field(default=None, ge=0)


class TaskUpdateBody(BaseModel):
    taskId: Optional[str] = Field(default=None, min_length=1, max_length=32)
    firstLevelTaskId: Optional[str] = Field(default=None, min_length=1, max_length=32)
    stageId: Optional[str] = Field(default=None, min_length=1, max_length=32)
    title: Optional[str] = Field(default=None, min_length=1, max_length=128)
    description: Optional[str] = None
    detail: Optional[str] = None
    type: Optional[TaskType] = None
    completionType: Optional[CompletionType] = None
    actionText: Optional[str] = Field(default=None, max_length=64)
    actionUrl: Optional[str] = Field(default=None, max_length=512)
    tag: Optional[str] = Field(default=None, max_length=32)
    defaultCompleted: Optional[int] = Field(default=None, ge=0)
    sortOrder: Optional[int] = Field(default=None, ge=0)


@router.get("/list", summary="获取二级任务列表(可按 firstLevelTaskId/stageId 过滤)")
def task_list(
    firstLevelTaskId: Optional[str] = Query(default=None),
    stageId: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(get_current_admin),
) -> dict:
    return success(list_tasks(db, firstLevelTaskId, stageId))


@router.post("/create", summary="创建二级任务(仅 super_admin/admin)")
def task_create(
    body: TaskCreateBody,
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(require_roles("super_admin", "admin")),
) -> dict:
    return success_response(create_task(db, body.model_dump(exclude_unset=True)), status_code=201)


@router.get("/{id}", summary="获取二级任务详情")
def task_detail(
    id: int,
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(get_current_admin),
) -> dict:
    return success(get_task(db, id))


@router.put("/{id}", summary="更新二级任务(仅 super_admin/admin)")
def task_update(
    id: int,
    body: TaskUpdateBody,
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(require_roles("super_admin", "admin")),
) -> dict:
    return success(update_task(db, id, body.model_dump(exclude_unset=True)))


@router.delete("/{id}", summary="删除二级任务(仅 super_admin/admin)")
def task_delete(
    id: int,
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(require_roles("super_admin", "admin")),
) -> dict:
    return success(delete_task(db, id))
