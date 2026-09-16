"""内部通知(内部飞书 IM 通道;新商家注册 #PB-23 / 任务单 #PL-4 §七 + 京麦ID重复登记 #PB-36 §5.3)。

**独立通道**:不复用面向商家的 `feishu_notification`(后者是商家维度 + `template_type` 枚举 + 48h 频控,
塞内部通知会污染商家通知语义)。发送实现沿用已在依赖内的 `lark-oapi`(`im.v1.message.create`)。

硬口径:
- **旁路**:注册/签发 token 的事务**先 commit**,再由 FastAPI `BackgroundTasks` 调用本模块;
  **任何异常都不得向上抛**(只落 `internal_notify_log` + `logger.warning`),绝不影响 HTTP 201;
- **幂等**:同 `(event_type, merchant_id)` 已有 `status="sent"` 行即跳过(同一商家只通知一次);
- **内容最小化**:只含**脱敏手机号** + merchant_id + 时间,**不含 token/密钥/完整手机号**;
- 接收方:`INTERNAL_NOTIFY_RECEIVE_ID_TYPE`(默认 `open_id`)/ `INTERNAL_NOTIFY_RECEIVE_ID`(**必填,只由 `.env`/环境变量注入**,源码默认空串、不硬编码 PII;#PB-37 A);
  留空 = 未配置 → 通知**显式跳过**并记日志(`_notify_skip_reason`),不拒启动、不影响业务返回;
  email 兜底选项(`<INTERNAL_EMAIL>`)只在真源登记,**不硬编码**进代码。
"""
import json
import logging
from datetime import datetime
from typing import Any, Optional, Tuple

from sqlalchemy import text

from app.core.config import get_settings
from app.core.utils import mask_jd_merchant_id, mask_phone
from app.db.models.internal_notify_log import InternalNotifyLog
from app.db.session import SessionLocal

logger = logging.getLogger("api")

CHANNEL_FEISHU_IM = "feishu_im"
EVENT_MERCHANT_REGISTERED = "merchant_registered"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"
# 内部通知正文模板(纯文本;手机号必须是脱敏后的值)
NOTIFY_TEXT_TEMPLATE = "新商家注册\n手机号：{phone}\n商家ID：{merchant_id}\n时间：{created_at}"
# 事件 2:京麦商家ID 被别的账号申请重复登记(#PB-36 / 方案 §5.3)
# 事件名长度受列宽约束:`internal_notify_log.event_type` 为 VARCHAR(32) 且库开 STRICT_TRANS_TABLES;
# 设计稿拟的 `merchant_id_duplicate_registration`(34 字符)实测写入报 (1406) Data too long,
# 故以**已落地的 schema(#DB-19 / v1.10)为准**取语义等价的短名(方案 §4.2:DDL 以 database 单落地为准)。
EVENT_MERCHANT_ID_DUPLICATE_REGISTRATION = "jd_duplicate_registration"
DEDUPE_KEY_JD_PREFIX = "jd:"
# 去重键 = `jd:<完整 jd_merchant_id>`:**完整值只落 DB 列**(人可读、便于排障;与 merchant.jd_merchant_id 同暴露面),
# IM 正文与日志文本**一律脱敏** —— 详见 notify_duplicate_registration 的「脱敏边界」(#PB-38)
# 同一 jd_merchant_id 的重复登记通知去重窗口(小时):窗口内已有 status=sent 则只告警、不写行不发送
DUPLICATE_NOTIFY_DEDUPE_HOURS = 24
# 重复登记通知正文(申请商家ID 必须脱敏:IM 有第三方可见风险,同时保留首尾便于运营比对)
NOTIFY_DUPLICATE_TEXT_TEMPLATE = (
    "京麦商家ID重复登记申请\n申请账号：{merchant_id}\n手机号：{phone}\n"
    "申请商家ID：{jd_merchant_id}\n时间：{created_at}"
)
# `internal_notify_log.error_message` 列宽(VARCHAR(255)):超长必须截断,否则 MySQL 严格模式写入失败
ERROR_MESSAGE_MAX_CHARS = 255
# 上游 msg 的单段上限(避免一条超长上游报文把 255 列宽吃光,挤掉 code 等关键信息)
UPSTREAM_MSG_MAX_CHARS = 160


def _truncate_error_message(text: str) -> str:
    """按列宽截断失败原因(先截断、再落库/落日志,避免 1406 Data too long)。"""
    return (text or "")[:ERROR_MESSAGE_MAX_CHARS]


def _upstream_failure_detail(exc: Exception) -> str:
    """上游异常的**结构化**失败原因(保留 `exception:<类名>` 兜底,并补 `code`/`msg`;#PB-23-R5)。

    动因(lark SDK 实测):`ObtainAccessTokenException` 这类异常自带 `code`/`msg`——
    只记类名会丢掉真因(如飞书 `10014 app secret invalid`),真机排障时只能直连上游接口才看得到。
    只取 `code`/`msg`/`message` 三个属性并截断;不回显请求体、密钥、token、完整手机号。
    """
    detail = f"exception:{type(exc).__name__}"
    code = getattr(exc, "code", None)
    if code is not None:
        detail += f" code={code}"
    msg = getattr(exc, "msg", None) or getattr(exc, "message", None)
    if msg:
        detail += f" msg={str(msg)[:UPSTREAM_MSG_MAX_CHARS]!r}"
    return _truncate_error_message(detail)


