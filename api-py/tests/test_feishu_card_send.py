"""飞书卡片发送回归(#PB-17):lark-oapi 调用形态 + 降级语义 + 唯一发送实现。

实测口径(lark-oapi 1.7.3,本机 uv 环境核对):
  CreateMessageRequestBody.builder().receive_id(...).msg_type("interactive").content(card_json).build()
  CreateMessageRequest.builder().receive_id_type("open_id").request_body(body).build()
  client.im.**v1**.message.create(request)
旧实现 `client.im.message.create(...)` 在 SDK 上不存在('ImService' object has no attribute 'message'),
导致欢迎卡片/阶段完成/任务提醒全部发送失败(生产实测 2026-09-14)。

纪律:全程打桩,零真实外呼;不使用真实 open_id/secret/token(一律占位符)。
"""

import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import feishu as feishu_service

OPEN_ID_PLACEHOLDER = "ou_placeholder_value"
CARD_TEXT = "卡片正文占位符"


class _FakeResponse:
    def __init__(self, code=0, msg="ok"):
        self.code = code
        self.msg = msg

    def success(self):
        return self.code == 0


class _FakeMessageService:
    """模拟真实的 im.v1.message(只有 create)。"""

    def __init__(self, response=None, exc=None):
        self.calls = []
        self._response = response
        self._exc = exc

    def create(self, request, option=None):
        self.calls.append(request)
        if self._exc is not None:
            raise self._exc
        return self._response or _FakeResponse()


class _FakeClient:
    """只暴露真实 SDK 存在的路径:client.im.v1.message(故意不提供 client.im.message)。"""

    def __init__(self, message_service):
        self.im = SimpleNamespace(v1=SimpleNamespace(message=message_service))


def _install_client(monkeypatch, message_service):
    monkeypatch.setattr(feishu_service, "_lark_client", lambda: _FakeClient(message_service))


def test_send_card_success_builds_create_message_request(monkeypatch):
    """① 正常发送 -> True,且请求体字段正确(receive_id/msg_type/content 为合法 JSON 字符串)。"""
    service = _FakeMessageService(_FakeResponse(code=0))
    _install_client(monkeypatch, service)

    assert feishu_service._send_card(OPEN_ID_PLACEHOLDER, CARD_TEXT) is True
    assert len(service.calls) == 1

    request = service.calls[0]
    assert type(request).__name__ == "CreateMessageRequest"
    assert request.receive_id_type == "open_id"

    body = request.request_body
    assert body.receive_id == OPEN_ID_PLACEHOLDER
    assert body.msg_type == "interactive"
    card = json.loads(body.content)          # content 必须是 JSON 字符串
    assert card["elements"][0]["tag"] == "div"
    assert card["elements"][0]["text"]["tag"] == "lark_md"
    assert card["elements"][0]["text"]["content"] == CARD_TEXT


def test_send_card_failure_code_logs_code_and_msg(monkeypatch, caplog):
    """② SDK 返回 code != 0 -> False,且日志含飞书 code/msg(不回显 open_id)。"""
    service = _FakeMessageService(_FakeResponse(code=99991663, msg="no permission"))
    _install_client(monkeypatch, service)

    with caplog.at_level(logging.WARNING, logger="api"):
        assert feishu_service._send_card(OPEN_ID_PLACEHOLDER, CARD_TEXT) is False

    logs = "\n".join(record.getMessage() for record in caplog.records)
    assert "code=99991663" in logs
    assert "no permission" in logs
    assert OPEN_ID_PLACEHOLDER not in logs


def test_send_card_exception_is_swallowed(monkeypatch, caplog):
    """③ 调用抛异常 -> False 且不冒泡(通知属降级面),日志记录异常类型。"""
    service = _FakeMessageService(exc=RuntimeError("'ImService' object has no attribute 'message'"))
    _install_client(monkeypatch, service)

    with caplog.at_level(logging.WARNING, logger="api"):
        assert feishu_service._send_card(OPEN_ID_PLACEHOLDER, CARD_TEXT) is False

    logs = "\n".join(record.getMessage() for record in caplog.records)
    assert "RuntimeError" in logs


