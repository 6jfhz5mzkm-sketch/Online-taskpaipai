"""飞书服务(对齐 backend feishu.service:advisor-qr 静态 + 通知信封 + 真实登录 lark-oapi)。

另含 API-10 的服务层实现 send_notification(48h 频控 + 发送 + 落库,触发点待定,无 HTTP 路由)。
"""
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("api")

from app.core.config import FEISHU_SECRET_PLACEHOLDERS, get_settings
from app.core.exceptions import ApiException
from app.db.models.feishu_notification import FeishuNotification

settings = get_settings()

# ---- API-10 通知模板与频控口径 ----

# 模板枚举:前 4 项取自真源 §6.5「推送时机」措辞;后 2 项为既有 automation/src/notify.js
# 正在写入的值(登记以免被误判为非法值);标题即模板中文名,正文由调用方经 extra.content 提供,
# 本服务不创作营销文案。
NOTIFICATION_TEMPLATES: Dict[str, str] = {
    "welcome": "入驻欢迎",
    "task_reminder": "任务未完成提醒",
    "first_order_countdown": "首单倒计时",
    "stage_complete": "阶段完成祝贺",
    "fee_sync": "拍拍资费月度同步",
    "fee_sync_failed": "拍拍资费同步中止",
}

# 频控范围与窗口(真源 API-10「频率控制」:同一商家同一 template_type 最多每 2 天推送 1 次)
FREQUENCY_CONTROLLED_TEMPLATES = frozenset({"task_reminder"})
MIN_INTERVAL_HOURS = 48
H5_URL_MAX_LENGTH = 1024

def _lark_client():
    try:
        import lark_oapi as lark
        return lark.Client.builder().app_id(settings.FEISHU_APP_ID).app_secret(settings.FEISHU_APP_SECRET).build()
    except Exception as e:
        # SEC P0:该吞(飞书客户端创建失败,通知降级)但记日志
        logger.warning(f"飞书客户端创建失败: {e}")
        return None

def welcome_on_first(db: Session, merchant_id: str, open_id: str, name: str):
    """首个登录发欢迎卡片(幂等)。

    幂等标志口径(**#PB-19 修正**):`merchant.welcome_sent = 1` 表示**已成功发送**。
    - 发送成功 -> 置 1,返回 `{"sent": True, "first": True}`;
    - **发送失败 -> 不置位**(保持 0),返回 `{"sent": False, "first": True}`,下次登录可重试
      (失败原因已由 _send_card 记录飞书 code/msg);
    - 已为 1 -> 直接跳过,不调用发送,返回 `{"sent": False, "first": False}`。

    修正前无论成败都置 1,导致一次发送失败后商家**永远不会再收到欢迎卡片**
    (生产 2026-09-14 实证:_send_card 因 SDK 调用错误失败,标志仍被置 1)。
    """
    row = db.execute(text("SELECT welcome_sent FROM merchant WHERE merchant_id = :m"), {"m": merchant_id}).mappings().first()
    if row and int(row["welcome_sent"] or 0) == 1:
        return {"sent": False, "first": False}
    sent = _send_card(open_id, "测试欢迎卡片")
    if sent:
        db.execute(text("UPDATE merchant SET welcome_sent = 1 WHERE merchant_id = :m"), {"m": merchant_id})
        db.commit()
    else:
        # 发送失败:保留 welcome_sent=0 以便后续重试(不置位);不抛异常(通知属降级面)
        logger.warning("欢迎卡片发送失败,保留 welcome_sent=0 以便下次登录重试(不置位)")
    return {"sent": bool(sent), "first": True}

def stage_complete(open_id: str, name: str, stage_name: str, next_stage: Optional[str]):
    return _send_card(open_id, f"{stage_name}完成通知")

def _response_ok(resp: Any) -> bool:
    """判定飞书响应是否成功:优先用 SDK 的 success(),退化到 code == 0。"""
    success = getattr(resp, "success", None)
    if callable(success):
        try:
            return bool(success())
        except Exception:  # noqa: BLE001 - success() 判定失败时退化到 code 判断
            pass
    return getattr(resp, "code", None) == 0


