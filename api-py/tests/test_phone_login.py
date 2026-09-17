"""商家手机号 + 短信验证码登录(#PB-23;PNVS 短信认证口径,#PL-4 §11.1 覆盖清单)。

硬性打桩:`SendSmsVerifyCode` / `CheckSmsVerifyCode` / `VerifyCaptcha` **全部打桩/替身**
(**绝不发真实短信、绝不调用任何云产品**);IM 通知同样打桩或降级注入。
隔离:手机号唯一随机;`merchant_login_code` / `internal_notify_log` **先记 id 再按 id 删**;
商家行复用 `tests/conftest.py::cleanup_temp_merchant`;`captcha_daily_counter`(1 行/天共享计数器)用例前后快照还原。
"""
import hashlib
import hmac
import json
import logging
import os
import random
from datetime import datetime, timedelta

import httpx
import pytest
from sqlalchemy import bindparam, text
from types import SimpleNamespace

from app.core.config import get_settings
from app.core.exceptions import ApiException
from app.core.security import decode_token
from app.core.utils import mask_phone
from app.db.engine import engine
from app.db.session import SessionLocal
from app.services import captcha as captcha_service
from app.services import feishu as feishu_service
from app.services import internal_notify, phone_auth, sms_verify

from tests.conftest import cleanup_temp_merchant, make_temp_merchant

SEND_PATH = "/api/auth/phone/send-code"
LOGIN_PATH = "/api/auth/phone/login"
CAPTCHA_PARAM = "opaque-captcha-param"


def _phone() -> str:
    """唯一合法手机号(11 位、`1[3-9]` 开头),避免与其它用例/存量数据串号。"""
    return "139" + "".join(str(random.randint(0, 9)) for _ in range(8))


def _stub_send(monkeypatch) -> list:
    """打桩 PNVS 下发(唯一短信出口):记录 (phone, out_id),返回固定 biz_id。"""
    calls = []

    def fake_send(phone, out_id):
        calls.append({"phone": phone, "out_id": out_id})
        return "biz-test-0001"

    monkeypatch.setattr(phone_auth.sms_verify, "send_verify_code", fake_send)
    return calls


def _stub_check(monkeypatch, *, passed: bool = True) -> list:
    """打桩 PNVS 校验:默认 PASS;可切换为未通过(UNKNOWN)。"""
    calls = []

    def fake_check(phone, code, out_id):
        calls.append({"phone": phone, "code": code, "out_id": out_id})
        return passed

    monkeypatch.setattr(phone_auth.sms_verify, "check_verify_code", fake_check)
    return calls


def _stub_captcha_ok(monkeypatch) -> list:
    calls = []

    def fake_verify(param, client_ip):
        calls.append({"param": param, "ip": client_ip})

    monkeypatch.setattr(phone_auth.captcha, "verify_captcha_or_raise", fake_verify)
    return calls


def _seed_row(session, phone: str, *, attempts: int = 0, used_at=None, created_at=None,
              ip: str = "127.0.0.1", out_id: str = "login-seed", biz_id: str = "biz-seed") -> int:
    """直接插一行登录码记录(构造频控/错次/作废等前置状态);只写 8 列结构里的列。"""
    session.execute(
        text("INSERT INTO merchant_login_code (phone, biz_id, out_id, ip, attempts, used_at, created_at) "
             "VALUES (:p, :biz, :out, :ip, :a, :u, :c)"),
        {"p": phone, "biz": biz_id, "out": out_id, "ip": ip, "a": attempts, "u": used_at,
         "c": created_at or datetime.now()})
    session.commit()
    return int(session.execute(
        text("SELECT id FROM merchant_login_code WHERE phone = :p ORDER BY id DESC LIMIT 1"), {"p": phone}).scalar())


def _freeze_phone_auth_clock(monkeypatch, hour: int = 12, minute: int = 0) -> datetime:
    """把产品侧时钟缝 `phone_auth._now()` 冻结到「今天的 hour:minute」,并返回该时刻供造行(#T-21)。

    背景(时间脆弱性):频控配额是**自然日**口径(`phone_auth._enforce_send_limits` 里
    `day_start = now.replace(hour=0, ...)`)。C3 日上限用例用真实 `datetime.now()` 造
    `now - timedelta(hours=2..11)` 共 10 行(恰等于 `LOGIN_CODE_PHONE_DAILY_MAX`),但当**真实本地
    时间 < 11:00** 时,hour=10/11 两行落到**前一天**,当日计数只有 8 行 ⇒ 不触发 C3 ⇒ 期望 429 实得 200。

    冻结到 12:00 后(>= 11:00),10 行全部落在同一自然日,判定与真实时钟无关;小时窗口计数仍为 0
    (h>=2 的行都在 now-1h 之前),故不会抢先触发 C2。调用方必须用返回的 frozen 造行 —— 冻结产品时钟
    却仍按真实 now 造行,种子行与判定窗口会不同源,断言依旧会红。
    """
    frozen = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    monkeypatch.setattr(phone_auth, "_now", lambda: frozen)
    return frozen


def _cleanup_phone(session, phone: str) -> None:
    """按 id 清理本用例造的行(先记录再删除);商家行复用 conftest 助手。"""
    merchant_ids = [r[0] for r in session.execute(
        text("SELECT merchant_id FROM merchant WHERE phone = :p"), {"p": phone}).all()]
    code_ids = [r[0] for r in session.execute(
        text("SELECT id FROM merchant_login_code WHERE phone = :p"), {"p": phone}).all()]
    notify_ids = []
    if merchant_ids:
        notify_ids = [r[0] for r in session.execute(
            text("SELECT id FROM internal_notify_log WHERE merchant_id IN :mids")
            .bindparams(bindparam("mids", expanding=True)), {"mids": merchant_ids}).all()]
    print(f"[#PB-23 清理] phone={mask_phone(phone)} code_ids={code_ids} notify_ids={notify_ids} merchant_ids={merchant_ids}")
    if code_ids:
        session.execute(text("DELETE FROM merchant_login_code WHERE id IN :ids")
                        .bindparams(bindparam("ids", expanding=True)), {"ids": code_ids})
    if notify_ids:
        session.execute(text("DELETE FROM internal_notify_log WHERE id IN :ids")
                        .bindparams(bindparam("ids", expanding=True)), {"ids": notify_ids})
    session.commit()
    for merchant_id in merchant_ids:
        cleanup_temp_merchant(session, merchant_id)


@pytest.fixture()
def session():
    """本文件专用会话:**READ COMMITTED** —— 端点用另一连接提交,默认 REPEATABLE READ 会读到旧快照。"""
    s = SessionLocal(bind=engine.execution_options(isolation_level="READ COMMITTED"))
    yield s
    s.close()


