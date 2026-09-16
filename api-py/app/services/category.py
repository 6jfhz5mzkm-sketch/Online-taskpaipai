"""类目服务(对齐 backend category.service)。"""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiException
from app.db.models.category import Category


def get_category_list(db: Session, parent_id: Optional[int] = None) -> List[dict]:
    """类目列表:不传 parent_id 返回一级(parent_id=0),传了返回该一级下二级。"""
    pid = parent_id if parent_id is not None else 0
    rows = db.execute(
        select(Category)
        .where(Category.is_active == 1, Category.parent_id == pid)
        .order_by(Category.sort_order.asc())
    ).scalars().all()
    # 对齐 NestJS:bigint(id/parent_id)由 mysql2 返回为字符串,前端零改动需保持一致
    return [
        {"id": str(c.id), "name": c.name, "parent_id": str(c.parent_id), "sort_order": c.sort_order}
        for c in rows
    ]


def get_category_detail(db: Session, id: int) -> dict:
    """类目详情;不存在抛 404。"""
    c = db.execute(
        select(Category).where(Category.id == id, Category.is_active == 1)
    ).scalar_one_or_none()
    if c is None:
        raise ApiException("类目不存在", code=404, status_code=404)
    return {"id": str(c.id), "name": c.name, "parent_id": str(c.parent_id), "sort_order": c.sort_order}
