"""飞书登录链路回归(#PB-14):app_access_token → OIDC 换 token → user_info。

背景(2026-09-14 生产实测):`POST /open-apis/authen/v1/oidc/access_token` 必须携带
`Authorization: Bearer <app_access_token>`,否则飞书返回 code=20014「The app access token passed is invalid」。

纪律:本用例用 monkeypatch 打桩 httpx,**绝不真实外呼飞书**;断言中也不回显任何 secret/token/授权 code 原文。
隔离:进程内 app_access_token 缓存在每个用例前后清空;settings 用替身,不依赖真实 .env。
"""

from types import SimpleNamespace

import logging

import pytest

from app.core.exceptions import ApiException
from app.services import feishu as feishu_service

APP_TOKEN = "app-token-for-test"
USER_TOKEN = "user-token-for-test"
AUTH_CODE = "auth-code-for-test"
APP_SECRET = "test-app-secret"

APP_TOKEN_OK = {"code": 0, "msg": "ok", "app_access_token": APP_TOKEN, "expire": 7200}
OIDC_OK = {"code": 0, "msg": "success", "data": {"access_token": USER_TOKEN, "scope": "contact:user.base:readonly"}}
USER_INFO_OK = {"code": 0, "msg": "success",
                "data": {"open_id": "<OPEN_ID>", "union_id": "on_test", "name": "测试用户", "avatar_url": "https://example.com/a.png"}}


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def isolate_app_token_cache(monkeypatch):
    """settings 替身 + 进程内 app_access_token 缓存清理(仅影响测试进程)。"""
    monkeypatch.setattr(feishu_service, "settings",
                        SimpleNamespace(FEISHU_APP_ID="cli_test_app", FEISHU_APP_SECRET=APP_SECRET))
    feishu_service._app_access_token_cache.clear()
    yield
    feishu_service._app_access_token_cache.clear()


def _install_httpx(monkeypatch, *, app_token_payload, oidc_payload, user_payload):
    """打桩 httpx.post/get,返回各端点调用记录(用于断言请求头/次数,不回显敏感原文)。"""
    calls = {"app": [], "oidc": [], "user": []}

    def fake_post(url, **kwargs):
        if url == feishu_service.APP_ACCESS_TOKEN_URL:
            calls["app"].append({"headers": kwargs.get("headers"), "json": kwargs.get("json"),
                                 "timeout": kwargs.get("timeout")})
            return _Resp(app_token_payload)
        calls["oidc"].append({"url": url, "headers": kwargs.get("headers"), "json": kwargs.get("json"),
                              "timeout": kwargs.get("timeout")})
        return _Resp(oidc_payload)

    def fake_get(url, **kwargs):
        calls["user"].append({"url": url, "headers": kwargs.get("headers"), "timeout": kwargs.get("timeout")})
        return _Resp(user_payload)

    monkeypatch.setattr(feishu_service.httpx, "post", fake_post)
    monkeypatch.setattr(feishu_service.httpx, "get", fake_get)
    return calls


def test_login_chain_success_sends_app_bearer(monkeypatch):
    """正常链路:先取 app_access_token,再用它作为 Bearer 头换 user token,最后取 user_info。"""
    calls = _install_httpx(monkeypatch, app_token_payload=APP_TOKEN_OK, oidc_payload=OIDC_OK,
                           user_payload=USER_INFO_OK)

    result = feishu_service.login_feishu(None, AUTH_CODE)

    assert result == {"open_id": "<OPEN_ID>", "union_id": "on_test", "name": "测试用户",
                      "avatar": "https://example.com/a.png"}
    assert len(calls["app"]) == 1
    assert calls["app"][0]["json"]["app_id"] == "cli_test_app"
    assert set(calls["app"][0]["json"]) == {"app_id", "app_secret"}
    assert calls["app"][0]["timeout"] == feishu_service.HTTP_TIMEOUT_SECONDS

    assert len(calls["oidc"]) == 1
    oidc = calls["oidc"][0]
    assert oidc["url"] == feishu_service.OIDC_ACCESS_TOKEN_URL
    # 关键断言:必须带 app_access_token 的 Bearer 头(缺它就是 code=20014 的根因)
    assert oidc["headers"]["Authorization"] == "Bearer " + APP_TOKEN
    assert oidc["json"]["grant_type"] == "authorization_code"
    assert oidc["json"]["code"] == AUTH_CODE
    assert oidc["json"]["client_id"] == "cli_test_app"

    assert len(calls["user"]) == 1
    assert calls["user"][0]["headers"]["Authorization"] == "Bearer " + USER_TOKEN


