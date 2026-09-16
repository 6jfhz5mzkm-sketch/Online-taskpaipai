"""AI 错误码语义回归(N5):超时 -> 504(LLM_TIMEOUT),网络/连接错误 -> 502(LLM_NETWORK_ERROR)。

背景:修复前 _post_chat 把所有异常统一映射为 LLM_NETWORK_ERROR(502),导致 _raise_from_code 里的
LLM_TIMEOUT(504)分支永不可达。NestJS 对账(只读参考):
  image-optimize.service.ts:236 AbortError -> 'LLM_TIMEOUT';:294-295 -> HttpStatus.GATEWAY_TIMEOUT(504);
  :263 UND_ERR_CONNECT_TIMEOUT 与其它连接类错误 -> 'LLM_NETWORK_ERROR'(502)。
Python 侧对应关系:httpx.ConnectTimeout(连接阶段,等价 UND_ERR_CONNECT_TIMEOUT)-> 502;
其余 httpx.TimeoutException(到达 timeout_ms 后中断,等价 AbortController abort)-> 504。
"""

import uuid

import httpx
import pytest
from sqlalchemy import text

from app.core.exceptions import ApiException
from app.services import ai
from app.services.ai_config import EntryConfig

from tests.conftest import cleanup_temp_merchant, make_temp_merchant


def _configure_ai(monkeypatch) -> None:
    monkeypatch.setattr(ai.settings, "AI_API_KEY", "test-key")
    monkeypatch.setattr(ai.settings, "AI_BASE_URL", "http://127.0.0.1:9/v1")


def _raise_on_post(monkeypatch, exc: Exception) -> None:
    def boom(*args, **kwargs):
        raise exc

    monkeypatch.setattr(ai.httpx, "post", boom)


def _cfg() -> EntryConfig:
    """直接构造解析结果(#PB-21:`_post_chat` 改由 cfg 提供 key/base_url/model);本文件只回归错误码映射。"""
    return EntryConfig(entry="analysis", api_key="test-key", base_url="http://127.0.0.1:9/v1",
                       model="test-model", timeout_ms=1000, max_tokens=16, daily_limit=0,
                       sources={}, key_status="ok", key_fingerprint=None)


def test_read_timeout_maps_to_llm_timeout(monkeypatch):
    _raise_on_post(monkeypatch, httpx.ReadTimeout("read timed out"))
    with pytest.raises(RuntimeError) as exc:
        ai._post_chat(_cfg(), "system", "user", 16, timeout_ms=1000)
    assert str(exc.value) == "LLM_TIMEOUT"


def test_connect_timeout_maps_to_network_error(monkeypatch):
    """连接阶段超时与 NestJS 的 UND_ERR_CONNECT_TIMEOUT 同口径,归网络错误。"""
    _raise_on_post(monkeypatch, httpx.ConnectTimeout("connect timed out"))
    with pytest.raises(RuntimeError) as exc:
        ai._post_chat(_cfg(), "system", "user", 16, timeout_ms=1000)
    assert str(exc.value) == "LLM_NETWORK_ERROR"


def test_connect_error_maps_to_network_error(monkeypatch):
    _raise_on_post(monkeypatch, httpx.ConnectError("connection refused"))
    with pytest.raises(RuntimeError) as exc:
        ai._post_chat(_cfg(), "system", "user", 16, timeout_ms=1000)
    assert str(exc.value) == "LLM_NETWORK_ERROR"


def test_error_code_to_http_status():
    with pytest.raises(ApiException) as timeout_exc:
        ai._raise_from_code("LLM_TIMEOUT")
    assert (timeout_exc.value.code, timeout_exc.value.status_code) == (504, 504)

    with pytest.raises(ApiException) as network_exc:
        ai._raise_from_code("LLM_NETWORK_ERROR")
    assert (network_exc.value.code, network_exc.value.status_code) == (502, 502)


def test_optimize_image_surfaces_504_on_timeout(monkeypatch, session):
    """端到端:主图优化遇上游超时 -> 504 + LLM_TIMEOUT 日志;网络错误 -> 502。"""
    merchant_id = make_temp_merchant(session)
    _configure_ai(monkeypatch)
    try:
        _raise_on_post(monkeypatch, httpx.ReadTimeout("read timed out"))
        with pytest.raises(ApiException) as exc:
            ai.optimize_image(session, merchant_id, "image/jpeg", "data:image/jpeg;base64,AAAA", 4)
        assert (exc.value.code, exc.value.status_code) == (504, 504)

        _raise_on_post(monkeypatch, httpx.ConnectError("connection refused"))
        with pytest.raises(ApiException) as exc2:
            ai.optimize_image(session, merchant_id, "image/jpeg", "data:image/jpeg;base64,AAAA", 4)
        assert (exc2.value.code, exc2.value.status_code) == (502, 502)

        logged = [
            r[0] for r in session.execute(
                text("SELECT error_message FROM ai_analysis_log WHERE merchant_id = :m ORDER BY id"),
                {"m": merchant_id},
            ).fetchall()
        ]
        assert logged == ["LLM_TIMEOUT", "LLM_NETWORK_ERROR"], logged
    finally:
        session.execute(text("DELETE FROM ai_analysis_log WHERE merchant_id = :m"), {"m": merchant_id})
        session.commit()
        cleanup_temp_merchant(session, merchant_id)