@pytest.fixture(autouse=True)
def stub_im_channel(monkeypatch):
    """**默认打桩**内部通知发送:任何用例都不得打真实飞书通道(需要失败/成功语义的用例自行再 patch)。

    #PB-37 A:接收人默认值改为空串(源码不硬编码 PII)→ 此处**显式注入测试接收人**并清 settings 缓存,
    否则本文件的通知用例会随部署方 .env 是否配置接收人而时绿时红。
    """
    from app.core.config import get_settings

    monkeypatch.setenv("INTERNAL_NOTIFY_RECEIVE_ID", "<OPEN_ID>_receive_id")
    get_settings.cache_clear()
    monkeypatch.setattr(internal_notify, "_send_text",
                        lambda target_type, target, text: (True, None))
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def restore_captcha_counter(session):
    """`captcha_daily_counter` 是 1 行/天的**共享**计数器:用例前后快照并还原(C7 预算不被测试污染)。"""
    today = datetime.now().date()
    before = session.execute(text("SELECT used FROM captcha_daily_counter WHERE day = :d"), {"d": today}).scalar()
    yield
    if before is None:
        session.execute(text("DELETE FROM captcha_daily_counter WHERE day = :d"), {"d": today})
    else:
        session.execute(text("UPDATE captcha_daily_counter SET used = :u WHERE day = :d"),
                        {"u": int(before), "d": today})
    session.commit()


# ---- 1) 发码契约 / PNVS 参数 / 防枚举 ----


def test_send_code_success_contract_fields(client, session, monkeypatch):
    phone = _phone()
    send_calls = _stub_send(monkeypatch)
    _stub_captcha_ok(monkeypatch)
    try:
        resp = client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": CAPTCHA_PARAM})
        assert resp.status_code == 200, resp.text
        settings = get_settings()
        assert resp.json()["data"] == {"sent": True,
                                       "cooldown_seconds": settings.LOGIN_CODE_COOLDOWN_SECONDS,
                                       "expires_in_seconds": settings.LOGIN_CODE_TTL_MINUTES * 60,
                                       "code_length": settings.LOGIN_CODE_LENGTH}
        assert phone not in json.dumps(resp.json(), ensure_ascii=False)      # 不回显完整手机号
        assert len(send_calls) == 1 and send_calls[0]["phone"] == phone
        row = session.execute(text("SELECT biz_id, out_id, attempts, used_at FROM merchant_login_code "
                                   "WHERE phone = :p"), {"p": phone}).mappings().first()
        assert row["biz_id"] == "biz-test-0001" and row["out_id"] == send_calls[0]["out_id"]
        assert int(row["attempts"]) == 0 and row["used_at"] is None
    finally:
        _cleanup_phone(session, phone)


def test_send_verify_code_request_matches_pnvs_contract(client, session, monkeypatch):
    """SDK 请求字段级断言:ReturnVerifyCode=false(不接收明文码) / ValidTime / Interval 取自常量。"""
    phone = _phone()
    captured = []
    monkeypatch.setattr(get_settings(), "ALIYUN_SMS_ACCESS_KEY_ID", "test-ak")
    monkeypatch.setattr(get_settings(), "ALIYUN_SMS_ACCESS_KEY_SECRET", "test-sk")
    _stub_captcha_ok(monkeypatch)

    class _Body:
        success = True
        code = "OK"
        message = "OK"
        request_id = "rid"

        class model:
            biz_id = "biz-xyz"
            out_id = "out-xyz"
            verify_code = "SHOULD-NEVER-BE-READ"      # 故意放一个明文码,断言我们既不落库也不打印

    class _Resp:
        body = _Body()

    class _Client:
        def __init__(self, config):
            pass

        def send_sms_verify_code(self, request):
            captured.append(request)
            return _Resp()

    monkeypatch.setattr(sms_verify, "SmsVerifyClient", _Client)
    settings = get_settings()
    try:
        resp = client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": CAPTCHA_PARAM})
        assert resp.status_code == 200, resp.text
        assert len(captured) == 1
        request = captured[0]
        assert request.phone_number == phone
        assert request.sign_name == settings.ALIYUN_SMS_SIGN_NAME == "恒创联众科技"
        assert request.template_code == settings.ALIYUN_SMS_TEMPLATE_CODE == "100001"
        assert request.return_verify_code is False
        assert request.valid_time == settings.LOGIN_CODE_TTL_MINUTES * 60
        assert request.interval == settings.LOGIN_CODE_COOLDOWN_SECONDS
        assert request.code_length == settings.LOGIN_CODE_LENGTH and request.code_type == 1
        assert request.country_code == "86" and request.duplicate_policy == 1
        params = json.loads(request.template_param)
        assert params["min"] == settings.LOGIN_CODE_TTL_MINUTES
        assert params["code"] == sms_verify.TEMPLATE_CODE_PLACEHOLDER
        row = session.execute(text("SELECT biz_id, out_id FROM merchant_login_code WHERE phone = :p"),
                              {"p": phone}).mappings().first()
        assert row["biz_id"] == "biz-xyz" and row["out_id"] == request.out_id
        assert "SHOULD-NEVER-BE-READ" not in json.dumps(dict(row))
    finally:
        _cleanup_phone(session, phone)


def test_send_code_anti_enumeration_new_and_existing_identical(client, session, monkeypatch):
    phone_new, phone_old = _phone(), _phone()
    _stub_send(monkeypatch)
    _stub_captcha_ok(monkeypatch)
    existing_id = make_temp_merchant(session)
    session.execute(text("UPDATE merchant SET phone = :p WHERE merchant_id = :m"), {"p": phone_old, "m": existing_id})
    session.commit()
    try:
        first = client.post(SEND_PATH, json={"phone": phone_new, "captcha_verify_param": CAPTCHA_PARAM})
        second = client.post(SEND_PATH, json={"phone": phone_old, "captcha_verify_param": CAPTCHA_PARAM})
        assert first.status_code == second.status_code == 200
        assert first.json() == second.json()
    finally:
        # #PB-23-R1:临时商家必须**显式按 id 清理**——若先 `SET phone = NULL` 再按 phone 反查,必然查不到,
        # 每次全量都会泄漏 1 行 `_test_shop_*`(确定性缺陷)。此处直接复用 conftest 助手按 id 删除
        # (覆盖范围 = scripts/merchant_scope.py 的动态发现,含驼峰 merchant_task_progress.merchantId)。
        cleanup_temp_merchant(session, existing_id)
        _cleanup_phone(session, phone_old)
        _cleanup_phone(session, phone_new)


def test_phone_format_invalid_400(client, session):
    resp = client.post(SEND_PATH, json={"phone": "12345", "captcha_verify_param": CAPTCHA_PARAM})
    assert resp.status_code == 400
    assert resp.json() == {"code": 400, "message": phone_auth.PHONE_INVALID_MESSAGE, "data": None}

# ---- 2) 人机校验接缝(图形认证服务端二次校验;fail-closed) ----

# 官方口径:`POST {CAPTCHA_API_SERVER}/validate?captcha_id=<appId>`,请求体 **form-urlencoded**,
# 参数 lot_number/captcha_output/pass_token/gen_time/sign_token,签名 = HMAC-SHA256(appKey, lot_number)。
CAPTCHA_APP_ID = "test-app-id"
CAPTCHA_APP_KEY = "test-app-key"
LOT_NUMBER = "4dc3cfc2cdff448cad8d13107198d473"


class _LogCapture:
    """收集 `api` logger(>=WARNING)的日志文本,便于断言脱敏口径。"""

    def __init__(self, caplog, level: int = logging.WARNING) -> None:
        self._caplog = caplog
        self._level = level
        self._ctx = None

    def __enter__(self):
        self._ctx = self._caplog.at_level(self._level, logger="api")
        self._ctx.__enter__()
        return self

    def __exit__(self, *exc_info):
        return self._ctx.__exit__(*exc_info)

    def text(self) -> str:
        return "\n".join(record.getMessage() for record in self._caplog.records)

    def __contains__(self, item) -> bool:
        return item in self.text()


