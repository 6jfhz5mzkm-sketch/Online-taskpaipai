"""AI 上游**空响应**自动重试 1 次(#PB-35)。

背景:上游大模型偶发返回空 content,原实现直接判 `LLM_EMPTY_RESPONSE` → 502「AI 分析结果异常，请稍后重试」
(#PB-33 已 A/B 证其为上游瞬时抖动,改造提示词前同样发生)。修复:**只对空响应重试 1 次**,
且**只能用剩余超时预算**——硬上界:总调用 ≤ 2、总耗时 ≤ 入口传入的 `timeout_ms`;
其余错误(`LLM_HTTP_429` / `LLM_TIMEOUT` / `LLM_NETWORK_ERROR` / `LLM_HTTP_5XX` / `LLM_PARSE_FAILED`)一律不重试。

隔离:`monkeypatch` `ai.httpx.post`(不触网)+ 假时钟 `ai._monotonic`(精确控制每次调用的耗时,不 sleep);
仅最后一条端到端用例需要临时商家,其 `ai_analysis_log` 行**先记 id 再按 id 删除**(conftest 不覆盖该表)。
"""
import httpx
import pytest
from sqlalchemy import bindparam, text

from app.core.exceptions import ApiException
from app.services import ai
from app.services.ai_config import EntryConfig

from tests.conftest import cleanup_temp_merchant, make_temp_merchant

EMPTY_COPY = "AI 分析结果异常，请稍后重试"      # 空响应的用户可见文案(契约不得改)


def _cfg(timeout_ms: int = 60000) -> EntryConfig:
    return EntryConfig(entry="analysis", api_key="test-key", base_url="http://127.0.0.1:9/v1",
                       model="test-model", timeout_ms=timeout_ms, max_tokens=16, daily_limit=0,
                       sources={}, key_status="ok", key_fingerprint=None)


class _Resp:
    def __init__(self, content, status_code: int = 200) -> None:
        self.status_code = status_code
        self.is_success = 200 <= status_code < 300
        self._content = content

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


class _Clock:
    """假单调时钟:由被测代码/桩推进,精确表达「这一次上游调用花了多久」。"""

    def __init__(self, start: float = 100000.0) -> None:
        self.now = float(start)

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _install_post(monkeypatch, clock: _Clock, *, contents, costs_ms=None, cost_ms: float = 100.0, raises=None):
    """桩化上游:按顺序返回 contents(耗尽后重复最后一个);第 i 次调用消耗 `costs_ms[i]` 秒预算。

    `costs_ms` 传列表可精确表达「第 1 次花了 57s、第 2 次花了 3s」这类真实耗时形态。
    """
    calls = []
    costs = list(costs_ms) if costs_ms is not None else []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"timeout": timeout})
        index0 = len(calls) - 1
        cost = costs[min(index0, len(costs) - 1)] if costs else cost_ms
        clock.advance(cost / 1000.0)
        if raises is not None:
            raise raises
        index = min(len(calls) - 1, len(contents) - 1)
        return _Resp(contents[index])

    monkeypatch.setattr(ai.httpx, "post", fake_post)
    # raising=False:修复前 ai 还没有这个时钟间接层,补丁前跑本用例仍应表现为「行为红」而非 AttributeError
    monkeypatch.setattr(ai, "_monotonic", clock, raising=False)
    return calls


# ---- 1) 三次调用形态:1 次成功 / 2 次成功(重试) / 2 次皆空后失败 ----


def test_empty_then_ok_retries_exactly_once_and_succeeds(monkeypatch, caplog):
    """第 1 次空、第 2 次正常 → **恰好 2 次**调用且最终成功。"""
    clock = _Clock()
    calls = _install_post(monkeypatch, clock, contents=["", "好的标题"])
    with caplog.at_level("WARNING", logger="api"):
        result = ai._post_chat(_cfg(), "system", "user", 16, timeout_ms=60000)
    assert result == "好的标题"
    assert len(calls) == 2, calls
    logs = "\n".join(r.getMessage() for r in caplog.records)
    assert "LLM_EMPTY_RESPONSE" in logs                      # 可诊断:原因码
    assert "好的标题" not in logs                             # 不记录上游返回原文


def test_two_empty_responses_call_twice_then_raise(monkeypatch):
    """两次都空 → **恰好 2 次**调用(上界可证)后按原错误码抛错,文案不变。"""
    clock = _Clock()
    calls = _install_post(monkeypatch, clock, contents=["", ""])
    with pytest.raises(RuntimeError) as exc:
        ai._post_chat(_cfg(), "system", "user", 16, timeout_ms=60000)
    assert str(exc.value) == "LLM_EMPTY_RESPONSE"
    assert len(calls) == 2, calls
    with pytest.raises(ApiException) as api_exc:
        ai._raise_from_code("LLM_EMPTY_RESPONSE")
    assert (api_exc.value.code, api_exc.value.status_code) == (502, 502)
    assert api_exc.value.message == EMPTY_COPY


def test_non_empty_content_calls_upstream_once(monkeypatch):
    """正常非空 → **只调用 1 次**(不得引入多余调用/多余等待)。"""
    clock = _Clock()
    calls = _install_post(monkeypatch, clock, contents=["{}"])
    assert ai._post_chat(_cfg(), "system", "user", 16, timeout_ms=60000) == "{}"
    assert len(calls) == 1, calls


