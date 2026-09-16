"""AI 分入口配置服务(P7 v1.1 §四/§五)——解析/合并/掩码/写入/审计的**唯一实现**。

- 优先级:字段级合并(DB 该字段非 NULL → 用 DB;NULL → 回落 env 同名字段);
- 缓存:进程内 TTL 60s(键=入口,上界 3)+ **写路径主动失效**;缓存只持有**密文行快照**,
  密钥原文仅在单次解析/单次调用期间存在于内存(不落日志、不进接口、不进审计);
- 降级:库中有密文但 ENC key 缺失/换错/占位/密文格式非法 → **视为未配置**、回落 env、
  记结构化 warning,**绝不 500、不阻断启动**;写入路径遇密钥问题 → **400**(不写库、不写审计);
- 明确不做(P7 §3.5.4 禁令):启动期 fail-fast、启动期 DB 探测。
"""
import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ApiException
from app.core.timeutil import to_iso_utc
from app.db.models.admin_ai_config_audit import AdminAiConfigAudit
from app.db.models.ai_entry_config import AiEntryConfig
from app.services import ai_crypto

logger = logging.getLogger("api")

ENTRIES: Tuple[str, ...] = ("analysis", "image_optimize", "title_optimize")
CACHE_TTL_SECONDS = 60
MIN_API_KEY_LENGTH = 8
MAX_API_KEY_LENGTH = 256
# 分析入口 env 无 max_tokens 项(历史硬编码 4096,P7 §2.1);后台可配后统一为 max_tokens 字段
ANALYSIS_DEFAULT_MAX_TOKENS = 4096

SOURCE_DB = "db"
SOURCE_ENV = "env"
STATUS_OK = "ok"
STATUS_DECRYPT_FAILED = "decrypt_failed"
STATUS_NONE = "none"

# 可写字段(与审计 field 枚举一致)
WRITABLE_FIELDS: Tuple[str, ...] = ("api_key", "base_url", "model", "timeout_ms", "max_tokens",
                                    "daily_limit", "enabled")
# 参与「DB 覆盖 env」合并的非密钥字段
_MERGE_FIELDS: Tuple[str, ...] = ("base_url", "model", "timeout_ms", "max_tokens", "daily_limit")
_USERINFO_PATTERN = re.compile(r"^(?P<scheme>[a-zA-Z][a-zA-Z0-9+.\-]*://)(?P<userinfo>[^/@]+)@")


@dataclass(frozen=True)
class EntryConfig:
    """三入口解析后的生效配置(唯一出口;调用方不得自行读 settings.AI_*)。"""

    entry: str
    api_key: str
    base_url: str
    model: str
    timeout_ms: int
    max_tokens: int
    daily_limit: int
    sources: Dict[str, str]      # 非密钥字段 + api_key -> 'db' | 'env'
    key_status: str              # ok | decrypt_failed | none
    key_fingerprint: Optional[str]


@dataclass(frozen=True)
class _RowSnapshot:
    """ai_entry_config 行快照(**含密文**,不含密钥原文)。"""

    enabled: int
    ciphertext: Optional[str]
    fingerprint: Optional[str]
    base_url: Optional[str]
    model: Optional[str]
    timeout_ms: Optional[int]
    max_tokens: Optional[int]
    daily_limit: Optional[int]
    updated_by: Optional[str]
    updated_at: Optional[datetime]


_cache: Dict[str, Tuple[Optional[_RowSnapshot], float]] = {}
_cache_lock = threading.Lock()


def assert_entry(entry: str) -> str:
    """入口枚举校验;非法 → 404(P7 §5.2 错误码口径)。"""
    if entry not in ENTRIES:
        raise ApiException("入口不存在", code=404, status_code=404)
    return entry


def invalidate_cache(entry: Optional[str] = None) -> None:
    """写路径主动失效:清空某入口(或全部)缓存,使本进程立即生效。"""
    with _cache_lock:
        if entry is None:
            _cache.clear()
        else:
            _cache.pop(entry, None)


def _cached_row(entry: str) -> Optional[_RowSnapshot]:
    with _cache_lock:
        item = _cache.get(entry)
    if item is None:
        return None
    snapshot, loaded_at = item
    if time.time() - loaded_at > CACHE_TTL_SECONDS:
        return None
    return snapshot


