"""AI 分入口配置回归(P7 v1.1 §7.1 用例 1–24)。

覆盖:解析回落 / 单字段覆盖 / enabled 停用 / 掩码与投影 / 审计无密钥材料 / 权限 403·401 /
省略=不修改 / null=清除 / 空串 400 / 掩码与指纹回写 400 / 缓存失效 / DB 不可达降级 /
日限流与请求参数取 DB 值 / entry 404 / verify / 加解密往返 / 落库即密文 /
ENC key 缺失·换错·非法·密文格式非法四态 / 轮换脚本(读旧写新·幂等·失败行不改·退出码) / 指纹一致性。

隔离:monkeypatch 设定加密密钥与 env;新增的配置行与审计行**按主键 id** 记录后删除(铁律 5:禁止宽泛谓词),
teardown 断言两表行数回到基线。凭据纪律:只用测试占位密钥;密文仅在「是否 v1: 前缀」层面断言。
"""

import importlib.util
import json
import logging
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from app.core.config import get_settings
from app.core.error_handlers import VALIDATION_MESSAGE
from app.core.exceptions import ApiException
from app.core.security import hash_password
from app.db.models.admin_account import AdminAccount
from app.services import ai, ai_config, ai_crypto
from tests.conftest import cleanup_temp_admin

KEY_A = "a1" * 32
KEY_B = "b2" * 32
KEY_C = "c3" * 32
ENV_KEY = "env-key-placeholder-0001"
NEW_KEY = "sk-new-plaintext-key-0001"
ENV_BASE_URL = "https://env.example.com/v1"
ENV_MODEL = "env-model-1"
LIST_PATH = "/api/admin/ai-config/list"
PUT_PATH = "/api/admin/ai-config/analysis"
VERIFY_PATH = "/api/admin/ai-config/analysis/verify"
ENTRY_VIEW_KEYS = {"entry", "enabled", "apiKeySet", "apiKeyMasked", "apiKeyFingerprint", "apiKeyStatus",
                   "baseUrl", "model", "timeoutMs", "maxTokens", "dailyLimit", "effectiveSource",
                   "updatedBy", "updatedAt"}


