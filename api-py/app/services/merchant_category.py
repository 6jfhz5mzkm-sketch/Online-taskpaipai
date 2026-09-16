"""商家经营类目服务(API-07:POST /api/merchant/category)。

真源:project/docs/后端技术方案.md §5.2 API-07——校验 1-3 个 / is_primary 唯一 / category_id 必须存在 /
重复去重;覆盖式写入(先删该商家旧记录再插入,同一事务)+ 写 event_log。
只读参考(已作废的 NestJS backend merchant.service.saveCategories)只有「先删后插」,
无校验与埋点;本实现按真源补齐,响应仍为 { success, count }。
"""
import json
import logging
from typing import Any, Dict, List

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiException
from app.db.models.category import Category
from app.db.models.event_log import EventLog
from app.db.models.merchant_category import MerchantCategory

logger = logging.getLogger("api")

MIN_CATEGORIES = 1
MAX_CATEGORIES = 3
# 埋点事件类型取自前端 src/utils/track.ts 的 EventType 枚举(category_select),不新造类型
EVENT_TYPE_CATEGORY_SELECT = "category_select"
EVENT_ELEMENT_SAVE = "save_merchant_categories"


def _normalize(categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """去重(按 category_id 保序,is_primary 取「或」)并校验数量与主营唯一性。

    先去重再判 1-3:重复选择属真源明确的「去重处理」,不应因数了重复项而判超限。
    """
    deduped: List[Dict[str, Any]] = []
    index_by_category: Dict[int, int] = {}
    for item in categories:
        category_id = item.get("category_id")
        if not isinstance(category_id, int) or isinstance(category_id, bool) or category_id <= 0:
            raise ApiException("类目不存在", code=400, status_code=400)
        is_primary = bool(item.get("is_primary"))
        if category_id in index_by_category:
            position = index_by_category[category_id]
            deduped[position]["is_primary"] = deduped[position]["is_primary"] or is_primary
            continue
        index_by_category[category_id] = len(deduped)
        deduped.append({"category_id": category_id, "is_primary": is_primary})

    if not MIN_CATEGORIES <= len(deduped) <= MAX_CATEGORIES:
        raise ApiException("请选择1-3个类目", code=400, status_code=400)
    if sum(1 for item in deduped if item["is_primary"]) > 1:
        raise ApiException("只能选择一个主营类目", code=400, status_code=400)
    return deduped


def save_categories(db: Session, merchant_id: str, categories: List[Dict[str, Any]]) -> Dict[str, Any]:
    """覆盖式保存商家经营类目:校验 -> 删旧 -> 插新 -> 埋点,全部在同一事务内提交。

    事务口径:删除、插入与 event_log 同一次 commit;任一步失败则整体 rollback(不留半覆盖状态)。
    """
    if not isinstance(categories, list) or not categories:
        raise ApiException("请选择1-3个类目", code=400, status_code=400)
    normalized = _normalize(categories)
    category_ids = [item["category_id"] for item in normalized]

    existing_ids = set(
        db.execute(
            select(Category.id).where(Category.id.in_(category_ids), Category.deleted_at.is_(None))
        ).scalars().all()
    )
    if any(cid not in existing_ids for cid in category_ids):
        raise ApiException("类目不存在", code=400, status_code=400)

    try:
        db.execute(delete(MerchantCategory).where(MerchantCategory.merchant_id == merchant_id))
        for item in normalized:
            db.add(
                MerchantCategory(
                    merchant_id=merchant_id,
                    category_id=item["category_id"],
                    is_primary=1 if item["is_primary"] else 0,
                )
            )
        db.add(
            EventLog(
                merchant_id=merchant_id,
                event_type=EVENT_TYPE_CATEGORY_SELECT,
                element=EVENT_ELEMENT_SAVE,
                meta=json.dumps({"categoryIds": category_ids}, ensure_ascii=False),
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(f"保存商家经营类目失败: merchant={merchant_id}")
        raise
    return {"success": True, "count": len(normalized)}


def list_categories(db: Session, merchant_id: str) -> Dict[str, Any]:
    """查询该商家当前经营类目(API-07 查询侧)。

    返回形状与提交项对齐({category_id, is_primary}),便于前端直接回显选择态;
    类目名称不在此重复返回——名称唯一真源是 `category` 表,前端经 API-05 类目列表获取,
    避免同一事实出现两份可能漂移的副本。
    排序:is_primary DESC, category_id ASC(主营在前,其余按类目 id 稳定排序)。
    """
    rows = db.execute(
        select(MerchantCategory)
        .where(MerchantCategory.merchant_id == merchant_id)
        .order_by(MerchantCategory.is_primary.desc(), MerchantCategory.category_id.asc())
    ).scalars().all()
    return {
        "success": True,
        "categories": [
            {"category_id": row.category_id, "is_primary": bool(row.is_primary)} for row in rows
        ],
    }