def caplog_at_warning(caplog) -> _LogCapture:
    return _LogCapture(caplog)


def caplog_at_info(caplog) -> _LogCapture:
    """业务级「校验未通过」是 `logger.info`,捕获需降到 INFO。"""
    return _LogCapture(caplog, logging.INFO)


def _captcha_param(lot_number: str = LOT_NUMBER) -> str:
    """前端 `getValidate()` 回传的 4 字段 + captcha_id(**其中 captcha_id 必须被服务端忽略**)。"""
    return json.dumps({"lot_number": lot_number, "captcha_output": "out-1", "pass_token": "pass-1",
                       "gen_time": "1700000000", "captcha_id": "spoofed-by-client"}, ensure_ascii=False)


class _HttpResp:
    def __init__(self, payload, status_code: int = 200) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = "not-json-body" if payload is None else json.dumps(payload, ensure_ascii=False)

    def json(self):
        if self._payload is None:
            raise ValueError("invalid json")
        return self._payload


def _stub_captcha_http(monkeypatch, *, payload=None, status_code: int = 200, raises=None) -> list:
    """打桩二次校验 HTTP(`captcha.httpx.post`),记录完整请求以供格式/签名断言。"""
    monkeypatch.setattr(get_settings(), "CAPTCHA_APP_ID", CAPTCHA_APP_ID)
    monkeypatch.setattr(get_settings(), "CAPTCHA_APP_KEY", CAPTCHA_APP_KEY)
    calls = []

    def fake_post(url, params=None, data=None, timeout=None, **kwargs):
        calls.append({"url": url, "params": params, "data": data, "timeout": timeout, "extra": kwargs})
        if raises is not None:
            raise raises
        return _HttpResp(payload, status_code)

    # 注入替身 httpx(`raising=False`:改前实现根本没导入 httpx,注入后仍应表现为**行为红**)
    monkeypatch.setattr(captcha_service, "httpx", SimpleNamespace(post=fake_post), raising=False)
    return calls


def test_captcha_success_allows_send_code(client, session, monkeypatch):
    """① `status=success` + `result=success` → 放行发码(200)。"""
    phone = _phone()
    send_calls = _stub_send(monkeypatch)
    http_calls = _stub_captcha_http(monkeypatch, payload={"status": "success", "result": "success", "reason": ""})
    try:
        resp = client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": _captcha_param()})
        assert resp.status_code == 200, resp.text
        assert len(http_calls) == 1
        assert len(send_calls) == 1
    finally:
        _cleanup_phone(session, phone)


def test_captcha_request_is_form_urlencoded_with_server_captcha_id(client, session, monkeypatch):
    """⑥ 请求体必须是 form-urlencoded(`data=`,不是 `json=`),URL query 带**服务端配置**的 captcha_id。"""
    phone = _phone()
    _stub_send(monkeypatch)
    http_calls = _stub_captcha_http(monkeypatch, payload={"status": "success", "result": "success", "reason": ""})
    try:
        assert client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": _captcha_param()}).status_code == 200
        call = http_calls[0]
        assert call["url"] == get_settings().CAPTCHA_API_SERVER + "/validate"
        assert call["params"] == {"captcha_id": CAPTCHA_APP_ID}          # 服务端配置,忽略客户端传的 captcha_id
        assert set(call["data"]) == {"lot_number", "captcha_output", "pass_token", "gen_time", "sign_token"}
        assert call["data"]["lot_number"] == LOT_NUMBER
        assert "json" not in call["extra"]                               # 绝不用 json= 提交
        assert call["timeout"] == get_settings().CAPTCHA_TIMEOUT_MS / 1000
    finally:
        _cleanup_phone(session, phone)


def test_captcha_sign_token_matches_hmac_sha256_vector(client, session, monkeypatch):
    """⑦ `sign_token` 必须逐字符等于独立计算的 `HMAC-SHA256(appKey, lot_number)`(固定向量)。"""
    phone = _phone()
    _stub_send(monkeypatch)
    http_calls = _stub_captcha_http(monkeypatch, payload={"status": "success", "result": "success", "reason": ""})
    expected = hmac.new(CAPTCHA_APP_KEY.encode(), LOT_NUMBER.encode(), hashlib.sha256).hexdigest()
    try:
        assert client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": _captcha_param()}).status_code == 200
        assert http_calls[0]["data"]["sign_token"] == expected
        assert len(expected) == 64 and expected.islower()
    finally:
        _cleanup_phone(session, phone)


@pytest.mark.parametrize("mode,payload,status_code,raises", [
    ("result_fail", {"status": "success", "result": "fail", "reason": "pass_token expire"}, 200, None),
    ("status_error", {"status": "error", "code": "-50005", "msg": "illegal gen_time"}, 200, None),
    ("non_json", None, 200, None),
    ("http_500", {"status": "success", "result": "success"}, 500, None),
    ("timeout", None, 200, httpx.ReadTimeout("read timed out")),
    ("conn_error", None, 200, httpx.ConnectError("connection refused")),
])
def test_captcha_upstream_failures_fail_closed(client, session, monkeypatch, caplog, mode, payload, status_code, raises):
    """②③④ `result=fail` / `status=error` / 非 JSON / HTTP 500 / 超时 / 连接异常 → **一律拒绝且不发码**。"""
    phone = _phone()
    send_calls = _stub_send(monkeypatch)
    http_calls = _stub_captcha_http(monkeypatch, payload=payload, status_code=status_code, raises=raises)
    try:
        with caplog_at_warning(caplog) as logs:
            resp = client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": _captcha_param()})
        assert resp.status_code == 400, resp.text
        assert resp.json()["message"] == captcha_service.CAPTCHA_REQUIRED_MESSAGE
        assert len(http_calls) == 1
        assert send_calls == []                                          # 关键:绝不发码
        assert session.execute(text("SELECT COUNT(*) FROM merchant_login_code WHERE phone = :p"),
                               {"p": phone}).scalar() == 0
        assert phone not in logs and _captcha_param() not in logs        # ⑧ 日志脱敏
    finally:
        _cleanup_phone(session, phone)


@pytest.mark.parametrize("bad_param", ["not-a-json", json.dumps({"lot_number": LOT_NUMBER}),
                                       json.dumps({"lot_number": "", "captcha_output": "o", "pass_token": "p", "gen_time": "1"})])
def test_captcha_invalid_param_shape_fail_closed_without_http(client, session, monkeypatch, bad_param):
    """⑤ `captcha_verify_param` 非 JSON / 缺字段 / 字段为空 → 拒绝,且**不发出**二次校验请求。"""
    phone = _phone()
    send_calls = _stub_send(monkeypatch)
    http_calls = _stub_captcha_http(monkeypatch, payload={"status": "success", "result": "success"})
    try:
        resp = client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": bad_param})
        assert resp.status_code == 400, resp.text
        assert resp.json()["message"] == captcha_service.CAPTCHA_REQUIRED_MESSAGE
        assert http_calls == [] and send_calls == []
    finally:
        _cleanup_phone(session, phone)