def test_client_creation_failure_returns_false(monkeypatch):
    """客户端创建失败(_lark_client 返回 None)-> False,不抛异常。"""
    monkeypatch.setattr(feishu_service, "_lark_client", lambda: None)
    assert feishu_service._send_card(OPEN_ID_PLACEHOLDER, CARD_TEXT) is False


def test_card_send_does_not_touch_app_access_token_cache(monkeypatch):
    """④ 卡片发送与 app_access_token 缓存互不影响(缓存不被读写)。"""
    class _SpyCache:
        def get(self):
            raise AssertionError("卡片发送不应依赖 app_access_token 缓存")

        def clear(self):
            raise AssertionError("卡片发送不应操作 app_access_token 缓存")

    monkeypatch.setattr(feishu_service, "_app_access_token_cache", _SpyCache())
    service = _FakeMessageService(_FakeResponse(code=0))
    _install_client(monkeypatch, service)
    assert feishu_service._send_card(OPEN_ID_PLACEHOLDER, CARD_TEXT) is True


def test_only_one_card_send_implementation_in_module():
    """唯一发送实现:模块内只有一处 client.im.v1.message.create,且不得再出现旧的 client.im.message。"""
    source = Path(feishu_service.__file__).read_text(encoding="utf-8")
    assert source.count("client.im.v1.message.create(") == 1   # 唯一发送调用
    assert source.count("def _send_card(") == 1                # 唯一发送实现
    assert source.count("lark.Client.builder()") == 1          # 唯一客户端构造点
    # 旧写法若被恢复:`_FakeClient` 故意不提供 im.message,① 会立刻失败(AttributeError -> False)


class _FakeMappings:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row

    def all(self):
        return [self._row] if self._row else []


class _FakeResult:
    def __init__(self, row=None):
        self._row = row

    def mappings(self):
        return _FakeMappings(self._row)


class _FakeSession:
    """send_notification / welcome_on_first 所需的最小会话替身(不连库)。"""

    def __init__(self, merchant_row=None, welcome_sent=0):
        self.merchant_row = merchant_row
        self.welcome_sent = welcome_sent
        self.committed = 0
        self.added = []

    def execute(self, stmt, params=None):
        sql = str(stmt)
        if "welcome_sent" in sql:
            return _FakeResult({"welcome_sent": self.welcome_sent})
        if "feishu_open_id" in sql:
            return _FakeResult(self.merchant_row)
        return _FakeResult(None)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.committed += 1

    def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = 1


def test_welcome_and_stage_and_notification_share_single_send_path(monkeypatch):
    """welcome_on_first / stage_complete / send_notification 共用 _send_card(无第二套发送路径)。"""
    calls = []
    monkeypatch.setattr(feishu_service, "_send_card",
                        lambda open_id, content: (calls.append((open_id, content)), True)[1])

    # 阶段完成(无 DB)
    assert feishu_service.stage_complete(OPEN_ID_PLACEHOLDER, "名字占位符", "阶段一", "阶段二") is True
    # 欢迎卡片(fake session:未发送过 -> 应调用发送)
    assert feishu_service.welcome_on_first(_FakeSession(welcome_sent=0), "m1", OPEN_ID_PLACEHOLDER, "名字占位符")["sent"] is True
    # API-10 服务层(sender 未注入 -> 用 _send_card)
    db = _FakeSession(merchant_row={"feishu_open_id": OPEN_ID_PLACEHOLDER})
    result = feishu_service.send_notification(db, "m1", "welcome", {"content": "正文占位符"})

    assert result["success"] is True and result["skipped"] is False
    assert len(calls) == 3, calls
    assert all(open_id == OPEN_ID_PLACEHOLDER for open_id, _ in calls)


def test_welcome_skips_when_already_sent(monkeypatch):
    """已发送过欢迎消息时不再调用发送(幂等语义不受本次改动影响)。"""
    calls = []
    monkeypatch.setattr(feishu_service, "_send_card", lambda open_id, content: (calls.append(open_id), True)[1])
    result = feishu_service.welcome_on_first(_FakeSession(welcome_sent=1), "m1", OPEN_ID_PLACEHOLDER, "名字占位符")
    assert result == {"sent": False, "first": False}
    assert calls == []
