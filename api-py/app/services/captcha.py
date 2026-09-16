"""人机校验(阿里云「图形认证」服务端二次校验)—— **单一接缝**(#PB-23 / #PB-23-R2 官方口径)。

调用点**只有一处**:`phone_auth.send_code` 的「本地频控 C1~C6 → C7 成本闸 → 本接缝 → 阿里云下发」。

官方依据:用户 2026-09-16 提供的《图形认证服务端集成》文档(逐条核对,本文件即其实现):
  · 接口 `POST {CAPTCHA_API_SERVER}/validate?captcha_id={CAPTCHA_APP_ID}`,请求格式**必须**
    `application/x-www-form-urlencoded`(用 httpx 的 `data=`,**不得**用 `json=`;格式不对会报 `illegal gen_time`);
  · 请求参数 `lot_number` / `captcha_output` / `pass_token` / `gen_time` / `sign_token`;
  · 签名 `sign_token = HMAC-SHA256(key=appKey, message=lot_number)` 的 hexdigest;
  · 判定:**仅 `status == "success"` 且 `result == "success"` 才通过**;
  · 返回异常形如 `{status:"error", code:"-50005", msg:"illegal gen_time"}`(错误码清单见真源 §5.2 API-21)。

**fail-closed(与官方 demo 的关键差异)**:官方示例在请求异常时把结果默认成 `{result: success}`(demo 简化 ⇒ fail-open),
**我们不照抄**:HTTP 非 200 / 超时 / 连接异常 / JSON 解析失败 / `status=error` / `result != success`
⇒ 一律 400「请先完成安全验证」,**绝不发码、绝不降级放行**;
**凭证缺失(`CAPTCHA_APP_ID`/`CAPTCHA_APP_KEY` 为空)另按服务侧故障处理** ⇒ **503**「登录服务暂不可用，请稍后重试或联系管理员」
(与 `services/feishu.py::FEISHU_LOGIN_UNAVAILABLE_MESSAGE` 同句)+ `logger.error`(写明缺哪个变量);#PB-23-R3。
日志只记 `status`/`result`/`reason`/`code`/`msg` 与客户端 IP;**不回显 `captcha_verify_param` 原文、不回显 appKey**。
"""
import hashlib
import hmac
import json
import logging

import httpx

from app.core.config import get_settings
from app.core.exceptions import ApiException
# 服务侧不可用的用户文案与飞书登录**同源同句**(#PB-23-R3):用户看白话,缺哪个变量只进日志
from app.services.feishu import FEISHU_LOGIN_UNAVAILABLE_MESSAGE

logger = logging.getLogger("api")

# 用户可见文案(单一真源;不回显阿里云错误码/技术细节)
CAPTCHA_REQUIRED_MESSAGE = "请先完成安全验证"
# 凭证缺失 = **服务侧配置故障**(不是「用户没做验证」):503 + 与飞书登录同一句白话
CAPTCHA_UNAVAILABLE_MESSAGE = FEISHU_LOGIN_UNAVAILABLE_MESSAGE
VALIDATE_PATH = "/validate"
# `captcha_verify_param` 里必须携带的字段(前端 `getValidate()` 的 4 字段;`captcha_id` 一律忽略)
REQUIRED_PARAM_FIELDS = ("lot_number", "captcha_output", "pass_token", "gen_time")


def _reject(reason: str, client_ip: str) -> None:
    """统一 fail-closed 出口(**用户侧**原因:未验证/校验未通过):400 + 白话文案。"""
    logger.warning(f"人机校验未通过: reason={reason} ip={client_ip}")
    raise ApiException(CAPTCHA_REQUIRED_MESSAGE, code=400, status_code=400)


