"""管理端商家路由(对齐 NestJS merchant-admin.controller 列表 + task-progress 进度/一键解锁 + 账号绑定)。"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, require_roles
from app.core.response import success, success_response
from app.core.timeutil import to_iso_utc
from app.db.session import get_db
from app.services.merchant import list_all
from app.services.merchant_binding import (
    BIND_SUCCESS_MESSAGE,
    RELEASE_SUCCESS_MESSAGE,
    bind_member,
    get_bindings,
    release_member,
)
# 别名:merchant.list_all 已是商家主表列表,此处避免同名遮蔽
from app.services.task_progress import find_by_merchant, list_all as list_all_progress, unlock_phase1

router = APIRouter(prefix="/admin/merchant", tags=["商家任务进度"])


def _progress_row(row) -> Dict[str, Any]:
    return {
        "id": str(row.id),
        "merchantId": row.merchantId,
        "taskId": row.taskId,
        "status": row.status,
        "completedAt": to_iso_utc(row.completedAt),
        "createdAt": to_iso_utc(row.createdAt),
        "updatedAt": to_iso_utc(row.updatedAt),
    }


@router.get("", summary="商家主表列表(分页+关键词检索+阶段/状态筛选)")
def merchant_list(
    keyword: Optional[str] = Query(default=None),
    stage: Optional[str] = Query(
        default=None, description="阶段精确筛选:onboarding(入驻准备)/shop_setup(开店搭建);空=不筛选"
    ),
    status: Optional[str] = Query(
        default=None, description="状态精确筛选:0(禁用)/1(正常)/2(已退出);空=不筛选"
    ),
    page: int = Query(default=1),
    page_size: int = Query(default=20),
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(get_current_admin),
) -> dict:
    # 取值校验由 services/merchant.py::list_all 独占(业务语义,路由只透传),非法值 -> 400
    return success(list_all(db, {
        "keyword": keyword, "stage": stage, "status": status,
        "page": page, "page_size": page_size,
    }))


@router.post("/{id}/unlock-phase1", summary="商家阶段一解锁(管理端,幂等永久)")
def unlock_phase1_route(
    id: str,
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(require_roles("super_admin", "admin")),
) -> dict:
    return success_response(unlock_phase1(db, id), status_code=201)




class BindMemberBody(BaseModel):
    """绑定目标账号(API-22 写):只传 merchant_id,**不暴露内部 binding id**。"""

    member_merchant_id: str = Field(..., min_length=1, max_length=64)


@router.get("/{merchantId}/bindings", summary="商家同店账号绑定详情(需登录)")
def bindings_query(
    merchantId: str,
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(get_current_admin),
) -> dict:
    # 读权限与 API-17 列表同档(需登录);组解析/唯一性/关组规则全部在 services/merchant_binding.py
    return success(get_bindings(db, merchantId))


@router.post("/{merchantId}/bindings", summary="绑定同店账号(admin/super_admin;幂等)", status_code=201)
def bindings_create(
    merchantId: str,
    body: BindMemberBody,
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(require_roles("super_admin", "admin")),
) -> dict:
    # 成功信封 message = 中文专句「绑定成功」(管理后台直接用作成功 toast;真源 §4.3 / §5.2 API-22)
    return success_response(
        bind_member(db, merchantId, body.member_merchant_id, admin["username"]),
        message=BIND_SUCCESS_MESSAGE,
        status_code=201,
    )


@router.delete("/{merchantId}/bindings/{memberMerchantId}", summary="解绑同店账号(admin/super_admin)")
def bindings_release(
    merchantId: str,
    memberMerchantId: str,
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(require_roles("super_admin", "admin")),
) -> dict:
    # 成功信封 message = 中文专句「已解绑」(同上)
    return success(release_member(db, merchantId, memberMerchantId, admin["username"]),
                   message=RELEASE_SUCCESS_MESSAGE)


@router.get("/progress", summary="获取商家任务进度(merchantId 可选；不传 = 全部商家)")
def progress_query(
    merchantId: Optional[str] = Query(default=None, description="商家ID(可选；不传=全部商家)"),
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(get_current_admin),
) -> dict:
    rows = find_by_merchant(db, merchantId) if merchantId else list_all_progress(db)
    return success([_progress_row(r) for r in rows])


@router.get("/progress/{merchantId}", summary="获取指定商家进度")
def progress_param(
    merchantId: str,
    db: Session = Depends(get_db),
    admin: Dict[str, Any] = Depends(get_current_admin),
) -> dict:
    rows = find_by_merchant(db, merchantId)
    return success([_progress_row(r) for r in rows])
