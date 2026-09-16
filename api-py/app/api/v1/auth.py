"""认证路由(商家登录:飞书 OAuth / 手机号 + 短信验证码;#PB-23)。"""
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.response import success, success_response
from app.core.utils import get_client_ip
from app.db.session import get_db
from app.services import phone_auth
from app.services.auth import merchant_login

router = APIRouter(prefix="/auth", tags=["认证"])


class FeishuCallbackBody(BaseModel):
    code: str


class SendLoginCodeBody(BaseModel):
    """发码请求体。`captcha_verify_param` 是人机校验的不透明串,**原样透传**给服务端接缝。"""
    phone: str = Field(..., max_length=20)
    captcha_verify_param: Optional[str] = Field(default=None, max_length=4096)


class PhoneLoginBody(BaseModel):
    phone: str = Field(..., max_length=20)
    code: str = Field(..., max_length=10)


@router.post("/feishu/callback", summary="飞书 OAuth 登录")
def feishu_callback(body: FeishuCallbackBody, db: Session = Depends(get_db)) -> dict:
    # 对齐 NestJS:商家登录 POST 默认返回 201(admin 登录用 @HttpCode(200) 返回 200)
    return success_response(merchant_login(db, body.code), status_code=201)


@router.post("/phone/send-code", summary="发送手机号登录验证码")
def send_login_code(body: SendLoginCodeBody, request: Request, db: Session = Depends(get_db)) -> dict:
    """公开接口:校验人机校验 → 本地频控 → 发短信;成功 200。

    路由只做参数提取与投影:业务规则/频控矩阵/文案单一真源 = `app/services/phone_auth.py`。
    """
    return success(phone_auth.send_code(db, body.phone, body.captcha_verify_param, get_client_ip(request)))


@router.post("/phone/login", summary="手机号验证码登录(不存在则自注册)")
def phone_login(body: PhoneLoginBody, background_tasks: BackgroundTasks,
                db: Session = Depends(get_db)) -> dict:
    """公开接口:校验验证码 → 自注册/登录 → 签发 token;成功 **201**(沿用商家登录口径)。

    新商家注册的**内部通知**由服务层挂到 `BackgroundTasks`(注册事务先 commit,通知失败不影响 201)。
    """
    payload = phone_auth.login(db, body.phone, body.code, background_tasks)
    return success_response(payload, status_code=201)