def test_captcha_credentials_missing_is_503_service_unavailable(client, session, monkeypatch, caplog):
    """① 凭证缺失 = **服务侧故障** → 503 + 服务不可用白话 + `logger.error`(含变量名) + 短信 0 次。"""
    phone = _phone()
    send_calls = _stub_send(monkeypatch)
    http_calls = _stub_captcha_http(monkeypatch, payload={"status": "success", "result": "success"})
    monkeypatch.setattr(get_settings(), "CAPTCHA_APP_ID", "")
    monkeypatch.setattr(get_settings(), "CAPTCHA_APP_KEY", "")
    try:
        with caplog.at_level(logging.ERROR, logger="api"):
            resp = client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": _captcha_param()})
        assert resp.status_code == 503, resp.text
        assert resp.json()["message"] == captcha_service.CAPTCHA_UNAVAILABLE_MESSAGE
        assert resp.json()["message"] == feishu_service.FEISHU_LOGIN_UNAVAILABLE_MESSAGE   # 同句同源
        assert resp.json()["message"] == "登录服务暂不可用，请稍后重试或联系管理员"
        assert "请先完成安全验证" not in resp.json()["message"]                            # 不得误报成「用户没验证」
        assert send_calls == [] and http_calls == []
        logs = "\n".join(r.getMessage() for r in caplog.records)
        assert "CAPTCHA_APP_ID" in logs and "CAPTCHA_APP_KEY" in logs                     # 缺哪个变量只进日志
        assert CAPTCHA_APP_KEY not in str(resp.json())
    finally:
        _cleanup_phone(session, phone)


def test_captcha_missing_app_key_only_is_503(client, session, monkeypatch, caplog):
    """只缺 appKey(有 appId)同样 503,且日志只点名缺失的那一个变量。"""
    phone = _phone()
    send_calls = _stub_send(monkeypatch)
    _stub_captcha_http(monkeypatch, payload={"status": "success", "result": "success"})
    monkeypatch.setattr(get_settings(), "CAPTCHA_APP_KEY", "")
    try:
        with caplog_at_warning(caplog) as logs:
            resp = client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": _captcha_param()})
        assert resp.status_code == 503 and send_calls == []
        assert "CAPTCHA_APP_KEY" in logs and "CAPTCHA_APP_ID" not in logs
    finally:
        _cleanup_phone(session, phone)


@pytest.mark.parametrize("case", ["result_fail", "status_error", "http_500", "invalid_param", "missing_param"])
def test_captcha_other_fail_closed_branches_still_400(client, session, monkeypatch, caplog, case):
    """② 回归:除「凭证缺失」外,其余 fail-closed 分支**仍是 400**,未被 503 改动波及。"""
    phone = _phone()
    send_calls = _stub_send(monkeypatch)
    payload = {"status": "success", "result": "fail", "reason": "pass_token expire"}
    status_code = 200
    param = _captcha_param()
    if case == "status_error":
        payload = {"status": "error", "code": "-50005", "msg": "illegal gen_time"}
    elif case == "http_500":
        payload, status_code = {"status": "success", "result": "success"}, 500
    elif case == "invalid_param":
        param = "not-a-json"
    elif case == "missing_param":
        param = None
    _stub_captcha_http(monkeypatch, payload=payload, status_code=status_code)
    body = {"phone": phone}
    if param is not None:
        body["captcha_verify_param"] = param
    try:
        resp = client.post(SEND_PATH, json=body)
        assert resp.status_code == 400, resp.text
        assert resp.json()["message"] == captcha_service.CAPTCHA_REQUIRED_MESSAGE
        assert send_calls == []
    finally:
        _cleanup_phone(session, phone)


def test_captcha_missing_param_fail_closed(client, session, monkeypatch):
    """未带 `captcha_verify_param` → 400(与「未通过」同句,不回显技术细节)。"""
    phone = _phone()
    send_calls = _stub_send(monkeypatch)
    _stub_captcha_http(monkeypatch, payload={"status": "success", "result": "success"})
    try:
        resp = client.post(SEND_PATH, json={"phone": phone})
        assert resp.status_code == 400
        assert resp.json()["message"] == captcha_service.CAPTCHA_REQUIRED_MESSAGE
        assert send_calls == []
    finally:
        _cleanup_phone(session, phone)


def test_captcha_logs_never_leak_app_key_or_param(client, session, monkeypatch, caplog):
    """⑧ 日志只记 status/result/reason/code/msg;不含 appKey、不含 `captcha_verify_param` 原文。"""
    phone = _phone()
    _stub_send(monkeypatch)
    _stub_captcha_http(monkeypatch, payload={"status": "success", "result": "fail", "reason": "pass_token expire"})
    try:
        with caplog_at_warning(caplog) as logs:
            assert client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": _captcha_param()}).status_code == 400
        assert CAPTCHA_APP_KEY not in logs
        assert CAPTCHA_APP_ID not in logs
        assert _captcha_param() not in logs
        assert "pass_token expire" in logs                                # 供应商 reason 必须留痕
    finally:
        _cleanup_phone(session, phone)



# ---- 3) 频控矩阵 C1~C7(本地兜底闸) ----


def test_c1_cooldown_429_with_seconds(client, session, monkeypatch):
    phone = _phone()
    _stub_send(monkeypatch)
    _stub_captcha_ok(monkeypatch)
    try:
        assert client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": CAPTCHA_PARAM}).status_code == 200
        resp = client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": CAPTCHA_PARAM})
        assert resp.status_code == 429, resp.text
        message = resp.json()["message"]
        assert message.startswith("发送过于频繁，请在 ") and message.endswith(" 秒后重试")
        seconds = int(message.split("请在 ")[1].split(" 秒")[0])
        assert 1 <= seconds <= get_settings().LOGIN_CODE_COOLDOWN_SECONDS
    finally:
        _cleanup_phone(session, phone)


def test_c2_phone_hourly_limit_429_with_seconds(client, session, monkeypatch):
    phone = _phone()
    _stub_send(monkeypatch)
    _stub_captcha_ok(monkeypatch)
    now = datetime.now()
    try:
        for offset in range(1, 6):
            _seed_row(session, phone, created_at=now - timedelta(minutes=5 * offset))
        resp = client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": CAPTCHA_PARAM})
        assert resp.status_code == 429, resp.text
        seconds = int(resp.json()["message"].split("请在 ")[1].split(" 秒")[0])
        assert 1 <= seconds <= 3600
    finally:
        _cleanup_phone(session, phone)


def test_c3_phone_daily_limit_429(client, session, monkeypatch):
    phone = _phone()
    _stub_send(monkeypatch)
    _stub_captcha_ok(monkeypatch)
    # #T-21:冻结产品时钟到 12:00 并按同一时刻造行(原用真实 now,< 11:00 时后两行落到前一天 → 假红)
    now = _freeze_phone_auth_clock(monkeypatch)
    try:
        for hour in range(2, 12):
            _seed_row(session, phone, created_at=now - timedelta(hours=hour))
        resp = client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": CAPTCHA_PARAM})
        assert resp.status_code == 429, resp.text
        assert resp.json()["message"] == phone_auth.PHONE_DAILY_LIMIT_MESSAGE
    finally:
        _cleanup_phone(session, phone)