def _load_row(db: Session, entry: str) -> Optional[_RowSnapshot]:
    """读一行配置(带 TTL 缓存);查库异常 → 记 warning 并返回 None(**不缓存失败结果**)。"""
    cached = _cached_row(entry)
    if cached is not None:
        return cached
    with _cache_lock:
        item = _cache.get(entry)
        if item is not None and (time.time() - item[1]) <= CACHE_TTL_SECONDS:
            return item[0]
    try:
        row = db.execute(select(AiEntryConfig).where(AiEntryConfig.entry == entry)).scalar_one_or_none()
    except Exception as exc:  # noqa: BLE001 - DB 不可达:回落 env,不缓存失败结果
        logger.warning(f"AI 配置读取失败,已回落 env: entry={entry} error={type(exc).__name__}")
        return None

    snapshot = None if row is None else _RowSnapshot(
        enabled=int(row.enabled or 0),
        ciphertext=row.api_key_ciphertext,
        fingerprint=row.api_key_fingerprint,
        base_url=row.base_url,
        model=row.model,
        timeout_ms=row.timeout_ms,
        max_tokens=row.max_tokens,
        daily_limit=row.daily_limit,
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )
    with _cache_lock:
        _cache[entry] = (snapshot, time.time())
    return snapshot


def env_defaults(entry: str) -> Dict[str, Any]:
    """该入口的 env 回落值(base_url/model 取自 AI_*,超时/tokens/日限流取该入口 env 项)。"""
    settings = get_settings()
    if entry == "analysis":
        return {"api_key": settings.AI_API_KEY, "base_url": settings.AI_BASE_URL, "model": settings.AI_MODEL,
                "timeout_ms": settings.AI_TIMEOUT_MS, "max_tokens": ANALYSIS_DEFAULT_MAX_TOKENS,
                "daily_limit": settings.AI_DAILY_LIMIT}
    if entry == "image_optimize":
        return {"api_key": settings.AI_API_KEY, "base_url": settings.AI_BASE_URL, "model": settings.AI_MODEL,
                "timeout_ms": settings.IMAGE_OPT_TIMEOUT_MS, "max_tokens": settings.IMAGE_OPT_MAX_TOKENS,
                "daily_limit": settings.AI_IMAGE_OPT_DAILY_LIMIT}
    return {"api_key": settings.AI_API_KEY, "base_url": settings.AI_BASE_URL, "model": settings.AI_MODEL,
            "timeout_ms": settings.TITLE_OPT_TIMEOUT_MS, "max_tokens": settings.TITLE_OPT_MAX_TOKENS,
            "daily_limit": settings.AI_TITLE_OPT_DAILY_LIMIT}


def resolve_config(db: Session, entry: str) -> EntryConfig:
    """解析某入口的生效配置(三入口的唯一取值出口,供 ai.py 调用)。"""
    assert_entry(entry)
    values = env_defaults(entry)
    sources = {field_name: SOURCE_ENV for field_name in ("api_key",) + _MERGE_FIELDS}
    key_status = STATUS_NONE
    key_fingerprint: Optional[str] = None

    snapshot = _load_row(db, entry)
    if snapshot is not None and int(snapshot.enabled or 0) == 1:
        if snapshot.ciphertext:
            try:
                values["api_key"] = ai_crypto.decrypt_secret(snapshot.ciphertext, ai_crypto.load_enc_keys())
                sources["api_key"] = SOURCE_DB
                key_status = STATUS_OK
            except ai_crypto.SecretDecryptError as exc:
                reason = exc.reason
                if reason == ai_crypto.REASON_KEY_MISSING:
                    # 区分「密钥槽位缺失」与「槽位存在但非法」(两者都要回落 env)
                    reason = ai_crypto.enc_key_state()
                key_status = STATUS_DECRYPT_FAILED
                logger.warning(f"AI 配置密钥解密失败,已回落 env: entry={entry} reason={reason}")
            key_fingerprint = snapshot.fingerprint
        for field_name in _MERGE_FIELDS:
            value = getattr(snapshot, field_name)
            if value is not None:
                values[field_name] = value
                sources[field_name] = SOURCE_DB

    return EntryConfig(entry=entry, sources=sources, key_status=key_status,
                       key_fingerprint=key_fingerprint, **values)