def _load_rotator():
    path = Path(__file__).resolve().parents[1] / "scripts" / "rotate_ai_config_key.py"
    spec = importlib.util.spec_from_file_location("rotate_ai_config_key", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


rotator = _load_rotator()


@pytest.fixture(autouse=True)
def ai_enc_env(monkeypatch):
    """测试用加密密钥与 env 取值(monkeypatch 自动恢复;不触碰真实 .env)。"""
    settings = get_settings()
    for name, value in (("AI_CONFIG_ENC_KEY", KEY_A), ("AI_CONFIG_ENC_KEY_PREVIOUS", ""),
                        ("AI_API_KEY", ENV_KEY), ("AI_BASE_URL", ENV_BASE_URL), ("AI_MODEL", ENV_MODEL),
                        ("AI_TIMEOUT_MS", 11111), ("AI_DAILY_LIMIT", 3),
                        ("IMAGE_OPT_TIMEOUT_MS", 22222), ("IMAGE_OPT_MAX_TOKENS", 8000),
                        ("AI_IMAGE_OPT_DAILY_LIMIT", 5), ("TITLE_OPT_TIMEOUT_MS", 33333),
                        ("TITLE_OPT_MAX_TOKENS", 4000), ("AI_TITLE_OPT_DAILY_LIMIT", 5)):
        monkeypatch.setattr(settings, name, value, raising=False)
    ai_config.invalidate_cache()
    yield
    ai_config.invalidate_cache()


@pytest.fixture()
def clean_config_rows(session):
    """按 id 清理本用例新增的配置行与审计行,并断言回到基线行数。"""
    session.commit()
    before_entry = {int(x) for x in session.execute(text("SELECT id FROM ai_entry_config")).scalars().all()}
    before_audit = {int(x) for x in session.execute(text("SELECT id FROM admin_ai_config_audit")).scalars().all()}
    yield
    session.commit()
    for table, before in (("ai_entry_config", before_entry), ("admin_ai_config_audit", before_audit)):
        current = [int(x) for x in session.execute(text("SELECT id FROM " + table)).scalars().all()]
        for row_id in current:
            if row_id not in before:
                session.execute(text("DELETE FROM " + table + " WHERE id = :i"), {"i": row_id})
        session.commit()
        remaining = {int(x) for x in session.execute(text("SELECT id FROM " + table)).scalars().all()}
        assert remaining == before, (table, remaining, before)
    ai_config.invalidate_cache()


@pytest.fixture()
def admins(client, session):
    """创建临时管理员并返回取 token 的函数(结束按 username 清理)。"""
    created = []

    def _token(role: str = "super_admin") -> str:
        username = f"_test_aiadmin_{uuid.uuid4().hex[:8]}"
        password = "Test@12345"
        enc, salt = hash_password(password)
        session.add(AdminAccount(username=username, passwordHash=enc, salt=salt,
                                 realName="AI 配置测试", role=role, status=1))
        session.commit()
        created.append(username)
        resp = client.post("/api/admin/auth/login", json={"username": username, "password": password})
        assert resp.status_code == 200, resp.text
        return resp.json()["data"]["token"]

    yield _token
    for name in created:
        cleanup_temp_admin(session, name)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _row_ids(session):
    session.commit()
    return [int(x) for x in session.execute(text("SELECT id FROM ai_entry_config ORDER BY id")).scalars().all()]


def _scalar(session, sql: str, params=None):
    """先结束本会话事务再读,避免 REPEATABLE READ 快照读到写前的旧值(见 #PB-11 经验)。"""
    session.commit()
    return session.execute(text(sql), params or {}).scalar()


def _one(session, sql: str, params=None):
    session.commit()
    return session.execute(text(sql), params or {}).mappings().first()


def _audit_ids(session):
    session.commit()
    return [int(x) for x in session.execute(text("SELECT id FROM admin_ai_config_audit ORDER BY id")).scalars().all()]


def _audit_rows(session, ids):
    session.commit()
    return [dict(r) for r in session.execute(
        text("SELECT * FROM admin_ai_config_audit WHERE id IN :ids").bindparams(
            __import__("sqlalchemy").bindparam("ids", expanding=True)), {"ids": tuple(ids)}).mappings().all()]


def _insert_row(session, entry: str, *, ciphertext=None, fingerprint=None, enabled=1, **columns) -> int:
    row = {"entry": entry, "enabled": enabled, "api_key_ciphertext": ciphertext,
           "api_key_fingerprint": fingerprint}
    row.update(columns)
    cols = ", ".join(row)
    binds = ", ".join(":" + c for c in row)
    session.execute(text(f"INSERT INTO ai_entry_config ({cols}) VALUES ({binds})"), row)
    session.commit()
    ai_config.invalidate_cache()
    return int(session.execute(text("SELECT id FROM ai_entry_config WHERE entry = :e"), {"e": entry}).scalar())


# ---------- 用例 1–3:解析与合并 ----------

def test_resolve_falls_back_to_env_without_row(session, clean_config_rows):
    cfg = ai_config.resolve_config(session, "analysis")

    assert cfg.api_key == ENV_KEY and cfg.base_url == ENV_BASE_URL and cfg.model == ENV_MODEL
    assert cfg.timeout_ms == 11111 and cfg.max_tokens == 4096 and cfg.daily_limit == 3
    assert cfg.key_status == "none" and cfg.key_fingerprint is None
    assert set(cfg.sources.values()) == {"env"}


def test_single_field_override_keeps_others_env(client, session, admins, clean_config_rows):
    token = admins()
    resp = client.put(PUT_PATH, headers=_auth(token), json={"api_key": NEW_KEY})
    assert resp.status_code == 200, resp.text
    session.commit()   # 写路径已失效缓存,再结束本会话事务快照以保证读到新行

    cfg = ai_config.resolve_config(session, "analysis")
    assert cfg.api_key == NEW_KEY and cfg.sources["api_key"] == "db"
    assert cfg.base_url == ENV_BASE_URL and cfg.sources["base_url"] == "env"
    assert cfg.model == ENV_MODEL and cfg.sources["model"] == "env"
    assert cfg.key_status == "ok" and cfg.key_fingerprint == ai_crypto.fingerprint(NEW_KEY)


def test_enabled_zero_ignores_row(session, clean_config_rows):
    _insert_row(session, "analysis", enabled=0, base_url="https://db.example.com/v1", model="db-model")

    cfg = ai_config.resolve_config(session, "analysis")
    assert cfg.base_url == ENV_BASE_URL and cfg.model == ENV_MODEL
    assert set(cfg.sources.values()) == {"env"}


# ---------- 用例 4–5:投影与审计 ----------

def test_list_masks_key_and_never_leaks_material(client, session, admins, clean_config_rows):
    token = admins()
    assert client.put(PUT_PATH, headers=_auth(token), json={"api_key": NEW_KEY}).status_code == 200

    resp = client.get(LIST_PATH, headers=_auth(token))
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]
    entry = next(item for item in items if item["entry"] == "analysis")

    assert set(entry) == ENTRY_VIEW_KEYS                      # 无长度/密文字段
    assert entry["apiKeySet"] is True
    assert entry["apiKeyMasked"] == NEW_KEY[:3] + "****" + NEW_KEY[-4:]
    assert entry["apiKeyFingerprint"] == ai_crypto.fingerprint(NEW_KEY)
    assert entry["apiKeyStatus"] == "ok"
    assert NEW_KEY not in resp.text                           # 绝不回密钥原文
    assert "v1:" not in resp.text                             # 绝不回密文
    assert KEY_A not in resp.text                             # 绝不回 ENC key


