"""埋点路由(对齐 NestJS event.controller,管理端统计)。"""
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.response import success, success_response
from app.core.utils import get_client_ip
from app.db.session import get_db
from app.services.event import stats
from app.services.event_core import track

logger = logging.getLogger("api")

router = APIRouter(prefix="/event", tags=["埋点"])


class TrackBody(BaseModel):
    event_type: str
    page_name: Optional[str] = None
    task_key: Optional[str] = None
    stage_key: Optional[str] = None
    element: Optional[str] = None
    meta: Optional[Any] = None


@router.post("/track", summary="上报埋点事件(落库;未登录可上报,静默)")
def event_track(body: TrackBody, request: Request, db: Session = Depends(get_db)):
    # SEC-02/审查:埋点 IP 用可信来源(不再取客户端可控 XFF 首段)
    ip = get_client_ip(request) or None
    ua = request.headers.get("user-agent") or None
    # merchant_id 从 JWT 提取
    merchant_id = None
    from app.core.security import decode_token
    from app.core.config import get_settings
    auth = request.headers.get("authorization") or ""
    if auth.startswith("Bearer "):
        try:
            payload = decode_token(auth[7:], get_settings().JWT_SECRET, ["HS256"])
            merchant_id = payload.get("merchant_id")
        except Exception as e:
            # SEC P0:该吞(埋点,无效 token 不阻断)但记日志
            logger.warning(f"埋点 token 解析失败忽略: {e}")
            merchant_id = None
    return success_response(track(db, merchant_id, body.event_type, body.page_name, body.task_key, body.stage_key, body.element, body.meta, ip, ua), status_code=201)


@router.get("/stats", summary="获取埋点统计(管理端,≤90天)", dependencies=[Depends(get_current_admin)])
def event_stats(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    event_type: Optional[str] = Query(default=None),
    group_by: str = Query(default="day", pattern="^(day|week)$"),
    db: Session = Depends(get_db),
) -> dict:
    return success(stats(db, start_date, end_date, event_type, group_by))