def test_c4_c5_ip_limits_429(client, session, monkeypatch):
    """C4 小时上限(先把小时维度占满)→ C5 日上限(抬高小时上限后仍被日上限拦住)。"""
    phone = _phone()
    _stub_send(monkeypatch)
    _stub_captcha_ok(monkeypatch)
    # #T-21:同 C3 —— 第二步 C5 是 IP 的**自然日**上限:真实本地时间 00:00~00:29 时,
    # `now - timedelta(minutes=30)` 会落到前一天,IP 日计数凑不满 LOGIN_CODE_IP_DAILY_MAX
    # ⇒ 凌晨假红(同源模拟 00:15 实测 :612 断言失败)。冻结到 12:00 后与真实时钟无关;
    # C4 走相对小时窗口(now-1h),冻结后这些行仍在窗口内,不影响其语义。
    now = _freeze_phone_auth_clock(monkeypatch)
    seeded = []
    try:
        for _ in range(get_settings().LOGIN_CODE_IP_HOURLY_MAX):
            other = _phone()
            seeded.append(other)
            _seed_row(session, other, created_at=now - timedelta(minutes=2), ip="testclient")
        resp = client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": CAPTCHA_PARAM})
        assert resp.status_code == 429, resp.text
        assert resp.json()["message"] == phone_auth.IP_SEND_LIMITED_MESSAGE

        monkeypatch.setattr(get_settings(), "LOGIN_CODE_IP_HOURLY_MAX", 9999)
        for _ in range(get_settings().LOGIN_CODE_IP_DAILY_MAX - len(seeded)):
            other = _phone()
            seeded.append(other)
            _seed_row(session, other, created_at=now - timedelta(minutes=30), ip="testclient")
        daily = client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": CAPTCHA_PARAM})
        assert daily.status_code == 429, daily.text
        assert daily.json()["message"] == phone_auth.IP_SEND_LIMITED_MESSAGE
    finally:
        for other in seeded:
            _cleanup_phone(session, other)
        _cleanup_phone(session, phone)


def test_c6_global_daily_limit_503_with_error_log(client, session, monkeypatch, caplog):
    phone = _phone()
    send_calls = _stub_send(monkeypatch)
    _stub_captcha_ok(monkeypatch)
    monkeypatch.setattr(get_settings(), "LOGIN_CODE_GLOBAL_DAILY_MAX", 0)
    try:
        with caplog.at_level(logging.ERROR, logger="api"):
            resp = client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": CAPTCHA_PARAM})
        assert resp.status_code == 503, resp.text
        assert resp.json()["message"] == phone_auth.GLOBAL_SEND_LIMIT_MESSAGE
        assert send_calls == []
        assert any("全局日上限" in r.getMessage() for r in caplog.records)
    finally:
        _cleanup_phone(session, phone)


def test_c7_captcha_cost_gate_503_blocks_captcha_and_sms(client, session, monkeypatch):
    phone = _phone()
    send_calls = _stub_send(monkeypatch)
    captcha_calls = _stub_captcha_ok(monkeypatch)
    # `limit=0` 语义是「不限」;这里把上限压到 1 并预占 1 次,使本次自增后 2 > 1 触发成本闸
    monkeypatch.setattr(get_settings(), "LOGIN_CAPTCHA_DAILY_MAX", 1)
    session.execute(text("INSERT INTO captcha_daily_counter (day, used, created_at, updated_at) "
                         "VALUES (:d, 1, :now, :now) ON DUPLICATE KEY UPDATE used = 1"),
                    {"d": datetime.now().date(), "now": datetime.now()})
    session.commit()
    try:
        resp = client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": CAPTCHA_PARAM})
        assert resp.status_code == 503, resp.text
        assert captcha_calls == [] and send_calls == []
    finally:
        _cleanup_phone(session, phone)


def test_rejected_requests_do_not_count(client, session, monkeypatch):
    """被拒请求不写行:连续 3 次 429 后,该手机号行数不增长(窗口不被延后)。"""
    phone = _phone()
    _stub_send(monkeypatch)
    _stub_captcha_ok(monkeypatch)
    # #T-21:同 C3 —— 冻结时钟并按 frozen 造行,否则真实 now < 11:00 时该手机号日的行数凑不满
    now = _freeze_phone_auth_clock(monkeypatch)
    try:
        for hour in range(2, 12):
            _seed_row(session, phone, created_at=now - timedelta(hours=hour))
        before = session.execute(text("SELECT COUNT(*) FROM merchant_login_code WHERE phone = :p"), {"p": phone}).scalar()
        for _ in range(3):
            resp = client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": CAPTCHA_PARAM})
            assert resp.status_code == 429, resp.text
            assert resp.json()["message"] == phone_auth.PHONE_DAILY_LIMIT_MESSAGE
        after = session.execute(text("SELECT COUNT(*) FROM merchant_login_code WHERE phone = :p"), {"p": phone}).scalar()
        assert before == after == 10
    finally:
        _cleanup_phone(session, phone)


def test_local_gate_runs_before_captcha_seam(client, session, monkeypatch):
    """顺序口径(设计 §五):本地闸在接缝之前 —— 被频控拦下时**不调用**人机校验、不消耗短信。"""
    phone = _phone()
    send_calls = _stub_send(monkeypatch)
    captcha_calls = _stub_captcha_ok(monkeypatch)
    # #T-21:同 C3 —— 冻结时钟并按 frozen 造行(被拦下的仍是 C3 日上限这条本地闸)
    now = _freeze_phone_auth_clock(monkeypatch)
    try:
        for hour in range(2, 12):
            _seed_row(session, phone, created_at=now - timedelta(hours=hour))
        resp = client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": CAPTCHA_PARAM})
        assert resp.status_code == 429, resp.text
        assert resp.json()["message"] == phone_auth.PHONE_DAILY_LIMIT_MESSAGE
        assert send_calls == [] and captcha_calls == []
    finally:
        _cleanup_phone(session, phone)


def test_client_ip_ignores_xff(client, session, monkeypatch):
    """IP 计数取 TCP 对端,不信任客户端可控的 X-Forwarded-For。"""
    phone = _phone()
    _stub_send(monkeypatch)
    _stub_captcha_ok(monkeypatch)
    try:
        resp = client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": CAPTCHA_PARAM},
                           headers={"X-Forwarded-For": "1.2.3.4"})
        assert resp.status_code == 200, resp.text
        ip = session.execute(text("SELECT ip FROM merchant_login_code WHERE phone = :p"), {"p": phone}).scalar()
        assert ip == "testclient" and ip != "1.2.3.4"
    finally:
        _cleanup_phone(session, phone)

# ---- 4) 登录:老号 / 自注册 / 校验四态 / C8 / C10 / 禁用 / 软删 ----


def _seed_phone_merchant(session, phone: str, *, status: int = 1, deleted: bool = False) -> str:
    merchant_id = make_temp_merchant(session)
    session.execute(text("UPDATE merchant SET phone = :p, status = :s, deleted_at = :d WHERE merchant_id = :m"),
                    {"p": phone, "s": status, "d": datetime.now() if deleted else None, "m": merchant_id})
    session.commit()
    return merchant_id


