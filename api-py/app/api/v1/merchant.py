"""商家路由(对齐 NestJS merchant.controller:/info 只读 + /registration 登记)。"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_merchant
from app.core.response import success, success_response
from app.db.session import get_db
from app.services.merchant import get_merchant_info, get_registration, save_registration
from app.services.merchant_category import list_categories, save_categories

router = APIRouter(prefix="/merchant", tags=["商家"])


class RegistrationBody(BaseModel):
    jd_merchant_id: Optional[str] = Field(default=None, max_length=64)
    shop_name: Optional[str] = Field(default=None, max_length=128)


class CategoryItem(BaseModel):
    """经营类目提交项(真源 §5.2 API-07:camelCase 之外的字段名按契约固定为 category_id / is_primary)。"""

    category_id: int
    is_primary: bool = False


class CategoriesBody(BaseModel):
    categories: List[CategoryItem]


@router.get("/info", summary="获取商家信息")
def merchant_info(
    merchant: Dict[str, Any] = Depends(get_current_merchant),
    db: Session = Depends(get_db),
) -> dict:
    return success(get_merchant_info(db, merchant["merchant_id"]))


@router.put("/registration", summary="商家登记 jd_merchant_id/shop_name(幂等覆盖+格式校验:商家ID 仅数字 / 店铺名称 仅汉字)")
def save_merchant_registration(
    body: RegistrationBody,
    merchant: Dict[str, Any] = Depends(get_current_merchant),
    db: Session = Depends(get_db),
) -> dict:
    patch = {}
    if "jd_merchant_id" in body.model_fields_set:
        patch["jd_merchant_id"] = body.jd_merchant_id
    if "shop_name" in body.model_fields_set:
        patch["shop_name"] = body.shop_name
    return success(save_registration(db, merchant["merchant_id"], patch))


@router.post("/category", summary="保存商家经营类目(API-07 / 任务 T1.1.2,覆盖式写入)", status_code=201)
def save_merchant_categories(
    body: CategoriesBody,
    merchant: Dict[str, Any] = Depends(get_current_merchant),
    db: Session = Depends(get_db),
) -> dict:
    return success_response(
        save_categories(db, merchant["merchant_id"], [item.model_dump() for item in body.categories]),
        status_code=201,
    )


@router.get("/category", summary="获取商家已保存经营类目(API-07 查询侧)")
def get_merchant_categories(
    merchant: Dict[str, Any] = Depends(get_current_merchant),
    db: Session = Depends(get_db),
) -> dict:
    return success(list_categories(db, merchant["merchant_id"]))


@router.get("/registration", summary="获取商家已登记信息")
def get_merchant_registration(
    merchant: Dict[str, Any] = Depends(get_current_merchant),
    db: Session = Depends(get_db),
) -> dict:
    return success(get_registration(db, merchant["merchant_id"]))