# ---- 2) 总超时预算:重试只能用剩余预算,剩余不足则不重试 ----


def test_retry_uses_remaining_budget_only(monkeypatch):
    """第 1 次消耗 57s(空),重试只拿到剩余 3s;总耗时不得超过入口 timeout_ms。"""
    clock = _Clock()
    calls = _install_post(monkeypatch, clock, contents=["", "ok"], costs_ms=[57000.0, 3000.0])
    started = clock()
    assert ai._post_chat(_cfg(timeout_ms=60000), "system", "user", 16, timeout_ms=60000) == "ok"
    assert [c["timeout"] for c in calls] == [60.0, 3.0], calls          # 重试只拿到剩余 3s
    assert clock() - started <= 60.0                                     # 总耗时不超过总预算
    assert calls[1]["timeout"] * 1000 <= 60000 - 57000


def test_retry_is_skipped_when_remaining_budget_too_small(monkeypatch):
    """第 1 次几乎耗尽预算 → 剩余不足**不重试**,直接按原错误码抛错(不得让用户等 2×timeout)。"""
    clock = _Clock()
    # 第 1 次耗时 = 总预算 - 下限 + 1ms ⇒ 剩余 999ms < 下限 1000ms ⇒ 不重试
    calls = _install_post(monkeypatch, clock, contents=["", "ok"],
                          cost_ms=60000.0 - ai._EMPTY_RETRY_MIN_BUDGET_MS + 1.0)
    with pytest.raises(RuntimeError) as exc:
        ai._post_chat(_cfg(timeout_ms=60000), "system", "user", 16, timeout_ms=60000)
    assert str(exc.value) == "LLM_EMPTY_RESPONSE"
    assert len(calls) == 1, calls
    assert calls[0]["timeout"] == 60.0


def test_total_elapsed_never_exceeds_budget(monkeypatch):
    """两次调用(含重试)的累计耗时不得超过入口 timeout_ms。"""
    clock = _Clock()
    calls = _install_post(monkeypatch, clock, contents=["", "ok"], costs_ms=[20000.0, 5000.0])
    started = clock()
    assert ai._post_chat(_cfg(timeout_ms=60000), "system", "user", 16, timeout_ms=60000) == "ok"
    assert clock() - started <= 60.0
    assert len(calls) == 2


# ---- 3) 其余错误码一律不重试 ----


@pytest.mark.parametrize("exc,expected", [
    (httpx.ReadTimeout("read timed out"), "LLM_TIMEOUT"),
    (httpx.ConnectTimeout("connect timed out"), "LLM_NETWORK_ERROR"),
    (httpx.ConnectError("connection refused"), "LLM_NETWORK_ERROR"),
])
def test_transport_errors_are_not_retried(monkeypatch, exc, expected):
    clock = _Clock()
    calls = _install_post(monkeypatch, clock, contents=[""], raises=exc)
    with pytest.raises(RuntimeError) as raised:
        ai._post_chat(_cfg(), "system", "user", 16, timeout_ms=60000)
    assert str(raised.value) == expected
    assert len(calls) == 1, calls


@pytest.mark.parametrize("status,expected", [(429, "LLM_HTTP_429"), (503, "LLM_HTTP_5XX"), (400, "LLM_HTTP_400")])
def test_http_errors_are_not_retried(monkeypatch, status, expected):
    clock = _Clock()
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(timeout)
        clock.advance(0.1)
        return _Resp("", status_code=status)

    monkeypatch.setattr(ai.httpx, "post", fake_post)
    monkeypatch.setattr(ai, "_monotonic", clock, raising=False)
    with pytest.raises(RuntimeError) as raised:
        ai._post_chat(_cfg(), "system", "user", 16, timeout_ms=60000)
    assert str(raised.value) == expected
    assert len(calls) == 1, calls


def test_parse_failure_is_not_retried_end_to_end(monkeypatch, session):
    """有内容但不是 JSON(`LLM_PARSE_FAILED`)→ 上游**只被调用 1 次**,仍 502 + 同一句文案。"""
    merchant_id = make_temp_merchant(session)
    log_ids = []
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(timeout)
        return _Resp("这不是 JSON，只是一段说明文字")

    monkeypatch.setattr(ai.httpx, "post", fake_post)
    try:
        with pytest.raises(ApiException) as exc:
            ai.optimize_title(session, merchant_id,
                              {"mode": "generate", "brand": "测试品牌", "category": "二手手机"})
        assert (exc.value.code, exc.value.status_code) == (502, 502)
        assert exc.value.message == EMPTY_COPY
        assert len(calls) == 1, calls
        log_ids = [int(r[0]) for r in session.execute(
            text("SELECT id FROM ai_analysis_log WHERE merchant_id = :m ORDER BY id"), {"m": merchant_id}).all()]
    finally:
        if log_ids:
            session.execute(text("DELETE FROM ai_analysis_log WHERE id IN :ids").bindparams(
                bindparam("ids", expanding=True)), {"ids": log_ids})
            session.commit()
        cleanup_temp_merchant(session, merchant_id)
    assert log_ids, "未记录到失败日志行(应先记 id 再按 id 删除)"