def test_login_existing_merchant_201(client, session, monkeypatch):
    phone = _phone()
    merchant_id = _seed_phone_merchant(session, phone)
    _seed_row(session, phone, out_id="login-existing")
    check_calls = _stub_check(monkeypatch, passed=True)
    try:
        resp = client.post(LOGIN_PATH, json={"phone": phone, "code": "123456"})
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["is_new_merchant"] is False
        assert data["merchant"]["merchant_id"] == merchant_id
        assert decode_token(data["token"], get_settings().JWT_SECRET, ["HS256"])["merchant_id"] == merchant_id
        assert check_calls[0]["out_id"] == "login-existing"        # OutId 透传
        assert session.execute(text("SELECT used_at FROM merchant_login_code WHERE phone = :p"),
                               {"p": phone}).scalar() is not None
    finally:
        _cleanup_phone(session, phone)


def test_login_self_registration_201_creates_merchant(client, session, monkeypatch):
    phone = _phone()
    _seed_row(session, phone, out_id="login-new")
    _stub_check(monkeypatch, passed=True)
    try:
        resp = client.post(LOGIN_PATH, json={"phone": phone, "code": "654321"})
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["is_new_merchant"] is True
        merchant_id = data["merchant"]["merchant_id"]
        assert merchant_id.startswith("p_") and len(merchant_id) == 34 and phone not in merchant_id
        row = session.execute(text("SELECT phone, status, current_stage FROM merchant WHERE merchant_id = :m"),
                              {"m": merchant_id}).mappings().first()
        assert row["phone"] == phone and int(row["status"]) == 1 and row["current_stage"] == "onboarding"
    finally:
        _cleanup_phone(session, phone)


def test_login_check_unknown_400_and_counts_failure(client, session, monkeypatch):
    phone = _phone()
    _seed_phone_merchant(session, phone)
    row_id = _seed_row(session, phone)
    _stub_check(monkeypatch, passed=False)
    try:
        resp = client.post(LOGIN_PATH, json={"phone": phone, "code": "000000"})
        assert resp.status_code == 400, resp.text
        assert resp.json()["message"] == phone_auth.CODE_INVALID_MESSAGE
        row = session.execute(text("SELECT attempts, used_at FROM merchant_login_code WHERE id = :i"),
                              {"i": row_id}).mappings().first()
        assert int(row["attempts"]) == 1 and row["used_at"] is None
    finally:
        _cleanup_phone(session, phone)


def test_login_without_usable_row_400(client, session, monkeypatch):
    phone = _phone()
    _seed_phone_merchant(session, phone)
    check_calls = _stub_check(monkeypatch, passed=True)
    try:
        resp = client.post(LOGIN_PATH, json={"phone": phone, "code": "123456"})
        assert resp.status_code == 400, resp.text
        assert resp.json()["message"] == phone_auth.CODE_INVALID_MESSAGE
        assert check_calls == []                       # 无可用行时不调用外部校验
    finally:
        _cleanup_phone(session, phone)


def test_login_c8_failure_limit_voids_row(client, session, monkeypatch):
    """C8:第 5 次失败 → 429「验证尝试次数过多」且该行作废(第 6 次直接 400)。"""
    phone = _phone()
    _seed_phone_merchant(session, phone)
    _seed_row(session, phone)
    _stub_check(monkeypatch, passed=False)
    try:
        for _ in range(4):
            resp = client.post(LOGIN_PATH, json={"phone": phone, "code": "000000"})
            assert resp.status_code == 400 and resp.json()["message"] == phone_auth.CODE_INVALID_MESSAGE
        fifth = client.post(LOGIN_PATH, json={"phone": phone, "code": "000000"})
        assert fifth.status_code == 429, fifth.text
        assert fifth.json()["message"] == phone_auth.VERIFY_TOO_MANY_MESSAGE
        voided = session.execute(text("SELECT used_at FROM merchant_login_code WHERE phone = :p"),
                                 {"p": phone}).scalar()
        assert voided is not None
        sixth = client.post(LOGIN_PATH, json={"phone": phone, "code": "123456"})
        assert sixth.status_code == 400, sixth.text
    finally:
        _cleanup_phone(session, phone)


def test_login_c10_verify_window_429(client, session, monkeypatch):
    phone = _phone()
    _seed_phone_merchant(session, phone)
    _seed_row(session, phone, attempts=10)              # 窗口内失败次数已达上限
    check_calls = _stub_check(monkeypatch, passed=True)
    try:
        resp = client.post(LOGIN_PATH, json={"phone": phone, "code": "123456"})
        assert resp.status_code == 429, resp.text
        assert resp.json()["message"] == phone_auth.VERIFY_TOO_MANY_MESSAGE
        assert check_calls == []
    finally:
        _cleanup_phone(session, phone)


def test_new_send_invalidates_previous_rows(client, session, monkeypatch):
    phone = _phone()
    _seed_row(session, phone, out_id="login-old")
    _stub_send(monkeypatch)
    _stub_captcha_ok(monkeypatch)
    monkeypatch.setattr(get_settings(), "LOGIN_CODE_COOLDOWN_SECONDS", 0)
    try:
        assert client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": CAPTCHA_PARAM}).status_code == 200
        usable = session.execute(text("SELECT out_id FROM merchant_login_code WHERE phone = :p AND used_at IS NULL"),
                                 {"p": phone}).all()
        assert len(usable) == 1 and usable[0][0] != "login-old"      # 旧行已被作废
    finally:
        _cleanup_phone(session, phone)


def test_login_disabled_merchant_403(client, session, monkeypatch):
    phone = _phone()
    _seed_phone_merchant(session, phone, status=0)
    _seed_row(session, phone)
    _stub_check(monkeypatch, passed=True)
    try:
        resp = client.post(LOGIN_PATH, json={"phone": phone, "code": "123456"})
        assert resp.status_code == 403, resp.text
        assert resp.json()["message"] == phone_auth.ACCOUNT_DISABLED_MESSAGE
    finally:
        _cleanup_phone(session, phone)


def test_login_soft_deleted_merchant_400(client, session, monkeypatch):
    phone = _phone()
    _seed_phone_merchant(session, phone, deleted=True)
    _seed_row(session, phone)
    _stub_check(monkeypatch, passed=True)
    try:
        resp = client.post(LOGIN_PATH, json={"phone": phone, "code": "123456"})
        assert resp.status_code == 400, resp.text
        assert resp.json()["message"] == phone_auth.PHONE_UNAVAILABLE_MESSAGE
    finally:
        _cleanup_phone(session, phone)


def test_login_phone_format_invalid_400(client, session):
    resp = client.post(LOGIN_PATH, json={"phone": "123", "code": "123456"})
    assert resp.status_code == 400
    assert resp.json()["message"] == phone_auth.PHONE_INVALID_MESSAGE


def test_check_provider_exception_fail_closed_502(client, session, monkeypatch):
    """校验通道异常 → 502 且**不放行**(不签发 token、不消费该行)。"""
    phone = _phone()
    _seed_phone_merchant(session, phone)
    row_id = _seed_row(session, phone)

    def boom(phone_number, code, out_id):
        raise ApiException(sms_verify.SMS_UNAVAILABLE_MESSAGE, code=502, status_code=502)

    monkeypatch.setattr(phone_auth.sms_verify, "check_verify_code", boom)
    try:
        resp = client.post(LOGIN_PATH, json={"phone": phone, "code": "123456"})
        assert resp.status_code == 502, resp.text
        assert resp.json()["message"] == sms_verify.SMS_UNAVAILABLE_MESSAGE
        assert "token" not in json.dumps(resp.json(), ensure_ascii=False)
        assert session.execute(text("SELECT used_at FROM merchant_login_code WHERE id = :i"),
                               {"i": row_id}).scalar() is None
    finally:
        _cleanup_phone(session, phone)