def test_app_access_token_failure_raises_502_without_further_calls(monkeypatch):
    """app_access_token 获取失败 -> 结构化 502,且不再调用 OIDC(不降级 mock)。"""
    calls = _install_httpx(monkeypatch, app_token_payload={"code": 10003, "msg": "invalid app_secret"},
                           oidc_payload=OIDC_OK, user_payload=USER_INFO_OK)

    with pytest.raises(ApiException) as excinfo:
        feishu_service.login_feishu(None, AUTH_CODE)

    assert excinfo.value.code == 502 and excinfo.value.status_code == 502
    assert "飞书应用凭证" in excinfo.value.message
    assert APP_SECRET not in excinfo.value.message
    assert calls["oidc"] == [] and calls["user"] == []
    # 失败不写缓存:清掉缓存里的空值后仍会重新尝试(此处断言缓存未残留可用值)
    assert feishu_service._app_access_token_cache._token == ""


def test_app_access_token_failure_does_not_poison_cache(monkeypatch):
    """一次失败后,下一次登录仍会重新换取并成功(失败结果不入缓存)。"""
    calls = _install_httpx(monkeypatch, app_token_payload={"code": 10003, "msg": "boom"},
                           oidc_payload=OIDC_OK, user_payload=USER_INFO_OK)
    with pytest.raises(ApiException):
        feishu_service.login_feishu(None, AUTH_CODE)

    calls = _install_httpx(monkeypatch, app_token_payload=APP_TOKEN_OK, oidc_payload=OIDC_OK,
                           user_payload=USER_INFO_OK)
    result = feishu_service.login_feishu(None, AUTH_CODE)
    assert result["open_id"] == "<OPEN_ID>"
    assert len(calls["app"]) == 1


def test_oidc_20014_raises_401_with_feishu_code_and_no_mock_fallback(monkeypatch):
    """OIDC 返回 code=20014 -> 401 且文案带飞书错误码;不继续取 user_info、不降级 mock。"""
    calls = _install_httpx(
        monkeypatch, app_token_payload=APP_TOKEN_OK,
        oidc_payload={"code": 20014, "msg": "The app access token passed is invalid"},
        user_payload=USER_INFO_OK)

    with pytest.raises(ApiException) as excinfo:
        feishu_service.login_feishu(None, AUTH_CODE)

    assert excinfo.value.code == 401 and excinfo.value.status_code == 401
    assert "20014" in excinfo.value.message
    assert APP_SECRET not in excinfo.value.message and APP_TOKEN not in excinfo.value.message
    assert calls["user"] == []


def test_user_info_without_open_id_raises(monkeypatch):
    """user_info 未返回 open_id -> 结构化 401。"""
    _install_httpx(monkeypatch, app_token_payload=APP_TOKEN_OK, oidc_payload=OIDC_OK,
                   user_payload={"code": 0, "msg": "success", "data": {"name": "无 open_id"}})

    with pytest.raises(ApiException) as excinfo:
        feishu_service.login_feishu(None, AUTH_CODE)

    assert excinfo.value.code == 401
    assert "open_id" in excinfo.value.message


def test_user_info_failure_includes_feishu_code(monkeypatch):
    """user_info 业务失败 -> 401 且文案带飞书错误码。"""
    _install_httpx(monkeypatch, app_token_payload=APP_TOKEN_OK, oidc_payload=OIDC_OK,
                   user_payload={"code": 99991663, "msg": "invalid user_access_token"})

    with pytest.raises(ApiException) as excinfo:
        feishu_service.login_feishu(None, AUTH_CODE)

    assert excinfo.value.code == 401
    assert "99991663" in excinfo.value.message


