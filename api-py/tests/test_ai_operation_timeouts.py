"""AI 各操作超时配置回归(B6)。

背景:修复前 _post_chat 统一使用 AI_TIMEOUT_MS,图片优化/标题优化忽略了已存在的
IMAGE_OPT_TIMEOUT_MS / TITLE_OPT_TIMEOUT_MS(config.py:66/70)。NestJS 三个入口各自取配置:
  ai-analysis.service.ts:120 -> AI_TIMEOUT_MS、image-optimize.service.ts:105 -> IMAGE_OPT_TIMEOUT_MS、
  title-optimize.service.ts:124 -> TITLE_OPT_TIMEOUT_MS。
修复后:timeout_ms 由调用方按操作类型显式传入(无默认值,漏传即 TypeError),不硬编码数值。

隔离:临时商家;LLM 调用被 monkeypatch 拦截(不触网);ai_analysis_log / shop_trade_data finally 清理。
"""

import uuid

from sqlalchemy import text

from app.services import ai
from app.services.ai_config import EntryConfig

from tests.conftest import cleanup_temp_merchant, make_temp_merchant

_FAKE_LLM_JSON = '{"summary": "ok", "strengths": [], "weaknesses": [], "suggestions": []}'


def test_post_chat_uses_passed_timeout(monkeypatch):
    """_post_chat 使用调用方传入的 timeout_ms(换算为秒),不再读死 AI_TIMEOUT_MS。"""
    captured = {}

    class _Resp:
        status_code = 200
        is_success = True

        def json(self):
            return {"choices": [{"message": {"content": "{}"}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["timeout"] = timeout
        return _Resp()

    monkeypatch.setattr(ai.httpx, "post", fake_post)
    # #PB-21:key/base_url/model 由解析后的 cfg 提供(调用方不再自行读 settings.AI_*)
    cfg = EntryConfig(entry="analysis", api_key="test-key", base_url="http://127.0.0.1:9/v1",
                      model="test-model", timeout_ms=45000, max_tokens=16, daily_limit=0,
                      sources={}, key_status="ok", key_fingerprint=None)

    ai._post_chat(cfg, "system", "user", 16, timeout_ms=45000)
    assert captured["timeout"] == 45.0


def test_each_operation_uses_its_own_timeout(monkeypatch, session):
    """analyze / optimize_image / optimize_title 分别使用 AI / IMAGE_OPT / TITLE_OPT 超时配置。"""
    merchant_id = make_temp_merchant(session)
    monkeypatch.setattr(ai.settings, "AI_TIMEOUT_MS", 111000)
    monkeypatch.setattr(ai.settings, "IMAGE_OPT_TIMEOUT_MS", 222000)
    monkeypatch.setattr(ai.settings, "TITLE_OPT_TIMEOUT_MS", 333000)
    seen = []
    monkeypatch.setattr(ai, "_post_chat", lambda *a, **kw: seen.append(kw.get("timeout_ms")) or _FAKE_LLM_JSON)
    try:
        session.execute(
            text("INSERT INTO shop_trade_data (merchant_id, data_date, time_range, trade_amount) "
                 "VALUES (:m, '2026-09-01', '7d', 1)"),
            {"m": merchant_id},
        )
        session.commit()

        ai.analyze(session, merchant_id, "7d", "_test_ip_" + uuid.uuid4().hex[:8])
        ai.optimize_image(session, merchant_id, "image/jpeg", "data:image/jpeg;base64,AAAA", 4)
        ai.optimize_title(session, merchant_id, {"mode": "generate", "brand": "测试品牌"})

        assert seen == [111000, 222000, 333000], seen
    finally:
        session.execute(text("DELETE FROM ai_analysis_log WHERE merchant_id = :m"), {"m": merchant_id})
        session.execute(text("DELETE FROM shop_trade_data WHERE merchant_id = :m"), {"m": merchant_id})
        session.commit()
        cleanup_temp_merchant(session, merchant_id)