def _send_card(open_id: str, content: str) -> bool:
    """发送 interactive 卡片(lark-oapi `im.v1.message.create`;**唯一发送实现**)。

    实测口径(lark-oapi 1.7.3,2026-09-14 本机 uv 环境核对):
      CreateMessageRequestBody.builder().receive_id(open_id).msg_type("interactive").content(卡片 JSON 字符串).build()
      CreateMessageRequest.builder().receive_id_type("open_id").request_body(body).build()
      client.**im.v1**.message.create(request)      # 注意是 im.v1.message;SDK 上不存在 im.message

    旧实现 `client.im.message.create(...)` 在 SDK 中不存在('ImService' object has no attribute 'message'),
    导致欢迎卡片/阶段完成/任务提醒(API-10)全部发送失败(生产实测)。
    失败为**降级面**:记录飞书 code/msg(不记 secret/token/open_id 原文)并返回 False,不抛异常。
    """
    client = _lark_client()
    if client is None:
        return False
    try:
        from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

        card = {"elements": [{"tag": "div", "text": {"tag": "lark_md", "content": content}}]}
        body = (
            CreateMessageRequestBody.builder()
            .receive_id(open_id)
            .msg_type("interactive")
            .content(json.dumps(card, ensure_ascii=False))
            .build()
        )
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("open_id")
            .request_body(body)
            .build()
        )
        resp = client.im.v1.message.create(request)
        if _response_ok(resp):
            return True
        # 可诊断性(参照 #PB-14):记飞书 code/msg,便于一眼定位;不回显 open_id
        logger.warning(
            f"飞书卡片发送失败: code={getattr(resp, 'code', None)} msg={getattr(resp, 'msg', None)!r}"
        )
        return False
    except Exception as e:
        # SEC P0:该吞(消息发送失败,通知降级)但记日志
        logger.warning(f"飞书卡片发送失败: {type(e).__name__}: {e}")
        return False

# ---- 飞书 app_access_token(内部应用凭证)与 OIDC 换 token ----
#
# 排障结论(2026-09-14 生产实测,#PB-14):
#   POST /open-apis/authen/v1/oidc/access_token 必须携带 `Authorization: Bearer <app_access_token>`,
#   否则飞书返回 code=20014「The app access token passed is invalid」且拿不到 user access_token。
#   app_access_token 需先经 POST /open-apis/auth/v3/app_access_token/internal({app_id, app_secret}) 换取。

FEISHU_BASE_URL = "https://open.feishu.cn"
APP_ACCESS_TOKEN_URL = FEISHU_BASE_URL + "/open-apis/auth/v3/app_access_token/internal"
OIDC_ACCESS_TOKEN_URL = FEISHU_BASE_URL + "/open-apis/authen/v1/oidc/access_token"
USER_INFO_URL = FEISHU_BASE_URL + "/open-apis/authen/v1/user_info"

HTTP_TIMEOUT_SECONDS = 20
# 提前刷新余量:剩余有效期不足该秒数即重新获取(避免边界上刚好过期)
APP_TOKEN_REFRESH_MARGIN_SECONDS = 300
# 飞书未返回 expire 时的兜底有效期
APP_TOKEN_FALLBACK_TTL_SECONDS = 3600

# ---- OIDC 换 token 失败的「飞书错误码 -> 用户可读文案」映射(单一真源) ----
# 只映射「用户能据此行动」的码;未列出的码一律保留附码(排障需要,用户看不懂但可截图)。
# 20003 = 授权码无效/已过期(生产实测:用户点登录时命中),应引导用户重新发起登录而非反复重试。
OIDC_ERROR_MESSAGES: Dict[int, str] = {
    20003: "登录链接已失效，请重新点击飞书登录",
}

# 授权码类错误:除映射文案外,日志附一句排障提示(授权码一次性,复用必失败)
AUTH_CODE_ERROR_CODES = frozenset({20003})

FRIENDLY_OIDC_FAILURE_MESSAGE = "飞书授权失败，请重新登录"


def _oidc_failure_message(feishu_code: Any) -> str:
    """OIDC 失败文案:已知码用可读文案(不带裸码),未知码保留附码,无码时用友好文案。

    单一真源在服务层:调用方(路由)不得再自行拼装该文案。
    """
    mapped = OIDC_ERROR_MESSAGES.get(feishu_code) if isinstance(feishu_code, int) else None
    if mapped:
        return mapped
    if feishu_code is None:
        return FRIENDLY_OIDC_FAILURE_MESSAGE
    return FRIENDLY_OIDC_FAILURE_MESSAGE + f"（飞书错误码 {feishu_code}）"