def _response_ok(resp: Any) -> bool:
    """判定飞书响应是否成功(与 `services/feishu.py::_response_ok` 同口径:优先 success(),退化 code==0)。"""
    success = getattr(resp, "success", None)
    if callable(success):
        try:
            return bool(success())
        except Exception:  # noqa: BLE001 - 判定失败时退化到 code 判断
            pass
    return getattr(resp, "code", None) == 0


def _send_text(target_type: str, target: str, text: str) -> Tuple[bool, Optional[str]]:
    """发送纯文本 IM 消息;返回 (是否成功, 失败原因)。失败原因**不含密钥/完整手机号**。"""
    from app.services.feishu import _lark_client       # 复用唯一 lark 客户端构造(应用凭证 + SDK 形态)
    from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

    client = _lark_client()
    if client is None:
        return False, "lark_client_unavailable"
    body = (CreateMessageRequestBody.builder()
            .receive_id(target)
            .msg_type("text")
            .content(json.dumps({"text": text}, ensure_ascii=False))
            .build())
    request = CreateMessageRequest.builder().receive_id_type(target_type).request_body(body).build()
    resp = client.im.v1.message.create(request)
    if _response_ok(resp):
        return True, None
    # #PB-23-R5:失败原因带上飞书 code 与 msg(真机排障需要);截断至列宽内
    return False, _truncate_error_message(
        f"feishu_code={getattr(resp, 'code', None)} "
        f"msg={str(getattr(resp, 'msg', None))[:UPSTREAM_MSG_MAX_CHARS]!r}")


def _notify_skip_reason() -> Optional[str]:
    """内部通知是否应**显式跳过**(返回原因;`None` = 可发送)。#PB-37 A

    两条安全跳过路径,都只记日志、不写 `internal_notify_log` 行、不发送:
    - `INTERNAL_NOTIFY_ENABLED=false` → 明确关闭;
    - `INTERNAL_NOTIFY_RECEIVE_ID` 为空/纯空白 → **接收人未配置**(源码不硬编码 PII,值只由 .env 注入)。
    绝不因未配置而拒启动或影响业务返回——与既有「通知失败不阻塞」旁路纪律一致。
    """
    settings = get_settings()
    if not settings.INTERNAL_NOTIFY_ENABLED:
        return "INTERNAL_NOTIFY_ENABLED=false"
    if not (settings.INTERNAL_NOTIFY_RECEIVE_ID or "").strip():
        return "INTERNAL_NOTIFY_RECEIVE_ID 未配置"
    return None


def _already_sent(db, merchant_id: str) -> bool:
    """同一商家是否已成功通知过(幂等判据:`(event_type, merchant_id, status=sent)`)。"""
    row = db.execute(
        text("SELECT id FROM internal_notify_log WHERE event_type = :e AND merchant_id = :m AND status = :s LIMIT 1"),
        {"e": EVENT_MERCHANT_REGISTERED, "m": merchant_id, "s": STATUS_SENT}).first()
    return row is not None