def test_check_unconfigured_fail_closed_502(client, session, monkeypatch):
    """凭证未配置(真实适配层,未打桩)→ 502,绝不放行。"""
    phone = _phone()
    _seed_phone_merchant(session, phone)
    _seed_row(session, phone)
    monkeypatch.setattr(get_settings(), "ALIYUN_SMS_ACCESS_KEY_ID", "")
    monkeypatch.setattr(get_settings(), "ALIYUN_SMS_ACCESS_KEY_SECRET", "")
    try:
        resp = client.post(LOGIN_PATH, json={"phone": phone, "code": "123456"})
        assert resp.status_code == 502, resp.text
        assert resp.json()["message"] == sms_verify.SMS_UNAVAILABLE_MESSAGE
    finally:
        _cleanup_phone(session, phone)


def test_send_unconfigured_fail_closed_502(client, session, monkeypatch):
    """发码侧凭证未配置 → 502(且不写行)。"""
    phone = _phone()
    _stub_captcha_ok(monkeypatch)
    monkeypatch.setattr(get_settings(), "ALIYUN_SMS_ACCESS_KEY_ID", "")
    monkeypatch.setattr(get_settings(), "ALIYUN_SMS_ACCESS_KEY_SECRET", "")
    try:
        resp = client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": CAPTCHA_PARAM})
        assert resp.status_code == 502, resp.text
        assert resp.json()["message"] == sms_verify.SMS_UNAVAILABLE_MESSAGE
        assert session.execute(text("SELECT COUNT(*) FROM merchant_login_code WHERE phone = :p"),
                               {"p": phone}).scalar() == 0
    finally:
        _cleanup_phone(session, phone)

# ---- 6) PNVS 接入点与异常可诊断性(#PB-23-R4) ----


def test_pnvs_endpoint_default_is_dypnsapi():
    """默认接入点必须是 PNVS(dypnsapi);写成 dysmsapi 会 InvalidAction.NotFound → 502(真机根因)。"""
    from app.core.config import Settings

    assert Settings.model_fields["ALIYUN_SMS_ENDPOINT"].default == "dypnsapi.aliyuncs.com"
    # 清空环境变量覆盖(且忽略 .env)后,仍必须解析出 PNVS 接入点
    os.environ.pop("ALIYUN_SMS_ENDPOINT", None)
    assert Settings(_env_file=None).ALIYUN_SMS_ENDPOINT == "dypnsapi.aliyuncs.com"
    assert get_settings().ALIYUN_SMS_ENDPOINT == "dypnsapi.aliyuncs.com"


class _FakeClientException(Exception):
    """模拟 SDK 的 ClientException:自带 code/message/request_id(真机排查的关键信息)。"""

    def __init__(self) -> None:
        super().__init__("Specified api is not found")
        self.code = 404
        self.message = "Specified api is not found, please check your url"
        self.request_id = "req-fake-0001"


def test_pnvs_sdk_exception_logs_code_and_message(monkeypatch, caplog):
    """SDK 异常必须落 code/message/request_id(旧实现只记类名,导致排查困难);用户侧仍是 502 + 同句文案。"""
    monkeypatch.setattr(get_settings(), "ALIYUN_SMS_ACCESS_KEY_ID", "test-ak")
    monkeypatch.setattr(get_settings(), "ALIYUN_SMS_ACCESS_KEY_SECRET", "test-sk")

    class _Client:
        def __init__(self, config):
            pass

        def send_sms_verify_code(self, request):
            raise _FakeClientException()

    monkeypatch.setattr(sms_verify, "SmsVerifyClient", _Client)
    with caplog_at_warning(caplog) as logs:
        with pytest.raises(ApiException) as exc:
            sms_verify.send_verify_code("<PHONE>", "login-out-id")
    assert (exc.value.code, exc.value.status_code) == (502, 502)
    assert exc.value.message == sms_verify.SMS_UNAVAILABLE_MESSAGE == "短信服务暂不可用，请稍后重试"
    text = logs.text()
    assert "error=_FakeClientException" in text
    assert "code=404" in text
    assert "Specified api is not found" in text
    assert "request_id=req-fake-0001" in text
    assert "<PHONE>" not in text                                   # 完整手机号不入日志
    assert "test-sk" not in text and "test-ak" not in text             # 凭证不入日志


class _FakeValidateFail(Exception):
    """模拟真机输错码:`CheckSmsVerifyCode` 以 ClientException(code=isv.ValidateFail) 抛出(实测)。"""

    def __init__(self) -> None:
        super().__init__("code: 400, 验证失败")
        self.code = "isv.ValidateFail"
        self.message = "code: 400, 验证失败 request id: fake-req-2"
        self.request_id = "fake-req-2"


def test_check_business_level_failure_is_not_passed_not_502(monkeypatch, caplog):
    """`isv.ValidateFail`(输错码)必须映射为「未通过」return False,**不得**当服务故障抛 502。"""
    monkeypatch.setattr(get_settings(), "ALIYUN_SMS_ACCESS_KEY_ID", "test-ak")
    monkeypatch.setattr(get_settings(), "ALIYUN_SMS_ACCESS_KEY_SECRET", "test-sk")

    class _Client:
        def __init__(self, config):
            pass

        def check_sms_verify_code(self, request):
            raise _FakeValidateFail()

    monkeypatch.setattr(sms_verify, "SmsVerifyClient", _Client)
    with caplog_at_info(caplog) as logs:
        assert sms_verify.check_verify_code("<PHONE>", "999999", "login-out-id") is False
    assert "校验未通过(业务级)" in logs.text() and "isv.ValidateFail" in logs.text()
    assert "999999" not in logs.text()                                  # 验证码不入日志


def test_login_wrong_code_via_sdk_returns_400_and_counts_attempt(client, session, monkeypatch):
    """端到端(打桩 SDK 而非适配层):真机式输错码 → **400「验证码不正确或已过期」**且 attempts+1(C8 生效)。"""
    phone = _phone()
    _seed_phone_merchant(session, phone)
    row_id = _seed_row(session, phone, out_id="login-sdk-fail")
    monkeypatch.setattr(get_settings(), "ALIYUN_SMS_ACCESS_KEY_ID", "test-ak")
    monkeypatch.setattr(get_settings(), "ALIYUN_SMS_ACCESS_KEY_SECRET", "test-sk")

    class _Client:
        def __init__(self, config):
            pass

        def check_sms_verify_code(self, request):
            raise _FakeValidateFail()

    monkeypatch.setattr(sms_verify, "SmsVerifyClient", _Client)
    try:
        resp = client.post(LOGIN_PATH, json={"phone": phone, "code": "999999"})
        assert resp.status_code == 400, resp.text
        assert resp.json()["message"] == phone_auth.CODE_INVALID_MESSAGE
        attempts = session.execute(text("SELECT attempts FROM merchant_login_code WHERE id = :i"),
                                   {"i": row_id}).scalar()
        assert int(attempts) == 1
    finally:
        _cleanup_phone(session, phone)



