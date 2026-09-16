"""飞书路由(对齐 NestJS feishu.controller:advisor-qr + notify)。"""
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.api.deps import get_current_merchant
from app.core.response import success, success_response
from app.db.session import get_db
from app.services import feishu
router = APIRouter(prefix="/feishu", tags=["飞书推送"])

@router.get("/advisor-qr", summary="获取商家顾问二维码", dependencies=[Depends(get_current_merchant)])
def advisor_qr():
    return success({"qr_url": "/api/static/advisor-qr.jpg", "talk": "您好，我是XX店铺负责人，想咨询入驻事宜。"})

@router.post("/notify/welcome", summary="发送欢迎消息")
def notify_welcome(merchant: Dict[str, Any] = Depends(get_current_merchant), db: Session = Depends(get_db)):
    mid = merchant["merchant_id"]; open_id = mid.replace("feishu_", "") if mid.startswith("feishu_") else "mock_open_id"
    name = "商家用户" if mid.startswith("feishu_") else "测试商家"
    res = feishu.welcome_on_first(db, mid, open_id, name)
    return success_response({"code": (1 if (res["first"] and not res["sent"]) else 0), "message": (("发送失败") if (res["first"] and not res["sent"]) else "success"), "data": {"sent": res["sent"], "first": res["first"], "open_id": open_id}}, status_code=200)

class StageBody(BaseModel):
    stage_name: str
    next_stage_name: Optional[str] = None

@router.post("/notify/stage-complete", summary="发送阶段完成通知")
def notify_stage(body: StageBody, merchant: Dict[str, Any] = Depends(get_current_merchant)):
    mid = merchant["merchant_id"]; open_id = mid.replace("feishu_", "") if mid.startswith("feishu_") else "mock_open_id"
    name = "商家用户" if mid.startswith("feishu_") else "测试商家"
    ok = feishu.stage_complete(open_id, name, body.stage_name, body.next_stage_name)
    return success_response({"code": (0 if ok else 1), "message": ("success" if ok else "发送失败"), "data": {"sent": ok}}, status_code=200)