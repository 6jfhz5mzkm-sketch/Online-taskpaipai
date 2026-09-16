"""管理员认证路由(对齐 admin/src/api/auth.ts + NestJS admin-auth.controller)。

接口:POST /login(公开)、GET /profile(需登录)、POST /change-password(需登录)。
总控 #PB-7 追加范围(A);响应仍为统一 {code,message,data}。
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.response import success, success_response
from app.db.session import get_db
from app.services.auth import admin_change_password, admin_login, admin_profile

router = APIRouter(prefix="/admin/auth", tags=["管理员认证"])


class AdminLoginBody(BaseModel):
    username: str = Field(..., min_length=2, description="登录用户名")
    password: str = Field(..., min_length=6, description="登录密码")


class ChangePasswordBody(BaseModel):
    oldPassword: str = Field(..., min_length=6)
    newPassword: str = Field(..., min_length=8)


@router.post("/login", summary="管理员登录")
def login(body: AdminLoginBody, request: Request, db: Session = Depends(get_db)) -> dict:
    ip = request.client.host if request.client else None
    return success(admin_login(db, body.username, body.password, ip))


@router.get("/profile", summary="获取当前管理员信息")
def profile(admin: Dict[str, Any] = Depends(get_current_admin)) -> dict:
    return success(admin_profile(admin))


@router.post("/change-password", summary="修改密码")
def change_password(
    body: ChangePasswordBody,
    admin: Dict[str, Any] = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(
        admin_change_password(db, int(admin["sub"]), body.oldPassword, body.newPassword),
        status_code=201,
    )