def test_audit_rows_contain_masks_lengths_fingerprints_only(client, session, admins, clean_config_rows):
    token = admins()
    before = set(_audit_ids(session))
    assert client.put(PUT_PATH, headers=_auth(token),
                      json={"api_key": NEW_KEY, "base_url": "https://user:pass@db.example.com/v1",
                            "model": "db-model"}).status_code == 200
    created = [i for i in _audit_ids(session) if i not in before]
    rows = _audit_rows(session, created)

    assert len(rows) == 3                                     # 三个变更字段各一行
    blob = json.dumps(rows, ensure_ascii=False, default=str)
    assert NEW_KEY not in blob and "v1:" not in blob and KEY_A not in blob
    key_row = next(r for r in rows if r["field"] == "api_key")
    assert key_row["action"] == "update"
    assert key_row["new_display"] == NEW_KEY[:3] + "****" + NEW_KEY[-4:]
    assert key_row["new_len"] == len(NEW_KEY) and key_row["new_fp"] == ai_crypto.fingerprint(NEW_KEY)
    assert key_row["old_display"] is None and key_row["old_len"] is None and key_row["old_fp"] is None
    url_row = next(r for r in rows if r["field"] == "base_url")
    assert "pass" not in (url_row["new_display"] or "")        # userinfo 脱敏
    assert url_row["new_display"] == "https://****@db.example.com/v1"


# ---------- 用例 6–7:权限 ----------

def test_non_super_admin_forbidden(client, session, admins, clean_config_rows):
    for role in ("admin", "viewer"):
        token = admins(role)
        get_resp = client.get(LIST_PATH, headers=_auth(token))
        put_resp = client.put(PUT_PATH, headers=_auth(token), json={"model": "x"})
        verify_resp = client.post(VERIFY_PATH, headers=_auth(token))
        for resp in (get_resp, put_resp, verify_resp):
            assert resp.status_code == 403, (role, resp.status_code, resp.text)
            assert resp.json()["message"] == "无权限执行该操作"


def test_no_token_unauthorized(client):
    assert client.get(LIST_PATH).status_code == 401
    assert client.put(PUT_PATH, json={"model": "x"}).status_code == 401
    assert client.post(VERIFY_PATH).status_code == 401


# ---------- 用例 8–11:写入语义 ----------