def _log_oidc_failure(feishu_code: Any, feishu_msg: Any) -> None:
    """记录飞书返回的 code/msg(含 msg 为 None 的情况);授权码类错误附排障提示。

    凭据纪律:只记飞书业务码与提示语,**绝不记录授权 code 原文**,也不记录任何 secret/token。
    """
    detail = f"code={feishu_code} msg={feishu_msg!r}"
    if feishu_code in AUTH_CODE_ERROR_CODES:
        logger.warning(f"飞书授权失败: {detail} (授权码一次性,通常为已使用或已过期)")
    else:
        logger.warning(f"飞书授权失败: {detail}")


def _monotonic() -> float:
    """单调时钟(经模块级间接层调用,测试可 monkeypatch,避免真实等待令牌过期)。"""
    return time.monotonic()


class _AppAccessTokenCache:
    """app_access_token 的进程内缓存(单条目、线程安全、有上界)。

    为什么值得缓存:每次登录都多一次换取会使登录延迟翻倍并放大飞书侧压力;
    应用凭证在有效期内完全可复用,故缓存是纯收益。

    边界(务必知悉):
    - **进程内**——多 worker/多实例各持一份,每进程首次登录各换一次,不影响正确性;
    - **上界**:应用级凭证只有一份,缓存是单条目结构,不存在无界增长;
    - 失效:剩余有效期 < refresh_margin 即重新获取;获取失败不写缓存(下次再试);
    - 并发:取用与写入都在 threading.Lock 内;低速路径(首次/过期)会持锁发起网络请求,
      并发登录因此串行等待一次获取,属有意取舍(避免惊群重复外呼)。
    """

    def __init__(self, clock: Callable[[], float], refresh_margin: int, fallback_ttl: int) -> None:
        self._clock = clock
        self._refresh_margin = refresh_margin
        self._fallback_ttl = fallback_ttl
        self._lock = threading.Lock()
        self._token = ""
        self._expires_at = 0.0

    def _valid(self) -> bool:
        return bool(self._token) and self._clock() < self._expires_at - self._refresh_margin

    def get(self) -> str:
        """取可用的 app_access_token;缓存失效时重新获取(失败则抛错,不写缓存)。"""
        if self._valid():
            return self._token
        with self._lock:
            # 双检:等锁期间可能已被其它线程刷新
            if self._valid():
                return self._token
            token, ttl = _request_app_access_token()
            self._token = token
            self._expires_at = self._clock() + (ttl if ttl > 0 else self._fallback_ttl)
            return token

    def clear(self) -> None:
        """清空缓存(测试隔离/运维排障)。"""
        with self._lock:
            self._token = ""
            self._expires_at = 0.0


_app_access_token_cache = _AppAccessTokenCache(
    clock=lambda: _monotonic(),
    refresh_margin=APP_TOKEN_REFRESH_MARGIN_SECONDS,
    fallback_ttl=APP_TOKEN_FALLBACK_TTL_SECONDS,
)


