"""商家反馈服务(对齐 backend feedback.service:M2 反馈闭环)。"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("api")

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiException
from app.core.timeutil import to_iso_utc
from app.db.models.feedback import Feedback

FEEDBACK_CATEGORIES = ["功能建议", "使用问题", "任务异常", "其他"]
FEEDBACK_STATUSES = ["pending", "processing", "resolved"]


def _row(f: Feedback) -> Dict[str, Any]:
    return {
        "id": str(f.id),
        "merchantId": f.merchant_id,
        "content": f.content,
        "category": f.category,
        "status": f.status,
        "adminReply": f.admin_reply,
        "handlerId": str(f.handler_id) if f.handler_id is not None else None,
        "createdAt": to_iso_utc(f.created_at),
        "updatedAt": to_iso_utc(f.updated_at),
    }


def create(db: Session, merchant_id: Optional[str], content: str, category: Optional[str]) -> Dict[str, Any]:
    """商家提交反馈:写库失败记日志并上抛(SEC P0 不再静默成成功);成功返回 received。"""
    try:
        db.add(Feedback(merchant_id=merchant_id, content=content,
                        category=category or "其他", status="pending"))
        db.commit()
    except Exception as e:
        db.rollback()
        # SEC P0:写库失败不再是静默成功,记日志并上抛(全局异常返回明确失败)
        logger.error(f"反馈写入失败: merchant={merchant_id} err={e}")
        raise
    return {"received": True}


def list_feedback(db: Session, query: Dict[str, Any]) -> Dict[str, Any]:
    page = int(query.get("page") or 1)
    page_size = int(query.get("page_size") or 20)
    stmt = select(Feedback)
    if query.get("status"):
        stmt = stmt.where(Feedback.status == query["status"])
    if query.get("category"):
        stmt = stmt.where(Feedback.category == query["category"])
    if query.get("start_date") and query.get("end_date"):
        stmt = stmt.where(Feedback.created_at.between(f"{query['start_date']} 00:00:00", f"{query['end_date']} 23:59:59"))
    elif query.get("start_date"):
        stmt = stmt.where(Feedback.created_at >= f"{query['start_date']} 00:00:00")
    elif query.get("end_date"):
        stmt = stmt.where(Feedback.created_at <= f"{query['end_date']} 23:59:59")

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    rows = db.execute(
        stmt.order_by(Feedback.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return {"list": [_row(r) for r in rows], "total": total, "page": page, "page_size": page_size}


def handle(db: Session, id: int, status: Optional[str], admin_reply: Optional[str], handler_id: int | None) -> Dict[str, Any]:
    # 合法状态校验(与 NestJS UpdateFeedbackDto 的 @IsIn(FEEDBACK_STATUSES) 同口径:写库前拦截,400)
    if status is not None and status not in FEEDBACK_STATUSES:
        raise ApiException(f"status 必须是 {'/'.join(FEEDBACK_STATUSES)} 之一", code=400, status_code=400)
    f = db.execute(select(Feedback).where(Feedback.id == id)).scalar_one_or_none()
    if f is None:
        raise ApiException(f"反馈 {id} 不存在", code=404, status_code=404)
    if status is not None:
        f.status = status
    if admin_reply is not None:
        f.admin_reply = admin_reply
    if status is not None or admin_reply is not None:
        f.handler_id = handler_id
    db.commit()
    return {
        "id": str(f.id),
        "status": f.status,
        "adminReply": f.admin_reply,
        "handlerId": str(f.handler_id) if f.handler_id is not None else None,
    }