def test_pnvs_check_exception_also_logs_code_and_message(monkeypatch, caplog):
    """校验侧异常同样带诊断信息(与下发侧同一范式),且仍 fail-closed 抛 502。"""
    monkeypatch.setattr(get_settings(), "ALIYUN_SMS_ACCESS_KEY_ID", "test-ak")
    monkeypatch.setattr(get_settings(), "ALIYUN_SMS_ACCESS_KEY_SECRET", "test-sk")

    class _Client:
        def __init__(self, config):
            pass

        def check_sms_verify_code(self, request):
            raise _FakeClientException()

    monkeypatch.setattr(sms_verify, "SmsVerifyClient", _Client)
    with caplog_at_warning(caplog) as logs:
        with pytest.raises(ApiException) as exc:
            sms_verify.check_verify_code("<PHONE>", "123456", "login-out-id")
    assert (exc.value.code, exc.value.status_code) == (502, 502)
    text = logs.text()
    assert "code=404" in text and "request_id=req-fake-0001" in text
    assert "123456" not in text                                        # 验证码不入日志



# ---- 5) 内部通知:失败不阻塞 / 幂等 / 脱敏 ----


# ---- 7) 内部通知失败可观测性 + INFO 日志配置(#PB-23-R5) ----


class _FakeLarkAuthError(Exception):
    """模拟 lark SDK 的 ObtainAccessTokenException:自带 code/msg(真机实测 10014 app secret invalid)。"""

    def __init__(self, msg: str = "app secret invalid") -> None:
        super().__init__(msg)
        self.code = 10014
        self.msg = msg


def test_internal_notify_error_message_keeps_feishu_code_and_msg(session, monkeypatch):
    """失败原因必须保留 `exception:<类名>` 兜底**并**带上飞书 code/msg(否则真机排障只剩类名)。"""
    phone = _phone()
    merchant_id = _seed_phone_merchant(session, phone)

    def _raise(*args, **kwargs):
        raise _FakeLarkAuthError()

    monkeypatch.setattr(internal_notify, "_send_text", _raise)
    try:
        internal_notify.notify_merchant_registered(merchant_id, phone)
        session.commit()
        row = session.execute(text("SELECT id, status, error_message FROM internal_notify_log WHERE merchant_id = :m"),
                              {"m": merchant_id}).mappings().first()
        assert row["status"] == "failed"
        message = row["error_message"]
        assert message.startswith("exception:_FakeLarkAuthError")
        assert "code=10014" in message and "app secret invalid" in message
        assert len(message) <= internal_notify.ERROR_MESSAGE_MAX_CHARS == 255
        assert phone not in message
    finally:
        _cleanup_phone(session, phone)


def test_error_message_helpers_truncate_to_column_width():
    """两层截断可证:上游 msg 段 ≤160;整行 ≤ 列宽 255(直接单测助手,稳定且不依赖 DB)。"""
    assert internal_notify.ERROR_MESSAGE_MAX_CHARS == 255
    assert len(internal_notify._truncate_error_message("y" * 500)) == 255
    detail = internal_notify._upstream_failure_detail(_FakeLarkAuthError("z" * 500))
    assert detail.startswith("exception:_FakeLarkAuthError code=10014")
    assert len(detail) <= 255 and len(detail) < 500
    assert internal_notify._upstream_failure_detail(RuntimeError("boom")) == "exception:RuntimeError"


def test_api_logger_is_idempotently_configured_for_info():
    """`api` 命名空间有一条幂等 StreamHandler(INFO 可落盘);重复调用只挂一次;不动 uvicorn。"""
    import app.main as main_module

    api_logger = logging.getLogger("api")
    marked = [h for h in api_logger.handlers if getattr(h, main_module.LOG_HANDLER_MARKER, False)]
    assert len(marked) == 1, api_logger.handlers
    assert isinstance(marked[0], logging.StreamHandler)
    assert api_logger.isEnabledFor(logging.INFO)
    main_module._configure_logging()
    main_module._configure_logging()
    marked_again = [h for h in api_logger.handlers if getattr(h, main_module.LOG_HANDLER_MARKER, False)]
    assert len(marked_again) == 1                      # 幂等:不重复挂
    assert logging.getLogger("uvicorn").level != logging.DEBUG   # 不动 uvicorn logger

def test_notify_failure_does_not_block_201(client, session, monkeypatch, caplog):
    phone = _phone()
    _seed_row(session, phone, out_id="login-notify-fail")
    _stub_check(monkeypatch, passed=True)

    def boom(target_type, target, text):
        raise RuntimeError("im channel down")

    monkeypatch.setattr(internal_notify, "_send_text", boom)
    try:
        with caplog.at_level(logging.WARNING, logger="api"):
            resp = client.post(LOGIN_PATH, json={"phone": phone, "code": "888888"})
        assert resp.status_code == 201, resp.text
        session.commit()                                          # 后台任务用独立会话写入
        rows = session.execute(text("SELECT status FROM internal_notify_log WHERE merchant_id = :m"),
                               {"m": resp.json()["data"]["merchant"]["merchant_id"]}).all()
        assert [r[0] for r in rows] == ["failed"]
        assert any("内部通知" in r.getMessage() for r in caplog.records)
    finally:
        _cleanup_phone(session, phone)


def test_notify_sent_once_and_masked(client, session, monkeypatch):
    phone = _phone()
    sent = []
    monkeypatch.setattr(internal_notify, "_send_text",
                        lambda target_type, target, text: (sent.append(text), (True, None))[1])
    _seed_row(session, phone, out_id="login-notify-1")
    _stub_check(monkeypatch, passed=True)
    try:
        first = client.post(LOGIN_PATH, json={"phone": phone, "code": "111111"})
        assert first.status_code == 201, first.text
        merchant_id = first.json()["data"]["merchant"]["merchant_id"]
        _seed_row(session, phone, out_id="login-notify-2")
        second = client.post(LOGIN_PATH, json={"phone": phone, "code": "222222"})
        assert second.status_code == 201 and second.json()["data"]["is_new_merchant"] is False
        session.commit()
        rows = session.execute(text("SELECT status FROM internal_notify_log WHERE merchant_id = :m"),
                               {"m": merchant_id}).all()
        assert [r[0] for r in rows] == ["sent"]                   # 同一商家只通知一次
        assert len(sent) == 1
        assert phone not in sent[0] and mask_phone(phone) in sent[0] and merchant_id in sent[0]
    finally:
        _cleanup_phone(session, phone)


def test_rows_and_logs_have_no_code_material_and_phone_masked(client, session, monkeypatch, caplog):
    """表结构=8 列(无验证码材料);日志不含完整手机号、不含人机校验串。"""
    phone = _phone()
    _stub_send(monkeypatch)
    _stub_captcha_ok(monkeypatch)
    try:
        with caplog.at_level(logging.INFO, logger="api"):
            resp = client.post(SEND_PATH, json={"phone": phone, "captcha_verify_param": CAPTCHA_PARAM})
        assert resp.status_code == 200
        columns = {r[0] for r in session.execute(text(
            "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() "
            "AND TABLE_NAME='merchant_login_code'")).all()}
        assert columns == {"id", "phone", "biz_id", "out_id", "ip", "attempts", "used_at", "created_at"}
        logs = "\n".join(r.getMessage() for r in caplog.records)
        assert phone not in logs and CAPTCHA_PARAM not in logs
        assert mask_phone(phone) in logs
    finally:
        _cleanup_phone(session, phone)


