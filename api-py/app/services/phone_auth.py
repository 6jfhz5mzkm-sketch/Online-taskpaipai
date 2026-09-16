"""商家手机号 + 短信验证码登录(业务层;#PB-23 / 任务单 #PL-4;PNVS 短信认证口径)。

验证码**由阿里云生成与校验**(`services/sms_verify.py` 的 `SendSmsVerifyCode` / `CheckSmsVerifyCode`):
我方**不接触验证码明文**(`ReturnVerifyCode=false`),只保存 `biz_id`/`out_id` 供可观测与透传校验;
有效期由阿里云 `ValidTime`(= `LOGIN_CODE_TTL_MINUTES * 60`)承担,同号间隔由 `Interval` 兜底。

owner:业务规则与频控矩阵 C1~C10 的**本地兜底闸**(路由只做参数提取与投影;外部调用只经适配层与接缝)。
安全口径:`merchant_id = "p_" + 32 hex 随机`(G-1,不用手机号);手机号明文存储但日志/通知一律脱敏(G-5);
`merchant_login_code` 落库行只含 `phone/biz_id/out_id/ip/attempts/used_at/created_at`(不写任何验证码材料)。
"""
import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import BackgroundTasks
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ApiException
from app.core.security import create_merchant_token
from app.core.utils import mask_phone
from app.db.models.merchant import Merchant
from app.services import captcha, sms_verify
from app.services.internal_notify import notify_merchant_registered

logger = logging.getLogger("api")

# ---- 用户可见文案(单一真源;真源 §4.3/§4.3.1/§5.2 登记,禁止散落字符串) ----
PHONE_INVALID_MESSAGE = "手机号格式不正确"                          # §4.3.1 专句(服务层 owner)
SEND_TOO_FREQUENT_TEMPLATE = "发送过于频繁，请在 {seconds} 秒后重试"   # C1 / C2(带剩余秒数)
PHONE_DAILY_LIMIT_MESSAGE = "今日发送次数已达上限，请明天再试"        # C3
IP_SEND_LIMITED_MESSAGE = "发送过于频繁，请稍后再试"                  # C4 / C5(不带秒数)
GLOBAL_SEND_LIMIT_MESSAGE = "当前发送量已达上限，请稍后再试"          # C6 / C7(503 新增分段)
CODE_INVALID_MESSAGE = "验证码不正确或已过期"                        # 校验未通过(含阿里云 UNKNOWN)
VERIFY_TOO_MANY_MESSAGE = "验证尝试次数过多，请重新获取验证码"        # C8 / C10
ACCOUNT_DISABLED_MESSAGE = "账号已被禁用，请联系平台"                # G-2 登录入口拦截
PHONE_UNAVAILABLE_MESSAGE = "该手机号不可用，请联系平台"              # G-3 软删仍占 uk_phone

PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")
MERCHANT_ID_PREFIX = "p_"          # G-1:随机 ID,不用手机号
OUT_ID_PREFIX = "login-"           # 我方透传 ID(同时写给阿里云,校验时回传)
DAILY_ALERT_RATIO = 0.8            # C6 80% 告警


def _now() -> datetime:
    """当前本地时间(与 ORM 默认 `datetime.now` 同口径;经模块级间接层便于测试回拨时钟)。"""
    return datetime.now()


def _normalized_phone(phone: Optional[str]) -> str:
    """校验并归一手机号;不合法 → 400 专句(服务层唯一 owner,与 `shop.DATA_DATE_INVALID_MESSAGE` 同机制)。"""
    value = (phone or "").strip()
    if not PHONE_PATTERN.match(value):
        raise ApiException(PHONE_INVALID_MESSAGE, code=400, status_code=400)
    return value