def _request_app_access_token() -> tuple:
    """换取 app_access_token,返回 (token, expire_seconds)。

    失败一律抛结构化 502 且**绝不降级 mock**(SEC-01);日志只记录飞书返回的 code/msg,
    绝不记录 app_secret / token / 授权 code 原文。
    """
    try:
        resp = httpx.post(
            APP_ACCESS_TOKEN_URL,
            json={"app_id": settings.FEISHU_APP_ID, "app_secret": settings.FEISHU_APP_SECRET},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 - 网络层异常统一转结构化错误
        logger.error(f"飞书 app_access_token 请求异常: {type(exc).__name__}")
        raise ApiException("飞书应用凭证获取异常，请稍后重试", code=502, status_code=502) from exc

    data = resp.json()
    token = data.get("app_access_token") or ""
    if data.get("code") != 0 or not token:
        logger.error(f"飞书 app_access_token 获取失败: code={data.get('code')} msg={data.get('msg')}")
        raise ApiException("飞书应用凭证获取失败，请稍后重试", code=502, status_code=502)
    return token, int(data.get("expire") or 0)


def send_notification(
    db: Session,
    merchant_id: str,
    template_type: str,
    extra: Optional[Dict[str, Any]] = None,
    sender: Optional[Callable[[str, str], bool]] = None,
) -> Dict[str, Any]:
    """向商家发送飞书通知并落库(API-10 服务层)。

    流程(对齐真源 §5.2 API-10):查 merchant 取飞书 id -> 频控判断 -> 发送 -> INSERT feishu_notification。
    - 绑定列取 `merchant.feishu_open_id`(实测唯一被写入的飞书绑定列,且与本模块 _send_card 的
      receive_id_type='open_id' 一致;真源原文写 feishu_user_id,已在 §5.2 修正并登记 §9.7)。
    - 频控:仅对 FREQUENCY_CONTROLLED_TEMPLATES(task_reminder)生效,窗口 MIN_INTERVAL_HOURS(48h);
      命中则直接返回 skipped,不发送、不落库、不报错(真源「频率超限 → 跳过,不报错」)。
    - 发送失败不抛异常(通知属降级面,历史 SEC 结论):落库 status='failed' + error_msg 并在返回值
      给出 success=False;HTTP 层(触发点确定后再接线)按契约映射为 502。
    - sender 可注入:测试与本地不对真实飞书外呼;默认走 _send_card。

    返回:{success, notification_id, skipped, reason}。
    """
    if not merchant_id or not str(merchant_id).strip():
        raise ApiException("merchant_id 不能为空", code=400, status_code=400)
    if template_type not in NOTIFICATION_TEMPLATES:
        raise ApiException("template_type 不在枚举范围", code=400, status_code=400)

    row = db.execute(
        text("SELECT feishu_open_id FROM merchant WHERE merchant_id = :m AND deleted_at IS NULL"),
        {"m": merchant_id},
    ).mappings().first()
    if row is None:
        raise ApiException("商家不存在", code=400, status_code=400)
    open_id = row["feishu_open_id"]
    if not open_id:
        raise ApiException("商家未绑定飞书", code=400, status_code=400)

    extra = extra or {}
    if template_type in FREQUENCY_CONTROLLED_TEMPLATES:
        last = db.execute(
            text(
                "SELECT sent_at FROM feishu_notification WHERE merchant_id = :m AND template_type = :t "
                "AND deleted_at IS NULL ORDER BY sent_at DESC, id DESC LIMIT 1"
            ),
            {"m": merchant_id, "t": template_type},
        ).mappings().first()
        last_sent = last["sent_at"] if last else None
        if last_sent is not None and datetime.now() - last_sent < timedelta(hours=MIN_INTERVAL_HOURS):
            return {"success": True, "notification_id": None, "skipped": True, "reason": "frequency_limited"}

    title = NOTIFICATION_TEMPLATES[template_type]
    content = str(extra.get("content") or title)
    h5_url = extra.get("h5_url")
    h5_url = str(h5_url)[:H5_URL_MAX_LENGTH] if h5_url else None

    ok = (sender or _send_card)(open_id, content)

    record = FeishuNotification(
        merchant_id=merchant_id,
        template_type=template_type,
        title=title,
        content=content,
        h5_url=h5_url,
        status="sent" if ok else "failed",
        sent_at=datetime.now(),
        error_msg=None if ok else "飞书消息发送失败",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    if not ok:
        # 通知降级面:记日志 + 落 failed 记录,不向调用方抛异常(HTTP 层再按契约映射 502)
        logger.warning(f"飞书通知发送失败: merchant={merchant_id} template={template_type} id={record.id}")
    return {
        "success": bool(ok),
        "notification_id": str(record.id),
        "skipped": False,
        "reason": None if ok else "send_failed",
    }


# 登录不可用时**给商家看**的白话文案:不出现环境变量名、不出现「未配置/占位」这类运维语(#PB-31 用户裁决)。
# 具体是哪个变量、缺失还是占位,只写日志(见 login_feishu 的 fail-fast 分支)。
FEISHU_LOGIN_UNAVAILABLE_MESSAGE = "登录服务暂不可用，请稍后重试或联系管理员"


def _feishu_secret_state(value: Optional[str]) -> str:
    """FEISHU_APP_SECRET 的合规状态:missing / placeholder / set(只回状态,不回显任何密钥材料)。"""
    secret = (value or "").strip()
    if not secret:
        return "missing"
    return "placeholder" if secret in FEISHU_SECRET_PLACEHOLDERS else "set"


def login_feishu(db: Session, code: str) -> dict:
    """真实飞书登录(SEC-01):app_access_token -> code 换 user_access_token -> user_info。失败抛错,绝不降级 mock。

    三步(2026-09-14 生产实测口径,#PB-14):
    1. POST /open-apis/auth/v3/app_access_token/internal  {app_id, app_secret} -> app_access_token(进程内缓存,见 _AppAccessTokenCache);
    2. POST /open-apis/authen/v1/oidc/access_token  **headers: Authorization: Bearer <app_access_token>**,
       body {grant_type, code, client_id, client_secret} -> data.access_token(user_access_token);
       **缺该 Bearer 头时飞书返回 code=20014「The app access token passed is invalid」**(本次排障根因);
    3. GET /open-apis/authen/v1/user_info (Authorization: Bearer <user_access_token>) -> data.{open_id, union_id, name, avatar_url}。

    说明:原注释所称「与 NestJS 实现等价」不成立——NestJS 版从未在真实飞书环境验证过,
    其调用方式同样缺少 app_access_token 头;当前实现以生产实测为准。
    返回 {open_id, union_id, name, avatar}。
    """
    if not code or not code.strip():
        raise ApiException("授权码不能为空", code=400, status_code=400)
    # fail-fast: 凭证缺失/占位 -> 502(不静默、不降级 mock;生产必须真实 FEISHU_APP_SECRET)。
    # #PB-31:用户只看到白话文案;判定依据(哪个变量、缺失还是占位)**只进日志**,供运维排障。
    # 占位清单复用 app/core/config.py::FEISHU_SECRET_PLACEHOLDERS(单一真源,不再就地内联一份)。
    secret_state = _feishu_secret_state(settings.FEISHU_APP_SECRET)
    if not settings.FEISHU_APP_ID or secret_state != "set":
        logger.error(
            "飞书登录凭证不合规(fail-fast,不降级 mock): "
            f"app_id={'missing' if not settings.FEISHU_APP_ID else 'set'}, "
            f"app_secret={secret_state}, required_env=[FEISHU_APP_ID, FEISHU_APP_SECRET]")
        raise ApiException(FEISHU_LOGIN_UNAVAILABLE_MESSAGE, code=502, status_code=502)

    # 1) 取 app_access_token(带缓存;失败抛 502,不降级)
    app_access_token = _app_access_token_cache.get()

    # 2) code 换 user_access_token(必须带 app_access_token 的 Bearer 头)
    try:
        resp = httpx.post(
            OIDC_ACCESS_TOKEN_URL,
            headers={"Authorization": f"Bearer {app_access_token}"},
            json={"grant_type": "authorization_code", "code": code,
                  "client_id": settings.FEISHU_APP_ID, "client_secret": settings.FEISHU_APP_SECRET},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
    except Exception as e:
        logger.error(f"飞书 OIDC 换 token 请求异常: {type(e).__name__}")
        raise ApiException("飞书登录网络异常，请稍后重试", code=502, status_code=502) from e
    data = resp.json()
    if data.get("code") != 0 or not (data.get("data") or {}).get("access_token"):
        # 日志:飞书 code/msg(含 msg 为 None);文案:服务层统一映射(见 _oidc_failure_message)
        feishu_code = data.get("code")
        _log_oidc_failure(feishu_code, data.get("msg"))
        raise ApiException(_oidc_failure_message(feishu_code), code=401, status_code=401)
    access_token = data["data"]["access_token"]

    # 3) user_info(用换到的 user_access_token 做 Bearer)
    try:
        r2 = httpx.get(USER_INFO_URL, headers={"Authorization": f"Bearer {access_token}"},
                       timeout=HTTP_TIMEOUT_SECONDS)
    except Exception as e:
        logger.error(f"飞书 user_info 请求异常: {type(e).__name__}")
        raise ApiException("飞书登录获取用户信息异常，请稍后重试", code=502, status_code=502) from e
    d2 = r2.json()
    if d2.get("code") != 0:
        logger.warning(f"飞书 user_info 失败: code={d2.get('code')} msg={d2.get('msg')}")
        raise ApiException(f"飞书登录获取用户信息失败（飞书错误码 {d2.get('code')}）", code=401, status_code=401)
    u = d2.get("data") or {}
    open_id = u.get("open_id")
    if not open_id:
        logger.warning("飞书 user_info 未返回 open_id")
        raise ApiException("飞书登录失败，未获取到用户 open_id", code=401, status_code=401)
    return {"open_id": open_id, "union_id": u.get("union_id"), "name": u.get("name"), "avatar": u.get("avatar_url")}