def test_app_access_token_is_cached_with_refresh_margin(monkeypatch):
    """缓存命中不重复换取;剩余有效期进入余量(300s)后重新换取。"""
    fake_now = {"t": 1000.0}
    monkeypatch.setattr(feishu_service, "_monotonic", lambda: fake_now["t"])
    calls = _install_httpx(monkeypatch, app_token_payload=APP_TOKEN_OK, oidc_payload=OIDC_OK,
                           user_payload=USER_INFO_OK)

    feishu_service.login_feishu(None, AUTH_CODE)
    assert len(calls["app"]) == 1  # 首次换取

    # expires_at = 1000 + 7200 = 8200;余量 300 -> [8200-300=7900) 之前视为有效
    fake_now["t"] = 7800.0
    feishu_service.login_feishu(None, AUTH_CODE)
    assert len(calls["app"]) == 1  # 命中缓存,不再换取

    fake_now["t"] = 7950.0  # 已进入刷新余量
    feishu_service.login_feishu(None, AUTH_CODE)
    assert len(calls["app"]) == 2  # 重新换取

    assert len(calls["oidc"]) == 3  # 每次登录都换 user token


# ---- 飞书错误码 -> 用户可读文案(#PB-16) ----


def test_oidc_20003_returns_readable_message_without_bare_code(monkeypatch):
    """20003(授权码无效/已过期)-> 401 且文案可读、不含裸错误码。"""
    _install_httpx(monkeypatch, app_token_payload=APP_TOKEN_OK,
                   oidc_payload={"code": 20003, "msg": "invalid authorization code"},
                   user_payload=USER_INFO_OK)

    with pytest.raises(ApiException) as excinfo:
        feishu_service.login_feishu(None, AUTH_CODE)

    assert excinfo.value.code == 401 and excinfo.value.status_code == 401
    assert excinfo.value.message == "登录链接已失效，请重新点击飞书登录"
    assert "20003" not in excinfo.value.message


def test_oidc_unknown_code_keeps_code_for_diagnosis(monkeypatch):
    """未知错误码保持现状:附码(排障需要);用户文案仍为友好前缀。"""
    _install_httpx(monkeypatch, app_token_payload=APP_TOKEN_OK,
                   oidc_payload={"code": 12345, "msg": "some other failure"},
                   user_payload=USER_INFO_OK)

    with pytest.raises(ApiException) as excinfo:
        feishu_service.login_feishu(None, AUTH_CODE)

    assert excinfo.value.code == 401
    assert excinfo.value.message.startswith("飞书授权失败，请重新登录")
    assert "12345" in excinfo.value.message


def test_oidc_missing_code_uses_friendly_message(monkeypatch):
    """响应里没有 code 时用友好文案,不得把字面 None 展示给用户。"""
    _install_httpx(monkeypatch, app_token_payload=APP_TOKEN_OK,
                   oidc_payload={"msg": "unexpected payload"}, user_payload=USER_INFO_OK)

    with pytest.raises(ApiException) as excinfo:
        feishu_service.login_feishu(None, AUTH_CODE)

    assert excinfo.value.message == "飞书授权失败，请重新登录"
    assert "None" not in excinfo.value.message


@pytest.mark.parametrize("code,expected", [
    (20003, "登录链接已失效，请重新点击飞书登录"),
    (20014, "飞书授权失败，请重新登录（飞书错误码 20014）"),
    (12345, "飞书授权失败，请重新登录（飞书错误码 12345）"),
    (None, "飞书授权失败，请重新登录"),
])
def test_oidc_failure_message_mapping_is_single_source(code, expected):
    """文案映射为服务层纯函数(单一真源):已知码可读、未知码附码、无码友好。"""
    assert feishu_service._oidc_failure_message(code) == expected
    assert 20003 in feishu_service.OIDC_ERROR_MESSAGES
    assert 20003 in feishu_service.AUTH_CODE_ERROR_CODES


def test_oidc_20003_logs_code_msg_and_auth_code_hint(monkeypatch, caplog):
    """20003 日志:记飞书 code/msg 并附「授权码一次性」提示;绝不记录授权 code 原文。"""
    _install_httpx(monkeypatch, app_token_payload=APP_TOKEN_OK,
                   oidc_payload={"code": 20003, "msg": "invalid authorization code"},
                   user_payload=USER_INFO_OK)

    with caplog.at_level(logging.WARNING, logger="api"):
        with pytest.raises(ApiException):
            feishu_service.login_feishu(None, AUTH_CODE)

    logs = "\n".join(record.getMessage() for record in caplog.records)
    assert "code=20003" in logs
    assert "invalid authorization code" in logs
    assert "授权码一次性,通常为已使用或已过期" in logs
    assert AUTH_CODE not in logs          # 凭据纪律:授权 code 原文不入日志
    assert APP_SECRET not in logs


