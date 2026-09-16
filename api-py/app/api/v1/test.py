"""鉴权测试接口(阶段1,用于验证 JWT/角色守卫)。"""
from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.api.deps import get_current_admin, get_current_merchant, require_roles
from app.core.response import success

router = APIRouter(prefix="/test", tags=["test-auth"])


@router.get("/merchant/me", summary="[测试] 商家鉴权")
def test_merchant_me(merchant: Dict[str, Any] = Depends(get_current_merchant)) -> Dict[str, Any]:
    """需要有效商家 token(JWT_SECRET 签发);无/伪 token 401。"""
    return success({"merchant_id": merchant["merchant_id"], "role": merchant["role"]})


@router.get("/admin/me", summary="[测试] 管理员鉴权")
def test_admin_me(admin: Dict[str, Any] = Depends(get_current_admin)) -> Dict[str, Any]:
    """需要有效管理员 token(ADMIN_JWT_SECRET 签发);无/伪 token 401。"""
    return success(
        {
            "id": admin["sub"],
            "username": admin["username"],
            "role": admin["role"],
            "realName": admin["realName"],
        }
    )


@router.get("/admin/account-manage", summary="[测试] 仅 super_admin 可访问")
def test_admin_account_manage(admin: Dict[str, Any] = Depends(require_roles("super_admin"))) -> Dict[str, Any]:
    """角色守卫:仅 super_admin 可访问;viewer/admin 调会 403。"""
    return success({"msg": "仅超级管理员可访问", "username": admin["username"]})