def _ceil_seconds(delta: timedelta) -> int:
    """timedelta → 向上取整秒(**整数运算,无浮点尾差**:#PB-34 的教训,不用 float + ceil)。"""
    if delta <= timedelta(0):
        return 0
    total_us = (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
    return -(-total_us // 1_000_000)


def _new_out_id() -> str:
    """生成我方透传 ID(不携带任何 PII;`OutId` 同时写入阿里云与本地行)。"""
    return f"{OUT_ID_PREFIX}{uuid.uuid4().hex}"


def _count(db: Session, where: str, params: Dict[str, Any]) -> int:
    return int(db.execute(text("SELECT COUNT(*) FROM merchant_login_code WHERE " + where), params).scalar() or 0)


def _oldest_created_at(db: Session, where: str, params: Dict[str, Any]) -> Optional[datetime]:
    return db.execute(text("SELECT MIN(created_at) FROM merchant_login_code WHERE " + where), params).scalar()


def _enforce_send_limits(db: Session, phone: str, client_ip: str, now: datetime) -> None:
    """本地频控 C1~C6(全部落库计数)。**被拒请求不写行**,故拒绝不会把窗口延后。"""
    settings = get_settings()
    hour_ago = now - timedelta(hours=1)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # C1 同手机号冷却:最近一次发码时间(不分新老号码,防枚举)
    last_created = db.execute(
        text("SELECT created_at FROM merchant_login_code WHERE phone = :p ORDER BY created_at DESC, id DESC LIMIT 1"),
        {"p": phone}).scalar()
    if last_created is not None:
        remaining = _ceil_seconds(last_created + timedelta(seconds=settings.LOGIN_CODE_COOLDOWN_SECONDS) - now)
        if remaining > 0:
            raise ApiException(SEND_TOO_FREQUENT_TEMPLATE.format(seconds=remaining), code=429, status_code=429)

    # C2 同手机号小时上限(带剩余秒数)
    phone_hour_window = "phone = :p AND created_at >= :since"
    phone_hour_params = {"p": phone, "since": hour_ago}
    if _count(db, phone_hour_window, phone_hour_params) >= settings.LOGIN_CODE_PHONE_HOURLY_MAX:
        oldest = _oldest_created_at(db, phone_hour_window, phone_hour_params)
        remaining = _ceil_seconds(oldest + timedelta(hours=1) - now) if oldest else settings.LOGIN_CODE_COOLDOWN_SECONDS
        raise ApiException(SEND_TOO_FREQUENT_TEMPLATE.format(seconds=max(1, remaining)), code=429, status_code=429)

    # C3 同手机号日上限
    if _count(db, "phone = :p AND created_at >= :since", {"p": phone, "since": day_start}) >= settings.LOGIN_CODE_PHONE_DAILY_MAX:
        raise ApiException(PHONE_DAILY_LIMIT_MESSAGE, code=429, status_code=429)

    # C4 / C5 同 IP 时/日上限(客户端真实 IP,默认不信任 XFF)
    if _count(db, "ip = :ip AND created_at >= :since", {"ip": client_ip, "since": hour_ago}) >= settings.LOGIN_CODE_IP_HOURLY_MAX:
        raise ApiException(IP_SEND_LIMITED_MESSAGE, code=429, status_code=429)
    if _count(db, "ip = :ip AND created_at >= :since", {"ip": client_ip, "since": day_start}) >= settings.LOGIN_CODE_IP_DAILY_MAX:
        raise ApiException(IP_SEND_LIMITED_MESSAGE, code=429, status_code=429)

    # C6 全局日上限(+80% 告警;达上限 503)
    global_today = _count(db, "created_at >= :since", {"since": day_start})
    if global_today >= settings.LOGIN_CODE_GLOBAL_DAILY_MAX:
        logger.error(f"登录验证码全局日上限已达上限: used={global_today} max={settings.LOGIN_CODE_GLOBAL_DAILY_MAX}")
        raise ApiException(GLOBAL_SEND_LIMIT_MESSAGE, code=503, status_code=503)
    if global_today >= settings.LOGIN_CODE_GLOBAL_DAILY_MAX * DAILY_ALERT_RATIO:
        logger.warning(f"登录验证码发送量接近全局日上限: used={global_today} max={settings.LOGIN_CODE_GLOBAL_DAILY_MAX}")


def _consume_captcha_budget(db: Session, now: datetime) -> int:
    """C7 人机校验成本闸:原子自增当日计数后判定(达上限 → 503,且**不再调用**人机校验)。

    自增用 `INSERT ... ON DUPLICATE KEY UPDATE used = used + 1`(1 行/天,天然有界、无需清理)。
    计数发生在调用外部服务**之前**,故超限请求也计入(外部按次计费口径)。
    """
    settings = get_settings()
    limit = settings.LOGIN_CAPTCHA_DAILY_MAX
    today = now.date()
    db.execute(
        text("INSERT INTO captcha_daily_counter (day, used, created_at, updated_at) VALUES (:d, 1, :now, :now) "
             "ON DUPLICATE KEY UPDATE used = used + 1, updated_at = :now"),
        {"d": today, "now": now})
    db.commit()      # 外部按次计费已发生:先落盘,后续本地闸拒绝也不回滚
    used = int(db.execute(text("SELECT used FROM captcha_daily_counter WHERE day = :d"), {"d": today}).scalar() or 0)
    if limit > 0 and used > limit:
        logger.error(f"人机校验成本闸已达上限: used={used} max={limit}")
        raise ApiException(GLOBAL_SEND_LIMIT_MESSAGE, code=503, status_code=503)
    if limit > 0 and used >= limit * DAILY_ALERT_RATIO:
        logger.warning(f"人机校验成本闸接近上限: used={used} max={limit}")
    return used


def _enforce_verify_window(db: Session, phone: str, now: datetime) -> None:
    """C10 同手机号校验尝试窗口:窗口内 `SUM(attempts)`(失败校验次数)达上限 → 429。"""
    settings = get_settings()
    since = now - timedelta(minutes=settings.LOGIN_CODE_VERIFY_WINDOW_MINUTES)
    failed = int(db.execute(
        text("SELECT COALESCE(SUM(attempts), 0) FROM merchant_login_code WHERE phone = :p AND created_at >= :since"),
        {"p": phone, "since": since}).scalar() or 0)
    if failed >= settings.LOGIN_CODE_VERIFY_WINDOW_MAX:
        logger.warning(f"手机号校验尝试过于频繁: phone={mask_phone(phone)} failures={failed}")
        raise ApiException(VERIFY_TOO_MANY_MESSAGE, code=429, status_code=429)


def send_code(db: Session, phone: Optional[str], captcha_verify_param: Optional[str], client_ip: str) -> Dict[str, Any]:
    """发码:① 参数 → ② 本地频控 C1~C6 → ③ C7 成本闸 → ④ 人机校验接缝 → ⑤ 阿里云下发 + 落行为证。"""
    settings = get_settings()
    normalized = _normalized_phone(phone)
    now = _now()
    _enforce_send_limits(db, normalized, client_ip, now)
    _consume_captcha_budget(db, now)
    captcha.verify_captcha_or_raise(captcha_verify_param or "", client_ip)

    out_id = _new_out_id()
    biz_id = sms_verify.send_verify_code(normalized, out_id)      # 唯一短信出口(失败抛 502)
    # 发新码作废旧码(本地兜底;阿里云侧由 DuplicatePolicy=1 保证最新覆盖)
    db.execute(text("UPDATE merchant_login_code SET used_at = :now WHERE phone = :p AND used_at IS NULL"),
               {"now": now, "p": normalized})
    db.execute(
        text("INSERT INTO merchant_login_code (phone, biz_id, out_id, ip, attempts, used_at, created_at) "
             "VALUES (:p, :biz, :out, :ip, 0, NULL, :now)"),
        {"p": normalized, "biz": biz_id, "out": out_id, "ip": client_ip, "now": now})
    db.commit()
    logger.info(f"登录验证码已下发: phone={mask_phone(normalized)} biz_id={biz_id} out_id={out_id}")
    return {"sent": True,
            "cooldown_seconds": settings.LOGIN_CODE_COOLDOWN_SECONDS,
            "expires_in_seconds": settings.LOGIN_CODE_TTL_MINUTES * 60,
            "code_length": settings.LOGIN_CODE_LENGTH}


def _lookup_merchant_by_phone(db: Session, phone: str) -> Optional[Dict[str, Any]]:
    """按手机号查商家(**含软删行**:G-3 软删仍占 `uk_phone`,必须能查到才能给出 400)。"""
    row = db.execute(
        text("SELECT merchant_id, nickname, avatar, merchant_name, current_stage, status, deleted_at "
             "FROM merchant WHERE phone = :p ORDER BY id LIMIT 1"),
        {"p": phone}).mappings().first()
    return dict(row) if row else None


def _merchant_projection(row: Dict[str, Any]) -> Dict[str, Any]:
    """响应里的 merchant 投影(与既有飞书登录响应同形;不含手机号,防枚举/防 PII 回显)。"""
    return {"merchant_id": row["merchant_id"],
            "nickname": row.get("nickname") or "",
            "avatar": row.get("avatar") or "",
            "merchant_name": row.get("merchant_name"),
            "current_stage": row.get("current_stage"),
            "status": int(row["status"])}


def login(db: Session, phone: Optional[str], code: Optional[str],
          background_tasks: Optional[BackgroundTasks] = None) -> Dict[str, Any]:
    """校验验证码(**阿里云 `CheckSmsVerifyCode`**)→ 不存在则自注册 → 签发 token →(新商家)旁路内部通知。

    判定顺序:参数 → C10 窗口 → 取最新未使用行(无行即 400) → 阿里云校验(仅 `PASS` 放行) →
    失败则本行 `attempts + 1`(达 C8 上限即作废并要求重新发码)→ 消费该行 → 商家存在性(软删 400 / 禁用 403 / 自注册)。
    """
    settings = get_settings()
    normalized = _normalized_phone(phone)
    now = _now()
    _enforce_verify_window(db, normalized, now)

    row = db.execute(
        text("SELECT id, out_id, attempts FROM merchant_login_code "
             "WHERE phone = :p AND used_at IS NULL ORDER BY created_at DESC, id DESC LIMIT 1"),
        {"p": normalized}).mappings().first()
    if row is None:
        # 无可用行(未发码 / 已使用 / 已被新一轮发码作废)→ 同一句文案(防探测)
        raise ApiException(CODE_INVALID_MESSAGE, code=400, status_code=400)

    passed = sms_verify.check_verify_code(normalized, (code or "").strip(), row["out_id"] or "")
    if not passed:
        attempts = int(row["attempts"]) + 1
        reached_limit = attempts >= settings.LOGIN_CODE_MAX_ATTEMPTS
        db.execute(text("UPDATE merchant_login_code SET attempts = :a, used_at = :used WHERE id = :id"),
                   {"a": attempts, "used": now if reached_limit else None, "id": row["id"]})
        db.commit()
        logger.warning(f"登录验证码校验未通过: phone={mask_phone(normalized)} attempts={attempts}")
        if reached_limit:
            raise ApiException(VERIFY_TOO_MANY_MESSAGE, code=429, status_code=429)
        raise ApiException(CODE_INVALID_MESSAGE, code=400, status_code=400)

    # 一次性:校验通过即消费该行(先消费,防重放)
    db.execute(text("UPDATE merchant_login_code SET used_at = :now WHERE id = :id"), {"now": now, "id": row["id"]})

    merchant_row = _lookup_merchant_by_phone(db, normalized)
    is_new = False
    if merchant_row is None:
        merchant_id = MERCHANT_ID_PREFIX + secrets.token_hex(16)      # G-1:随机 ID,不含 PII
        db.add(Merchant(merchant_id=merchant_id, nickname=mask_phone(normalized), phone=normalized,
                        current_stage="onboarding", status=1, registered_at=now, last_active_at=now))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            logger.warning(f"手机号唯一键冲突(G-3:软删行仍占位): phone={mask_phone(normalized)}")
            raise ApiException(PHONE_UNAVAILABLE_MESSAGE, code=400, status_code=400)
        is_new = True
        merchant_row = {"merchant_id": merchant_id, "nickname": mask_phone(normalized), "avatar": "",
                        "merchant_name": None, "current_stage": "onboarding", "status": 1}
        logger.info(f"手机号自注册新商家: merchant_id={merchant_id} phone={mask_phone(normalized)}")
    else:
        if merchant_row["deleted_at"] is not None:
            db.commit()      # 行保持已消费
            raise ApiException(PHONE_UNAVAILABLE_MESSAGE, code=400, status_code=400)
        if int(merchant_row["status"]) != 1:
            db.commit()      # 行保持已消费
            raise ApiException(ACCOUNT_DISABLED_MESSAGE, code=403, status_code=403)
        db.execute(text("UPDATE merchant SET last_active_at = :now WHERE merchant_id = :mid"),
                   {"now": now, "mid": merchant_row["merchant_id"]})
        db.commit()

    token = create_merchant_token(merchant_row["merchant_id"])
    if is_new and background_tasks is not None:
        # 注册事务已 commit → 旁路异步内部通知(任何失败都不影响 201)
        background_tasks.add_task(notify_merchant_registered, merchant_row["merchant_id"], normalized)
    logger.info(f"手机号登录成功: merchant_id={merchant_row['merchant_id']} is_new={is_new}")
    return {"token": token, "merchant": _merchant_projection(merchant_row), "is_new_merchant": is_new}