def test_omitted_field_not_modified(client, session, admins, clean_config_rows):
    token = admins()
    assert client.put(PUT_PATH, headers=_auth(token), json={"api_key": NEW_KEY}).status_code == 200
    row_id = _row_ids(session)[-1]
    before_ct = _scalar(session, "SELECT api_key_ciphertext FROM ai_entry_config WHERE id=:i", {"i": row_id})
    before_audit = set(_audit_ids(session))

    assert client.put(PUT_PATH, headers=_auth(token), json={"model": "changed-model"}).status_code == 200

    after_ct = _scalar(session, "SELECT api_key_ciphertext FROM ai_entry_config WHERE id=:i", {"i": row_id})
    assert after_ct == before_ct                              # 密文逐字节不变
    new_audits = [i for i in _audit_ids(session) if i not in before_audit]
    assert len(new_audits) == 1                               # 只有 model 一行审计
    assert _audit_rows(session, new_audits)[0]["field"] == "model"


def test_explicit_null_clears_and_falls_back(client, session, admins, clean_config_rows):
    token = admins()
    client.put(PUT_PATH, headers=_auth(token), json={"api_key": NEW_KEY})
    row_id = _row_ids(session)[-1]

    resp = client.put(PUT_PATH, headers=_auth(token), json={"api_key": None})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["apiKeySet"] is False and data["apiKeyMasked"] is None
    assert data["effectiveSource"]["apiKey"] == "env" and data["apiKeyStatus"] == "none"

    stored = _one(session, "SELECT api_key_ciphertext, api_key_fingerprint FROM ai_entry_config WHERE id=:i",
                  {"i": row_id})
    assert stored["api_key_ciphertext"] is None and stored["api_key_fingerprint"] is None
    clears = [r for r in _audit_rows(session, _audit_ids(session)) if r["field"] == "api_key" and r["action"] == "clear"]
    assert clears and clears[-1]["new_display"] is None


def test_empty_string_rejected(client, session, admins, clean_config_rows):
    token = admins()
    for payload in ({"api_key": ""}, {"model": ""}):
        resp = client.put(PUT_PATH, headers=_auth(token), json=payload)
        assert resp.status_code == 400, (payload, resp.status_code, resp.text)
        assert "空字符串" in resp.json()["message"]
    # base_url 由 schema 层模式校验先拦(要求 ^https?://),同样是 400 且文案为口语化中文
    url_resp = client.put(PUT_PATH, headers=_auth(token), json={"base_url": ""})
    assert url_resp.status_code == 400
    # #PB-24-1-R1:校验失败文案不再回显英文字段名(原断言检查 message 含 "base_url")
    assert url_resp.json()["message"] == VALIDATION_MESSAGE
    assert _row_ids(session) == []                            # 未写库
    assert _audit_ids(session) == []


def test_mask_and_fingerprint_write_back_rejected(client, session, admins, clean_config_rows):
    token = admins()
    client.put(PUT_PATH, headers=_auth(token), json={"api_key": NEW_KEY})
    masked = client.get(LIST_PATH, headers=_auth(token)).json()["data"]
    entry = next(i for i in masked if i["entry"] == "analysis")
    before_ct = _scalar(session, "SELECT api_key_ciphertext FROM ai_entry_config")

    mask_resp = client.put(PUT_PATH, headers=_auth(token), json={"api_key": entry["apiKeyMasked"]})
    assert mask_resp.status_code == 400 and "掩码" in mask_resp.json()["message"]
    fp_resp = client.put(PUT_PATH, headers=_auth(token), json={"api_key": entry["apiKeyFingerprint"]})
    assert fp_resp.status_code == 400 and "指纹" in fp_resp.json()["message"]

    assert _scalar(session, "SELECT api_key_ciphertext FROM ai_entry_config") == before_ct


# ---------- 用例 12–15:缓存、降级、参数生效 ----------

def test_write_invalidates_cache_immediately(client, session, admins, clean_config_rows):
    token = admins()
    assert ai_config.resolve_config(session, "analysis").api_key == ENV_KEY
    assert client.put(PUT_PATH, headers=_auth(token), json={"api_key": NEW_KEY}).status_code == 200
    session.commit()   # 结束当前事务快照(REPEATABLE READ 下否则读到旧行)
    assert ai_config.resolve_config(session, "analysis").api_key == NEW_KEY   # 不等 TTL