def _entry_view(db: Session, entry: str) -> Dict[str, Any]:
    """列表/写入响应的单入口投影(只回掩码 + 指纹 + 状态,**永不回明文/密文/长度/ENC key**)。"""
    cfg = resolve_config(db, entry)
    snapshot = _load_row(db, entry)
    key_ok = cfg.key_status == STATUS_OK
    return {
        "entry": entry,
        "enabled": bool(snapshot.enabled) if snapshot is not None else True,
        "apiKeySet": key_ok,
        "apiKeyMasked": ai_crypto.mask_secret(cfg.api_key) if key_ok else None,
        "apiKeyFingerprint": cfg.key_fingerprint,
        "apiKeyStatus": cfg.key_status,
        "baseUrl": cfg.base_url,
        "model": cfg.model,
        "timeoutMs": cfg.timeout_ms,
        "maxTokens": cfg.max_tokens,
        "dailyLimit": cfg.daily_limit,
        "effectiveSource": {
            "apiKey": cfg.sources["api_key"],
            "baseUrl": cfg.sources["base_url"],
            "model": cfg.sources["model"],
            "timeoutMs": cfg.sources["timeout_ms"],
            "maxTokens": cfg.sources["max_tokens"],
            "dailyLimit": cfg.sources["daily_limit"],
        },
        "updatedBy": snapshot.updated_by if snapshot is not None else None,
        "updatedAt": to_iso_utc(snapshot.updated_at) if snapshot is not None else None,
    }


def list_entry_configs(db: Session) -> List[Dict[str, Any]]:
    """三入口配置总览(仅 super_admin 可达;投影见 _entry_view)。"""
    return [_entry_view(db, entry) for entry in ENTRIES]


def _mask_userinfo(value: Optional[str]) -> Optional[str]:
    """base_url 含 userinfo(`scheme://user:pass@host`)时脱敏为 `scheme://****@host`。"""
    if not value:
        return value
    return _USERINFO_PATTERN.sub(lambda m: m.group("scheme") + "****@", value)


def _display_value(field_name: str, value: Any) -> Optional[str]:
    """审计 old/new_display 的展示值:非密钥字段记原值(base_url 脱敏 userinfo)。"""
    if value is None:
        return None
    if field_name == "base_url":
        return _mask_userinfo(str(value))
    if field_name == "enabled":
        return "true" if int(value) == 1 else "false"
    return str(value)


def _normalize_patch(patch: Dict[str, Any]) -> Dict[str, Any]:
    """写入语义校验:空串 400;密钥长度 8-256;掩码/指纹形态 400(防把展示值写回库)。"""
    normalized: Dict[str, Any] = {}
    for field_name, value in patch.items():
        if field_name not in WRITABLE_FIELDS:
            continue
        if value is None:                       # 显式 null = 清除并回落 env
            normalized[field_name] = None
            continue
        if field_name == "api_key":
            text = str(value)
            if text == "":
                raise ApiException("密钥不能为空字符串；如需清除请传 null", code=400, status_code=400)
            if ai_crypto.looks_like_mask(text):
                raise ApiException("检测到提交的是掩码，请填写完整密钥", code=400, status_code=400)
            if not (MIN_API_KEY_LENGTH <= len(text) <= MAX_API_KEY_LENGTH):
                raise ApiException(
                    f"密钥长度需在 {MIN_API_KEY_LENGTH}-{MAX_API_KEY_LENGTH} 之间", code=400, status_code=400)
            normalized[field_name] = text
            continue
        if isinstance(value, str) and value == "":
            raise ApiException(f"字段 {field_name} 不能为空字符串；如需清除请传 null", code=400, status_code=400)
        normalized[field_name] = int(value) if field_name == "enabled" else value
    return normalized