def notify_merchant_registered(merchant_id: str, phone: str) -> None:
    """新商家注册内部通知(供 `BackgroundTasks` 调用;绝不抛异常给调用方)。"""
    settings = get_settings()
    skip_reason = _notify_skip_reason()
    if skip_reason:
        logger.info(f"内部通知跳过: event={EVENT_MERCHANT_REGISTERED} merchant_id={merchant_id} reason={skip_reason}")
        return
    db = SessionLocal()
    try:
        if _already_sent(db, merchant_id):
            logger.info(f"内部通知此前已发送,跳过: merchant_id={merchant_id}")
            return
        text_body = NOTIFY_TEXT_TEMPLATE.format(
            phone=mask_phone(phone), merchant_id=merchant_id,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        try:
            ok, reason = _send_text(settings.INTERNAL_NOTIFY_RECEIVE_ID_TYPE,
                                    settings.INTERNAL_NOTIFY_RECEIVE_ID, text_body)
        except Exception as e:  # noqa: BLE001 - 发送异常一律降级为 failed 记录
            # #PB-23-R5:保留 `exception:<类名>` 兜底,并补上游 code/msg(如飞书 10014 app secret invalid)
            ok, reason = False, _upstream_failure_detail(e)
        db.add(InternalNotifyLog(
            channel=CHANNEL_FEISHU_IM, event_type=EVENT_MERCHANT_REGISTERED, merchant_id=merchant_id,
            target_type=settings.INTERNAL_NOTIFY_RECEIVE_ID_TYPE,
            target=(settings.INTERNAL_NOTIFY_RECEIVE_ID or "")[:128],
            status=STATUS_SENT if ok else STATUS_FAILED, error_message=reason))
        db.commit()
        if not ok:
            logger.warning(f"内部通知发送失败(不影响注册): merchant_id={merchant_id} reason={reason}")
    except Exception as e:  # noqa: BLE001 - 旁路通道:任何异常都不得向上抛
        logger.warning(f"内部通知落库异常(不影响注册): merchant_id={merchant_id} error={type(e).__name__}")
        try:
            db.rollback()
        except Exception:  # noqa: BLE001 - 兜底回滚失败不再抛
            pass
    finally:
        db.close()


def _duplicate_notify_sent_within_window(db, dedupe_key: str) -> bool:
    """同一去重键在窗口内是否已成功通知过(方案 §5.3 幂等/频控:防刷爆)。"""
    # 窗口小时数是**模块常量整数**(非用户输入),直接内联进 SQL;其余全部走绑定参数。
    sql = (
        "SELECT id FROM internal_notify_log WHERE event_type = :e AND dedupe_key = :k "
        "AND status = :s AND created_at > NOW() - INTERVAL " 
        + str(int(DUPLICATE_NOTIFY_DEDUPE_HOURS)) + " HOUR LIMIT 1"
    )
    row = db.execute(
        text(sql),
        {"e": EVENT_MERCHANT_ID_DUPLICATE_REGISTRATION, "k": dedupe_key, "s": STATUS_SENT},
    ).first()
    return row is not None


def notify_duplicate_registration(merchant_id: str, phone: str, jd_merchant_id: str) -> None:
    """京麦商家ID 重复登记内部通知(供**失败响应**的 BackgroundTasks 调用;绝不抛异常给调用方)。

    去重窗口 24h:同一 `jd:<jd_merchant_id>` 已有 `status=sent` 行时只 `logger.warning`,
    **不写行、不发送**。

    脱敏边界(#PB-38 口径澄清,消除「完整值能否落库」的歧义):
    - **完整 `jd_merchant_id` 只进 DB 去重列** `internal_notify_log.dedupe_key`(人可读,便于运营/排障
      对着京麦ID 核对);该值本就完整存于 `merchant.jd_merchant_id`(管理后台可按 keyword 搜索定位),
      故 DB 内落完整值**不新增暴露面**;
    - **IM 正文与全部日志文本一律脱敏**:正文用 `mask_phone`(手机号)与 `mask_jd_merchant_id`(京麦ID 保前 4 后 4),
      日志同样只打脱敏值 —— 所谓「不进 IM 与日志」指的**只是这两处**,**不是**数据库列。
    """
    settings = get_settings()
    masked_jd = mask_jd_merchant_id(jd_merchant_id)
    skip_reason = _notify_skip_reason()
    if skip_reason:
        logger.info(f"内部通知跳过: event={EVENT_MERCHANT_ID_DUPLICATE_REGISTRATION} jd={masked_jd} reason={skip_reason}")
        return
    dedupe_key = f"{DEDUPE_KEY_JD_PREFIX}{jd_merchant_id}"
    db = SessionLocal()
    try:
        if _duplicate_notify_sent_within_window(db, dedupe_key):
            logger.warning(f"重复登记通知 {DUPLICATE_NOTIFY_DEDUPE_HOURS}h 内已发送,跳过: jd_merchant_id={masked_jd}")
            return
        text_body = NOTIFY_DUPLICATE_TEXT_TEMPLATE.format(
            merchant_id=merchant_id, phone=mask_phone(phone), jd_merchant_id=masked_jd,
            created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        try:
            ok, reason = _send_text(settings.INTERNAL_NOTIFY_RECEIVE_ID_TYPE,
                                    settings.INTERNAL_NOTIFY_RECEIVE_ID, text_body)
        except Exception as e:  # noqa: BLE001 - 发送异常一律降级为 failed 记录
            ok, reason = False, _upstream_failure_detail(e)
        db.add(InternalNotifyLog(
            channel=CHANNEL_FEISHU_IM, event_type=EVENT_MERCHANT_ID_DUPLICATE_REGISTRATION,
            merchant_id=merchant_id,
            target_type=settings.INTERNAL_NOTIFY_RECEIVE_ID_TYPE,
            target=(settings.INTERNAL_NOTIFY_RECEIVE_ID or "")[:128],
            status=STATUS_SENT if ok else STATUS_FAILED, error_message=reason, dedupe_key=dedupe_key))
        db.commit()
        if not ok:
            logger.warning(f"重复登记通知发送失败(不影响 400): jd_merchant_id={masked_jd} reason={reason}")
    except Exception as e:  # noqa: BLE001 - 旁路通道:任何异常都不得向上抛
        logger.warning(f"重复登记通知落库异常(不影响 400): jd_merchant_id={masked_jd} error={type(e).__name__}")
        try:
            db.rollback()
        except Exception:  # noqa: BLE001 - 兜底回滚失败不再抛
            pass
    finally:
        db.close()
