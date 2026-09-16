"""埋点上报(对齐 backend event.service.track:静默落库)。"""
import json
import logging
from typing import Optional

logger = logging.getLogger("api")
from sqlalchemy.orm import Session
from app.db.models.event_log import EventLog


def track(db: Session, merchant_id: Optional[str], event_type: str, page_name, task_key, stage_key, element, meta, ip, user_agent) -> dict:
    try:
        db.add(EventLog(merchant_id=merchant_id or None, event_type=event_type, page_name=page_name or None,
                        task_key=task_key or None, stage_key=stage_key or None, element=element or None,
                        meta=(json.dumps(meta, ensure_ascii=False) if isinstance(meta, (dict, list)) else (meta or None)), ip=ip or None, user_agent=(user_agent or "")[:512] or None))
        db.commit()
    except Exception as e:
        db.rollback()
        # SEC P0:埋点(该吞,不入主流程)仍记日志,避免失败无感知
        logger.warning(f"埋点写入失败: type={event_type} err={e}")
    return {"received": True}
