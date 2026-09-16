"""商标服务(对齐 backend trademark.service)。"""
from typing import List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiException
from app.db.models.trademark_registry import TrademarkRegistry
from app.services.task_progress import get_phase2_unlock_state


_LIKE_ESCAPE = "\\"   # MySQL LIKE 默认转义符


def _escape_like(value: str) -> str:
    """转义 LIKE 通配符,让用户输入按字面匹配:先转义转义符本身,再转义 % 与 _。"""
    return (value.replace(_LIKE_ESCAPE, _LIKE_ESCAPE * 2)
            .replace("%", _LIKE_ESCAPE + "%")
            .replace("_", _LIKE_ESCAPE + "_"))


def search(db: Session, keyword: str, merchant_id: str) -> List[dict]:
    """模糊搜索商标注册号(阶段二解锁后可用);未解锁抛 403,空白关键词抛 400。"""
    state = get_phase2_unlock_state(db, merchant_id)
    if not state["unlocked"]:
        raise ApiException("阶段二未解锁", code=403, status_code=403)

    trimmed = keyword.strip()
    if not trimmed:
        # 空/纯空白会生成 LIKE '%%%' 匹配全表(返回与关键词无关的数据),按参数校验失败返回
        raise ApiException("关键词不能为空", code=400, status_code=400)

    rows = db.execute(
        select(TrademarkRegistry)
        # % 与 _ 是 LIKE 通配符:必须按字面匹配(否则 '%%' 命中全表),显式 ESCAPE
        .where(TrademarkRegistry.brand_name.like(f"%{_escape_like(trimmed)}%", escape=_LIKE_ESCAPE))
        .order_by(TrademarkRegistry.brand_name.asc())
        .limit(50)
    ).scalars().all()
    return [
        {"brand_name": r.brand_name, "registration_number": r.registration_number}
        for r in rows
    ]