def test_db_unreachable_falls_back_to_env(caplog):
    class _BrokenSession:
        def execute(self, *args, **kwargs):
            raise RuntimeError("db down")

    ai_config.invalidate_cache()
    with caplog.at_level(logging.WARNING, logger="api"):
        cfg = ai_config.resolve_config(_BrokenSession(), "analysis")

    assert cfg.api_key == ENV_KEY and cfg.sources["api_key"] == "env"
    assert any("回落 env" in record.getMessage() for record in caplog.records)


def test_daily_limit_from_db_is_enforced(monkeypatch, session, clean_config_rows):
    _insert_row(session, "analysis", ciphertext=ai_crypto.encrypt_secret(NEW_KEY, bytes.fromhex(KEY_A)),
                fingerprint=ai_crypto.fingerprint(NEW_KEY), daily_limit=1)
    monkeypatch.setattr(ai, "shop_get_summary", lambda db, mid, tr: {"star": {"shop_star": "4.8"}})
    monkeypatch.setattr(ai, "_count_today_success", lambda db, mid, t: 1)

    with pytest.raises(ApiException) as excinfo:
        ai.analyze(session, "m1", "7d", "127.0.0.1")
    assert excinfo.value.code == 429


def test_entry_params_reach_llm_payload(monkeypatch, session, clean_config_rows):
    captured = {}

    class _Resp:
        status_code = 200
        is_success = True
        def json(self):
            return {"choices": [{"message": {"content": json.dumps({"summary": "s", "strengths": [], "weaknesses": [], "suggestions": []})}}]}

    def fake_post(url, headers=None, json=None, timeout=None, **kwargs):
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return _Resp()

    _insert_row(session, "analysis", ciphertext=ai_crypto.encrypt_secret(NEW_KEY, bytes.fromhex(KEY_A)),
                fingerprint=ai_crypto.fingerprint(NEW_KEY), base_url="https://db.example.com/v1",
                model="db-model", timeout_ms=5555, max_tokens=1234, daily_limit=9)
    monkeypatch.setattr(ai.httpx, "post", fake_post)
    monkeypatch.setattr(ai, "shop_get_summary", lambda db, mid, tr: {"star": {"shop_star": "4.8"}})
    monkeypatch.setattr(ai, "_count_today_success", lambda db, mid, t: 0)
    monkeypatch.setattr(ai, "_log_insert", lambda *a, **k: None)

    result = ai.analyze(session, "m1", "7d", "127.0.0.1")

    assert result["summary"] == "s"
    assert captured["url"] == "https://db.example.com/v1/chat/completions"
    assert captured["json"]["model"] == "db-model" and captured["json"]["max_tokens"] == 1234
    assert captured["timeout"] == 5555 / 1000
    assert captured["headers"]["Authorization"] == "Bearer " + NEW_KEY


# ---------- 用例 16–17:entry 与 verify ----------

def test_unknown_entry_returns_404(client, session, admins, clean_config_rows):
    token = admins()
    assert client.put("/api/admin/ai-config/foo", headers=_auth(token), json={"model": "x"}).status_code == 404
    assert client.post("/api/admin/ai-config/foo/verify", headers=_auth(token)).status_code == 404


def test_verify_success_and_failure(monkeypatch, client, session, admins, clean_config_rows):
    token = admins()
    client.put(PUT_PATH, headers=_auth(token), json={"api_key": NEW_KEY})

    class _Ok:
        status_code = 200
        is_success = True
        def json(self):
            return {"choices": [{"message": {"content": "o"}}]}

    monkeypatch.setattr(ai.httpx, "post", lambda *a, **k: _Ok())
    ok = client.post(VERIFY_PATH, headers=_auth(token))
    assert ok.status_code == 200, ok.text
    assert ok.json()["data"]["entry"] == "analysis" and NEW_KEY not in ok.text

    class _Bad:
        status_code = 401
        is_success = False
        def json(self):
            return {}

    monkeypatch.setattr(ai.httpx, "post", lambda *a, **k: _Bad())
    bad = client.post(VERIFY_PATH, headers=_auth(token))
    assert bad.status_code == 502, bad.text
    assert NEW_KEY not in bad.text                            # 失败信息不泄漏密钥