def _reject_not_configured(missing: list, client_ip: str) -> None:
    """**服务侧配置故障**(凭证缺失)→ 503 + 服务不可用白话 + `logger.error`(明确指出缺哪个变量)。

    与其余 fail-closed 分支(400「请先完成安全验证」)语义不同:这里不是「用户没做验证」,
    而是登录链路整体不可用(生产忘配即全站不可登录),故用 503 让用户看到「稍后再试/联系管理员」、
    让告警抓得到;变量名只进日志,绝不进用户文案。
    """
    logger.error(f"图形认证凭证未配置,登录链路不可用: missing={','.join(missing)} ip={client_ip}")
    raise ApiException(CAPTCHA_UNAVAILABLE_MESSAGE, code=503, status_code=503)


def _parse_verify_param(captcha_verify_param: str) -> dict:
    """解析前端回传的不透明串(JSON),取出 4 个必需字段;`captcha_id` **忽略**(一律用服务端配置)。

    非 JSON / 非对象 / 缺字段 / 字段为空 ⇒ 抛 `ValueError`(调用方按 fail-closed 拒绝)。
    """
    try:
        parsed = json.loads(captcha_verify_param or "")
    except (TypeError, ValueError) as e:
        raise ValueError("invalid_json") from e
    if not isinstance(parsed, dict):
        raise ValueError("not_an_object")
    missing = [f for f in REQUIRED_PARAM_FIELDS if not str(parsed.get(f) or "").strip()]
    if missing:
        raise ValueError("missing_field")
    return {f: str(parsed[f]) for f in REQUIRED_PARAM_FIELDS}


def _sign_token(lot_number: str, app_key: str) -> str:
    """`sign_token = HMAC-SHA256(key=appKey, message=lot_number)` 的 hexdigest(官方签名算法)。"""
    return hmac.new(app_key.encode(), lot_number.encode(), hashlib.sha256).hexdigest()


def verify_captcha_or_raise(captcha_verify_param: str, client_ip: str) -> None:
    """服务端二次校验;通过返回 None,否则抛 400(**绝不放行**)。

    未配置 `CAPTCHA_APP_ID`/`CAPTCHA_APP_KEY`、参数缺失、传参格式非法时**不发起外部请求**(省成本、防误用)。
    """
    settings = get_settings()
    app_id = (settings.CAPTCHA_APP_ID or "").strip()
    app_key = (settings.CAPTCHA_APP_KEY or "").strip()
    if not app_id or not app_key:
        _reject_not_configured([name for name, value in (("CAPTCHA_APP_ID", app_id), ("CAPTCHA_APP_KEY", app_key))
                                if not value], client_ip)
    if not (captcha_verify_param or "").strip():
        _reject("missing_param", client_ip)
    try:
        payload = _parse_verify_param(captcha_verify_param)
    except ValueError as e:
        _reject(f"invalid_param:{e}", client_ip)

    data = dict(payload)
    data["sign_token"] = _sign_token(payload["lot_number"], app_key)
    url = settings.CAPTCHA_API_SERVER.rstrip("/") + VALIDATE_PATH
    try:
        resp = httpx.post(url, params={"captcha_id": app_id}, data=data,
                          timeout=settings.CAPTCHA_TIMEOUT_MS / 1000)
    except Exception as e:  # noqa: BLE001 - 超时/连接异常一律视为不通过(fail-closed)
        _reject(f"request_exception:{type(e).__name__}", client_ip)
    if resp.status_code != 200:
        _reject(f"http_status:{resp.status_code}", client_ip)
    try:
        body = resp.json()
    except Exception as e:  # noqa: BLE001 - 非 JSON 响应视为不通过
        _reject(f"invalid_response:{type(e).__name__}", client_ip)
    status = body.get("status")
    result = body.get("result")
    if status == "error":
        logger.warning(f"人机校验接口返回异常: code={body.get('code')} msg={body.get('msg')!r} ip={client_ip}")
        raise ApiException(CAPTCHA_REQUIRED_MESSAGE, code=400, status_code=400)
    if status != "success" or result != "success":
        logger.warning(f"人机校验未通过: status={status!r} result={result!r} reason={body.get('reason')!r} ip={client_ip}")
        raise ApiException(CAPTCHA_REQUIRED_MESSAGE, code=400, status_code=400)
    logger.info(f"人机校验通过: status=success result=success ip={client_ip}")