def update_entry_config(db: Session, entry: str, patch: Dict[str, Any], admin: Dict[str, Any],
                        ip: Optional[str] = None) -> Dict[str, Any]:
    """部分更新某入口配置:省略=不修改/显式 null=清除回落 env;变更字段各写一行审计(同一事务)。

    返回该入口更新后的列表投影(与 GET list 单元素同形)。
    """
    assert_entry(entry)
    normalized = _normalize_patch(patch)

    row = db.execute(select(AiEntryConfig).where(AiEntryConfig.entry == entry)).scalar_one_or_none()
    if row is None:
        row = AiEntryConfig(entry=entry, enabled=1)
        db.add(row)

    admin_id = int(admin.get("sub") or 0)
    admin_username = str(admin.get("username") or "")
    changed = 0
    try:
        for field_name, value in normalized.items():
            if field_name == "api_key":
                changed += _apply_api_key(db, row, value, entry, admin_id, admin_username, ip)
                continue
            column = field_name
            old_value = getattr(row, column)
            if field_name == "enabled":
                old_value = None if old_value is None else int(old_value)
            if old_value == value:
                continue                        # 未变更 → 不写审计(避免噪音)
            setattr(row, column, value)
            changed += 1
            db.add(AdminAiConfigAudit(
                entry=entry, field=field_name, action="update" if value is not None else "clear",
                old_display=_display_value(field_name, old_value), new_display=_display_value(field_name, value),
                admin_id=admin_id, admin_username=admin_username, ip=ip))
        if changed:
            row.updated_by = admin_username or row.updated_by
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        invalidate_cache(entry)
    return _entry_view(db, entry)


def _apply_api_key(db: Session, row: AiEntryConfig, value: Optional[str], entry: str, admin_id: int,
                   admin_username: str, ip: Optional[str]) -> int:
    """api_key 字段的写入与审计(密文入库;审计只留掩码/长度/指纹)。返回变更字段数。"""
    old_ciphertext = row.api_key_ciphertext
    old_fingerprint = row.api_key_fingerprint
    if value is None:
        if not old_ciphertext and not old_fingerprint:
            return 0
        row.api_key_ciphertext = None
        row.api_key_fingerprint = None
        row.updated_by = admin_username or row.updated_by
        db.add(AdminAiConfigAudit(
            entry=entry, field="api_key", action="clear",
            old_display=_old_key_display(old_ciphertext), new_display=None,
            old_len=ai_crypto.plaintext_length_from_ciphertext(old_ciphertext), new_len=None,
            old_fp=old_fingerprint, new_fp=None,
            admin_id=admin_id, admin_username=admin_username, ip=ip))
        return 1
    if value == (old_fingerprint or ""):
        raise ApiException("检测到提交的是密钥指纹，请填写完整密钥", code=400, status_code=400)
    new_fingerprint = ai_crypto.fingerprint(value)
    if old_fingerprint and old_fingerprint == new_fingerprint:
        return 0                                # 同一把 key → 未变更,不写审计
    state = ai_crypto.enc_key_state()
    if state != ai_crypto.REASON_OK:
        raise ApiException("加密密钥未配置或非法，无法保存密钥", code=400, status_code=400)
    master = ai_crypto.load_enc_keys()[0]
    row.api_key_ciphertext = ai_crypto.encrypt_secret(value, master)
    row.api_key_fingerprint = new_fingerprint
    row.updated_by = admin_username or row.updated_by
    db.add(AdminAiConfigAudit(
        entry=entry, field="api_key", action="update",
        old_display=_old_key_display(old_ciphertext), new_display=ai_crypto.mask_secret(value),
        old_len=ai_crypto.plaintext_length_from_ciphertext(old_ciphertext), new_len=len(value),
        old_fp=old_fingerprint, new_fp=new_fingerprint,
        admin_id=admin_id, admin_username=admin_username, ip=ip))
    return 1


def _old_key_display(old_ciphertext: Optional[str]) -> Optional[str]:
    """旧密钥的展示掩码:能解密则用真实掩码,解不开回退 `****`(绝不回显密文或原文)。"""
    if not old_ciphertext:
        return None
    try:
        plaintext = ai_crypto.decrypt_secret(old_ciphertext, ai_crypto.load_enc_keys())
    except ai_crypto.SecretDecryptError:
        return "****"
    return ai_crypto.mask_secret(plaintext)