# ---------- 用例 18–19:加解密与落库 ----------

def test_crypto_roundtrip_and_random_nonce():
    key = bytes.fromhex(KEY_A)
    first = ai_crypto.encrypt_secret(NEW_KEY, key)
    second = ai_crypto.encrypt_secret(NEW_KEY, key)

    assert first.startswith("v1:") and second.startswith("v1:")
    assert first != second                                    # 随机 nonce
    assert ai_crypto.decrypt_secret(first, [key]) == NEW_KEY
    assert ai_crypto.decrypt_secret(second, [key]) == NEW_KEY
    assert ai_crypto.plaintext_length_from_ciphertext(first) == len(NEW_KEY)


def test_db_stores_ciphertext_never_plaintext(client, session, admins, clean_config_rows):
    token = admins()
    client.put(PUT_PATH, headers=_auth(token), json={"api_key": NEW_KEY})
    row_id = _row_ids(session)[-1]

    stored = _one(session, "SELECT api_key_ciphertext, api_key_fingerprint FROM ai_entry_config WHERE id=:i",
                  {"i": row_id})
    ciphertext = stored["api_key_ciphertext"]
    assert ciphertext.startswith("v1:")
    assert ciphertext != NEW_KEY and NEW_KEY not in ciphertext
    assert stored["api_key_fingerprint"] == ai_crypto.fingerprint(NEW_KEY)
    # 用 ENC key 能解回原文(证明密文有效)
    assert ai_crypto.decrypt_secret(ciphertext, [bytes.fromhex(KEY_A)]) == NEW_KEY


# ---------- 用例 20–22:降级四态 ----------

def _write_key_row(client, session, admins, clean_config_rows) -> int:
    token = admins()
    assert client.put(PUT_PATH, headers=_auth(token), json={"api_key": NEW_KEY}).status_code == 200
    return _row_ids(session)[-1]


def test_decrypt_failed_when_enc_key_missing(monkeypatch, caplog, client, session, admins, clean_config_rows):
    _write_key_row(client, session, admins, clean_config_rows)
    monkeypatch.setattr(get_settings(), "AI_CONFIG_ENC_KEY", "", raising=False)
    ai_config.invalidate_cache()

    with caplog.at_level(logging.WARNING, logger="api"):
        cfg = ai_config.resolve_config(session, "analysis")
    assert cfg.api_key == ENV_KEY and cfg.sources["api_key"] == "env"
    assert cfg.key_status == "decrypt_failed"
    assert any("enc_key_missing" in record.getMessage() for record in caplog.records)

    token = admins()
    resp = client.get(LIST_PATH, headers=_auth(token))
    assert resp.status_code == 200                            # 绝不 500
    entry = next(i for i in resp.json()["data"] if i["entry"] == "analysis")
    assert entry["apiKeySet"] is False and entry["apiKeyMasked"] is None
    assert entry["apiKeyStatus"] == "decrypt_failed" and entry["effectiveSource"]["apiKey"] == "env"


def test_decrypt_failed_when_enc_key_wrong(monkeypatch, caplog, client, session, admins, clean_config_rows):
    _write_key_row(client, session, admins, clean_config_rows)
    monkeypatch.setattr(get_settings(), "AI_CONFIG_ENC_KEY", KEY_B, raising=False)
    ai_config.invalidate_cache()

    with caplog.at_level(logging.WARNING, logger="api"):
        cfg = ai_config.resolve_config(session, "analysis")
    assert cfg.api_key == ENV_KEY and cfg.key_status == "decrypt_failed"
    assert any("auth_tag_mismatch" in record.getMessage() for record in caplog.records)


def test_invalid_enc_key_read_fallback_and_write_400(monkeypatch, caplog, client, session, admins, clean_config_rows):
    _write_key_row(client, session, admins, clean_config_rows)
    monkeypatch.setattr(get_settings(), "AI_CONFIG_ENC_KEY", "placeholder-not-hex", raising=False)
    ai_config.invalidate_cache()

    with caplog.at_level(logging.WARNING, logger="api"):
        cfg = ai_config.resolve_config(session, "analysis")
    assert cfg.api_key == ENV_KEY and cfg.key_status == "decrypt_failed"
    assert any("enc_key_invalid" in record.getMessage() for record in caplog.records)

    before_audit = set(_audit_ids(session))
    token = admins()
    resp = client.put(PUT_PATH, headers=_auth(token), json={"api_key": "another-plaintext-key"})
    assert resp.status_code == 400, resp.text
    assert "加密密钥未配置或非法" in resp.json()["message"]
    assert set(_audit_ids(session)) == before_audit           # 不写审计


