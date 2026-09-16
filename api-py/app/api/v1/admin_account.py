"""管理员账号路由(对齐 admin/src/api/account.ts + NestJS admin-account.controller)。

权限口径(总控 #PB-7-C / #AF-4 修正):列表/详情 = 需登录;create/update/delete/reset-password/generate = super_admin。
"""
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, require_roles
from app.core.response import success, success_response
from app.db.session import get_db
from app.services.admin_account import (
    create,
    find_all,
    find_one,
    generate,
    remove,
    reset_password,
    update,
)

router = APIRouter(prefix="/admin/account", tags=["管理员账号管理"])

AdminRole = Literal["super_admin", "admin", "viewer"]


class GenerateAdminBody(BaseModel):
    username: str = Field(..., min_length=2)
    realName: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    role: Optional[AdminRole] = Field(default=None)


class CreateAdminBody(BaseModel):
    username: str = Field(..., min_length=2)
    password: str = Field(..., min_length=8)
    realName: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    role: Optional[AdminRole] = Field(default=None)


class UpdateAdminBody(BaseModel):
    realName: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    role: Optional[AdminRole] = Field(default=None)
    status: Optional[int] = Field(default=None, ge=0, le=1)


class ResetPasswordBody(BaseModel):
    password: str = Field(..., min_length=8)


@router.get("/list", summary="获取管理员列表", dependencies=[Depends(get_current_admin)])
def account_list(db: Session = Depends(get_db)) -> dict:
    return success(find_all(db))


@router.post("/generate", summary="生成管理员账号(仅 super_admin)", dependencies=[Depends(require_roles("super_admin"))])
def account_generate(body: GenerateAdminBody, db: Session = Depends(get_db)) -> dict:
    return success_response(generate(db, body.username, body.realName, body.phone, body.email, body.role), status_code=201)


@router.post("/create", summary="创建管理员(仅 super_admin)", dependencies=[Depends(require_roles("super_admin"))])
def account_create(body: CreateAdminBody, db: Session = Depends(get_db)) -> dict:
    return success_response(
        create(db, body.username, body.password, body.realName, body.phone, body.email, body.role),
        status_code=201,
    )


@router.get("/{id}", summary="获取管理员详情", dependencies=[Depends(get_current_admin)])
def account_one(id: int, db: Session = Depends(get_db)) -> dict:
    return success(find_one(db, id))


@router.put("/{id}", summary="更新管理员(仅 super_admin)", dependencies=[Depends(require_roles("super_admin"))])
def account_update(id: int, body: UpdateAdminBody, db: Session = Depends(get_db)) -> dict:
    return success(update(db, id, body.model_dump(exclude_unset=True)))


@router.delete("/{id}", summary="删除管理员(仅 super_admin)", dependencies=[Depends(require_roles("super_admin"))])
def account_delete(id: int, db: Session = Depends(get_db)) -> dict:
    return success(remove(db, id))


@router.post("/{id}/reset-password", summary="重置管理员密码(仅 super_admin)", dependencies=[Depends(require_roles("super_admin"))])
def account_reset_password(id: int, body: ResetPasswordBody, db: Session = Depends(get_db)) -> dict:
    return success_response(reset_password(db, id, body.password), status_code=201)