def test_oidc_failure_without_msg_still_logs_explicit_none(monkeypatch, caplog):
    """飞书未回 msg 时日志仍要明确记录 msg=None(不许静默丢字段)。"""
    _install_httpx(monkeypatch, app_token_payload=APP_TOKEN_OK,
                   oidc_payload={"code": 20014}, user_payload=USER_INFO_OK)

    with caplog.at_level(logging.WARNING, logger="api"):
        with pytest.raises(ApiException):
            feishu_service.login_feishu(None, AUTH_CODE)

    logs = "\n".join(record.getMessage() for record in caplog.records)
    assert "code=20014" in logs
    assert "msg=None" in logs

# ---- 登录页提示白话化(#PB-31):用户看白话,运维看结构化日志 ----


@pytest.fixture()
def real_login_mode(monkeypatch):
    """把进程内登录模式切到 real(仅本用例,结束后自动还原),以命中飞书凭证 fail-fast 分支。"""
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "LOGIN_MODE", "real")


def _error_logs(caplog) -> str:
    return "\n".join(record.getMessage() for record in caplog.records)


def test_login_copy_missing_credentials_is_plain_chinese(client, real_login_mode, monkeypatch, caplog):
    """凭证缺失:原始响应给商家看的是白话(不含环境变量名/运维语);判定依据在日志里。"""
    monkeypatch.setattr(feishu_service.settings, "FEISHU_APP_ID", "")
    monkeypatch.setattr(feishu_service.settings, "FEISHU_APP_SECRET", "")
    with caplog.at_level(logging.ERROR, logger="api"):
        resp = client.post("/api/auth/feishu/callback", json={"code": AUTH_CODE})
    assert resp.status_code == 502, resp.text
    body = resp.json()
    assert body == {"code": 502, "message": feishu_service.FEISHU_LOGIN_UNAVAILABLE_MESSAGE, "data": None}
    for leaked in ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "未配置", "占位"):
        assert leaked not in body["message"]
    logs = _error_logs(caplog)
    assert "飞书登录凭证不合规" in logs
    assert "app_id=missing" in logs and "app_secret=missing" in logs
    assert "required_env=[FEISHU_APP_ID, FEISHU_APP_SECRET]" in logs


def test_login_copy_placeholder_secret_is_plain_chinese(client, real_login_mode, monkeypatch, caplog):
    """占位 secret 同样只暴露白话;日志区分 missing/placeholder 但不回显占位值原文与授权码。"""
    monkeypatch.setattr(feishu_service.settings, "FEISHU_APP_ID", "cli_test_app")
    monkeypatch.setattr(feishu_service.settings, "FEISHU_APP_SECRET", "your_feishu_app_secret")
    with caplog.at_level(logging.ERROR, logger="api"):
        resp = client.post("/api/auth/feishu/callback", json={"code": AUTH_CODE})
    assert resp.status_code == 502, resp.text
    assert resp.json()["message"] == feishu_service.FEISHU_LOGIN_UNAVAILABLE_MESSAGE
    logs = _error_logs(caplog)
    assert "app_id=set" in logs and "app_secret=placeholder" in logs
    assert "your_feishu_app_secret" not in logs      # 凭据纪律:占位值原文不入日志
    assert AUTH_CODE not in logs


def test_login_unavailable_copy_is_locked_and_plain():
    """文案锁:改这句就是改用户可见口径,必须显式改本断言(不得出现技术细节)。"""
    assert feishu_service.FEISHU_LOGIN_UNAVAILABLE_MESSAGE == "登录服务暂不可用，请稍后重试或联系管理员"
    for leaked in ("FEISHU", "未配置", "占位", "env", "APP_"):
        assert leaked not in feishu_service.FEISHU_LOGIN_UNAVAILABLE_MESSAGE


def test_secret_state_reuses_config_placeholder_list():
    """占位清单单一真源:与 app/core/config.py 的启动校验同口径,不就地内联。"""
    from app.core.config import FEISHU_SECRET_PLACEHOLDERS
    assert feishu_service._feishu_secret_state("") == "missing"
    assert feishu_service._feishu_secret_state("   ") == "missing"
    assert feishu_service._feishu_secret_state(None) == "missing"
    for placeholder in FEISHU_SECRET_PLACEHOLDERS - {""}:
        assert feishu_service._feishu_secret_state(placeholder) == "placeholder"
    assert feishu_service._feishu_secret_state("real-secret") == "set"

