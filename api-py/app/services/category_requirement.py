"""类目入驻资质要求服务(对齐 NestJS category-requirement.service.findByCategoryId)。

响应转 camelCase 并字节对齐 NestJS:
- id/categoryId/category.id/category.parentId 等 bigint -> str;
- requirements(JSON 列) -> dict;
- createdAt/updatedAt -> ISO8601 毫秒 + Z(如 "2026-07-23T08:02:11.000Z");
- deletedAt(nullable) -> null;
- category 为关联类目对象。
"""
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import to_iso_utc
from app.db.models.category import Category
from app.db.models.category_requirement import CategoryRequirement


def find_by_category_id(db: Session, category_id: int) -> Optional[Dict[str, Any]]:
    """按 category_id 查单条;无记录返回 None(接口层转 data:null)。"""
    # 契约 §5.2 API-16:默认查询 is_active=1 的启用记录
    req = db.execute(
        select(CategoryRequirement).where(
            CategoryRequirement.category_id == category_id,
            CategoryRequirement.is_active == 1,
        )
    ).scalar_one_or_none()
    if req is None:
        return None

    # 关联类目对象
    cat = db.execute(
        select(Category).where(Category.id == req.category_id)
    ).scalar_one_or_none()
    category_dict = None
    if cat is not None:
        category_dict = {
            "id": str(cat.id),
            "parentId": str(cat.parent_id),
            "name": cat.name,
            "sortOrder": cat.sort_order,
            "isActive": cat.is_active,
            "createdAt": to_iso_utc(cat.created_at),
            "updatedAt": to_iso_utc(cat.updated_at),
            "deletedAt": to_iso_utc(cat.deleted_at),
        }

    return {
        "id": str(req.id),
        "categoryId": str(req.category_id),
        "shopType": req.shop_type,
        "shopNameRule": req.shop_name_rule,
        "requirements": req.requirements,  # JSON 列已解析为 dict
        "reviewFocus": req.review_focus,
        "contactEmail": req.contact_email,
        "isActive": req.is_active,
        "createdAt": to_iso_utc(req.created_at),
        "updatedAt": to_iso_utc(req.updated_at),
        "deletedAt": to_iso_utc(req.deleted_at),
        "category": category_dict,
    }