def test_format_invalid_ciphertext_falls_back(monkeypatch, caplog, session, clean_config_rows):
    _insert_row(session, "analysis", ciphertext="not-a-ciphertext", fingerprint="deadbeefdeadbeef")
    monkeypatch.setattr(get_settings(), "AI_CONFIG_ENC_KEY", KEY_A, raising=False)
    ai_config.invalidate_cache()

    with caplog.at_level(logging.WARNING, logger="api"):
        cfg = ai_config.resolve_config(session, "analysis")
    assert cfg.api_key == ENV_KEY and cfg.key_status == "decrypt_failed"
    assert any("format_invalid" in record.getMessage() for record in caplog.records)


# ---------- 用例 23:轮换脚本 ----------

def test_rotation_script_rotates_is_idempotent_and_reports_failures(session, clean_config_rows):
    old_key, new_key, third_key = bytes.fromhex(KEY_A), bytes.fromhex(KEY_B), bytes.fromhex(KEY_C)
    analysis_id = _insert_row(session, "analysis", ciphertext=ai_crypto.encrypt_secret(NEW_KEY, old_key),
                              fingerprint=ai_crypto.fingerprint(NEW_KEY))

    def _cipher(row_id):
        return _scalar(session, "SELECT api_key_ciphertext FROM ai_entry_config WHERE id=:i", {"i": row_id})

    # ① dry-run:只报告、不写库(此阶段仅有可轮换行 → 退出码 0)
    assert rotator.main(["--old-key", KEY_A, "--new-key", KEY_B, "--dry-run"]) == 0
    dry_cipher = _cipher(analysis_id)
    assert ai_crypto.decrypt_secret(dry_cipher, [old_key]) == NEW_KEY     # 仍是旧密钥密文

    # ② 真实轮换:读旧写新
    assert rotator.main(["--old-key", KEY_A, "--new-key", KEY_B]) == 0
    rotated = _cipher(analysis_id)
    assert rotated != dry_cipher
    assert ai_crypto.decrypt_secret(rotated, [new_key]) == NEW_KEY

    # ③ 幂等:二次运行 0 变更
    assert rotator.main(["--old-key", KEY_A, "--new-key", KEY_B]) == 0
    assert _cipher(analysis_id) == rotated

    # ④ 失败行(tile 入口用第三把钥匙加密,新旧钥匙都解不开)→ 失败清单 + 退出码非 0 + 该行不变
    stuck_id = _insert_row(session, "title_optimize", ciphertext=ai_crypto.encrypt_secret(NEW_KEY, third_key),
                           fingerprint=ai_crypto.fingerprint(NEW_KEY))
    stuck_before = _cipher(stuck_id)
    assert rotator.main(["--old-key", KEY_A, "--new-key", KEY_B]) == 1
    assert _cipher(stuck_id) == stuck_before                              # 失败行未被改动
    assert _cipher(analysis_id) == rotated                                # 可轮换行不受影响

    # ⑤ 参数错误 → exit 2
    assert rotator.main(["--old-key", "bad", "--new-key", KEY_B]) == 2


# ---------- 用例 24:指纹 ----------

def test_fingerprint_consistency():
    assert ai_crypto.fingerprint(NEW_KEY) == ai_crypto.fingerprint(NEW_KEY)
    assert ai_crypto.fingerprint(NEW_KEY) != ai_crypto.fingerprint(NEW_KEY + "x")
    assert len(ai_crypto.fingerprint(NEW_KEY)) == 16
    assert all(c in "0123456789abcdef" for c in ai_crypto.fingerprint(NEW_KEY))
    assert NEW_KEY not in ai_crypto.fingerprint(NEW_KEY)
