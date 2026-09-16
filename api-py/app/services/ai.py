"""AI 三功能服务(对齐 backend ai-analysis/image-optimize/title-optimize)。"""
import json
import logging
import re
import threading
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ApiException
from app.services.ai_config import EntryConfig, resolve_config
from app.services.metric_labels import localized_summary, localized_title_input, time_range_label
from app.services.shop import get_summary as shop_get_summary

settings = get_settings()

logger = logging.getLogger("api")

# 上游「空响应」重试的预算下限(#PB-35):重试本身也是一次上游调用,剩余预算低于该值时不重试,
# 直接按原错误码返回(既不把 502 变成必然的 504,也不让用户白等)。
_EMPTY_RETRY_MIN_BUDGET_MS = 1000

# AI 并发信号量(第三方审查:防止并发 AI 请求耗尽线程池;满则 429)
_CONCURRENCY_DEFAULT = 10
_analysis_sem = threading.BoundedSemaphore(_CONCURRENCY_DEFAULT)
_img_sem = threading.BoundedSemaphore(max(1, int(settings.IMAGE_OPT_MAX_CONCURRENCY)))
_title_sem = threading.BoundedSemaphore(max(1, int(settings.TITLE_OPT_MAX_CONCURRENCY)))


def _monotonic() -> float:
    """单调时钟(经模块级间接层调用,测试可 monkeypatch 以精确控制总预算消耗)。"""
    return time.monotonic()


def _json_default(o):
    """JSON 序列化兜底:date/datetime -> ISO(与 NestJS/JS 一致),其他 -> str。"""
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    return str(o)

SYSTEM_PROMPT_ANALYSIS = ("你是一名专业的「拍拍二手」商家经营顾问。请基于商家提供的经营指标数据，输出结构化分析，"
                          "必须且只能返回 JSON 对象，格式：{summary, strengths:[{point,reason}], weaknesses:[{point,reason}], suggestions:[{action,priority}]}。"
                          # #PB-32 硬要求:键名固定英文结构,内容文本一律中文指标名(禁止回显英文字段名)
                          "JSON 的键名固定用上述英文结构；但内容文本一律使用中文指标名，"
                          "禁止出现英文字段名或下划线命名（如 health_score、trade_amount、avg_score、shop_star），"
                          "提到指标时用其中文名（如「商品信息健康分」「成交金额」「店铺平均信息分」「店铺星级」）。"
                          "建议必须可执行且按优先级排列(high 在前);所有结论必须引用商家数据;建议 3-5 条。")

# 标题优化系统提示(#PB-33):
# - 输出**键名**固定为 spuTitle/skuTitle/notes(响应契约,不得改);
# - 键以外的文本内容一律中文,**禁止出现英文字段名/camelCase 字段名**(如 keyAttrs、currentTitle、saleAttrs)。
SYSTEM_PROMPT_TITLE = ("你是二手商品标题优化专家，必须且只能输出 JSON 对象 {spuTitle, skuTitle, notes}。"
                       "输入的字段名已是中文；输出中一律使用中文，"
                       "禁止出现英文字段名或 camelCase 字段名（如 keyAttrs、currentTitle、saleAttrs、brand），"
                       "JSON 的键名固定用 spuTitle / skuTitle / notes（这三个是响应契约要求的键，不属于被禁示例）。")

_analysis_window: Dict[str, list] = {}
# 限流窗口的"清理-读取-判定-写回"是 read-modify-write:FastAPI 同步端点跑在线程池,
# 无锁时并发请求会互相覆盖计数(实测 32 并发放行 6 次,应放行 5 次),必须整段串行化。
# 边界:进程内锁只约束本进程;多 worker(uvicorn --workers N)窗口按进程隔离,
# 全局上限约 5×N(与修前边界一致);要全局精确需共享存储(Redis),属新增依赖,须上报确认。
_analysis_window_lock = threading.Lock()

def _analysis_rate_ok(ip: str) -> bool:
    now = time.time()
    with _analysis_window_lock:
        # 清理过期 key(保留最近 60s 窗口),避免 dict 无限增长(进程内存泄漏)
        for k in list(_analysis_window.keys()):
            if not _analysis_window[k] or (now - _analysis_window[k][-1]) > 60:
                _analysis_window.pop(k, None)
        hits = [t for t in _analysis_window.get(ip, []) if now - t < 60]
        if len(hits) >= 5:
            _analysis_window[ip] = hits
            return False
        hits.append(now)
        _analysis_window[ip] = hits
        return True

def _post_chat(cfg: EntryConfig, prompt_system: str, prompt_user: str, max_tokens: int, timeout_ms: int,
               content=None, extra_body: Optional[dict] = None) -> str:
    """调用 LLM(**三入口唯一出口**)。`cfg` 由 `ai_config.resolve_config` 解析(key/base_url/model 分入口可配),
    `max_tokens`/`timeout_ms` 由调用方按入口传入(取自同一 `cfg`,避免第二真源)。

    #PB-35:上游偶发返回空 content(`LLM_EMPTY_RESPONSE`)属**瞬时抖动**,只对这种情况**重试 1 次**,
    且**只能用剩余超时预算**(`timeout_ms` 是**总预算**:总调用 ≤ 2 次、总耗时 ≤ `timeout_ms`,
    剩余低于 `_EMPTY_RETRY_MIN_BUDGET_MS` 即不重试、按原错误码返回)。
    其余错误(`LLM_HTTP_429`/`LLM_TIMEOUT`/`LLM_NETWORK_ERROR`/`LLM_HTTP_5XX`/`LLM_PARSE_FAILED`)
    一律**不重试**——重试会放大上游压力或让用户等更久。日志只记次数与原因码,不记上游返回原文与任何密钥。"""
    if not cfg.api_key or not cfg.base_url:
        raise RuntimeError("AI_NOT_CONFIGURED")
    started = _monotonic()
    try:
        return _post_chat_once(cfg, prompt_system, prompt_user, max_tokens, timeout_ms, content, extra_body)
    except RuntimeError as e:
        if str(e) != "LLM_EMPTY_RESPONSE":
            raise
        remaining_ms = timeout_ms - (_monotonic() - started) * 1000.0
        if remaining_ms < _EMPTY_RETRY_MIN_BUDGET_MS:
            logger.warning(
                f"AI 上游空响应(LLM_EMPTY_RESPONSE): 剩余预算不足({remaining_ms:.0f}ms < {_EMPTY_RETRY_MIN_BUDGET_MS}ms),不重试")
            raise
        logger.warning(
            f"AI 上游空响应(LLM_EMPTY_RESPONSE): 用剩余预算重试 1 次(attempt=2, remaining_budget_ms={int(remaining_ms)})")
        return _post_chat_once(cfg, prompt_system, prompt_user, max_tokens, int(remaining_ms), content, extra_body)


def _post_chat_once(cfg: EntryConfig, prompt_system: str, prompt_user: str, max_tokens: int, timeout_ms: int,
                    content=None, extra_body: Optional[dict] = None) -> str:
    """**单次**上游调用(不重试;异常语义与既有实现逐字一致)。"""
    payload: Dict[str, Any] = {"model": cfg.model,
                               "messages": [{"role": "system", "content": prompt_system},
                                            {"role": "user", "content": content if content is not None else prompt_user}],
                               "max_tokens": max_tokens}
    if extra_body:
        payload.update(extra_body)
    url = cfg.base_url.rstrip("/") + "/chat/completions"
    try:
        resp = httpx.post(url, headers={"Content-Type": "application/json",
                                        "Authorization": f"Bearer {cfg.api_key}"},
                          json=payload, timeout=timeout_ms / 1000)
    except httpx.ConnectTimeout as e:
        # 连接阶段超时:与 NestJS 的 UND_ERR_CONNECT_TIMEOUT 同口径,归网络错误(502)
        raise RuntimeError("LLM_NETWORK_ERROR") from e
    except httpx.TimeoutException as e:
        # 请求阶段超时(httpx 到达 timeout_ms 后中断,对应 NestJS AbortController -> AbortError)-> LLM_TIMEOUT(504)
        raise RuntimeError("LLM_TIMEOUT") from e
    except Exception as e:
        raise RuntimeError("LLM_NETWORK_ERROR") from e
    if resp.status_code == 429:
        raise RuntimeError("LLM_HTTP_429")
    if resp.status_code >= 500:
        raise RuntimeError("LLM_HTTP_5XX")
    if not resp.is_success:
        raise RuntimeError(f"LLM_HTTP_{resp.status_code}")
    data = resp.json()
    c = data.get("choices", [{}])[0].get("message", {}).get("content")
    if not c:
        raise RuntimeError("LLM_EMPTY_RESPONSE")
    return c

def _parse_json(content: str) -> Any:
    cleaned = re.sub(r"^```(?:json)?[ \t]*", "", content.strip())
    cleaned = re.sub(r"```[ \t]*$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        s = cleaned.find("{")
        e = cleaned.rfind("}")
        if s == -1 or e <= s:
            raise RuntimeError("LLM_PARSE_FAILED")
        return json.loads(cleaned[s:e + 1])

def _log_insert(db: Session, merchant_id: str, log_type: str, status: str, err: Optional[str]) -> None:
    db.execute(text("INSERT INTO ai_analysis_log (merchant_id, type, status, error_message) VALUES (:m, :t, :s, :e)"),
               {"m": merchant_id, "t": log_type, "s": status, "e": err})
    db.commit()

def _count_today_success(db: Session, merchant_id: str, log_type: str) -> int:
    row = db.execute(text("SELECT COUNT(*) AS c FROM ai_analysis_log WHERE merchant_id=:m AND type=:t AND status='success' AND created_at >= CURDATE()"),
                     {"m": merchant_id, "t": log_type}).mappings().first()
    return int(row["c"] or 0)

def error_message_for_code(code: str) -> str:
    """错误码 → 用户可读文案(单一真源;管理端连通性自检也复用它)。"""
    if code == "AI_NOT_CONFIGURED":
        return "AI 服务未配置，请联系管理员"
    if code == "LLM_NETWORK_ERROR":
        return "网络连接失败，请检查网络后重试"
    if code == "LLM_HTTP_429":
        return "AI 服务繁忙，请稍后重试"
    if code == "LLM_TIMEOUT":
        return "AI 分析超时，请稍后重试"
    if code in ("LLM_EMPTY_RESPONSE", "LLM_PARSE_FAILED"):
        return "AI 分析结果异常，请稍后重试"
    return "AI 分析失败，请稍后重试"


def _raise_from_code(code: str) -> None:
    status = 429 if code == "LLM_HTTP_429" else (504 if code == "LLM_TIMEOUT" else 502)
    raise ApiException(error_message_for_code(code), code=status, status_code=status)


# 连通性自检的超时上界:管理端表单等待,不沿用业务入口的长超时
VERIFY_TIMEOUT_CEILING_MS = 15000


def verify_connection(cfg: EntryConfig) -> Dict[str, Any]:
    """用**当前生效配置**发一次最小请求验证连通性(供管理端 /verify 调用)。

    - `max_tokens=1`(P7 §5.1),超时取 `min(cfg.timeout_ms, 15000)` 以免管理端长时间等待;
    - 不落库、不返回密钥原文/密文/长度;仅返回 `ok/code/message`;
    - 不抛异常:由路由决定 HTTP 状态(失败按 502)。

    注:`max_tokens=1` 时部分供应商会返回空内容,此时 HTTP 已连通,连通性仍视为成功(不误报失败)。
    """
    try:
        _post_chat(cfg, "你是连通性自检助手。", "ping", 1,
                   timeout_ms=min(int(cfg.timeout_ms), VERIFY_TIMEOUT_CEILING_MS))
        return {"ok": True, "code": None, "message": "连接正常"}
    except RuntimeError as e:
        code = str(e)
        if code == "LLM_EMPTY_RESPONSE":
            return {"ok": True, "code": None, "message": "连接正常"}
        return {"ok": False, "code": code, "message": error_message_for_code(code)}

def _norm(v: str) -> str:
    m = {"P0": "重要", "P1": "一般", "P2": "可选", "HIGH": "重要", "MEDIUM": "一般", "LOW": "可选",
         "高": "重要", "中": "一般", "低": "可选", "重要": "重要", "一般": "一般", "可选": "可选"}
    return m.get(str(v or "").strip().upper(), "一般")

def analyze(db: Session, merchant_id: str, time_range: str, ip: Optional[str]) -> Dict[str, Any]:
    if not _analysis_rate_ok(ip or "unknown"):
        raise ApiException("操作过于频繁，请稍后再试", code=429, status_code=429)
    summary = shop_get_summary(db, merchant_id, time_range)
    has_data = any([summary.get("star"), summary.get("trade"), summary.get("traffic"),
                    summary.get("product"), summary.get("product_count"), summary.get("health_score")])
    if not has_data:
        return {"summary": None, "strengths": [], "weaknesses": [], "suggestions": [],
                "message": "暂无已上传的经营数据，请先完成数据上传"}
    cfg = resolve_config(db, "analysis")
    if cfg.daily_limit > 0 and _count_today_success(db, merchant_id, "analysis") >= cfg.daily_limit:
        raise ApiException("今日 AI 分析次数已用完，请明天再试", code=429, status_code=429)
    # #PB-32:送模型的指标数据**键必须中文化**——否则模型照着英文键作答,商家端会看到 health_score 这类字段名。
    # 结构/层级/值不变,只换键(名册与覆盖保证见 app/services/metric_labels.py);时间维度也用中文口径。
    prompt_user = ("时间维度：" + time_range_label(time_range)
                   + "\n商家经营指标（字段为 null 表示未上传）：\n"
                   + json.dumps(localized_summary(summary), ensure_ascii=False, indent=2, default=_json_default))
    if not _analysis_sem.acquire(blocking=False):
        raise ApiException("AI 请求繁忙，请稍后重试", code=429, status_code=429)
    try:
        raw = _post_chat(cfg, SYSTEM_PROMPT_ANALYSIS, prompt_user, cfg.max_tokens, timeout_ms=cfg.timeout_ms,
                         extra_body={"temperature": 0.7, "response_format": {"type": "json_object"}})
        parsed = _parse_json(raw)
        _log_insert(db, merchant_id, "analysis", "success", None)
        return {"summary": parsed.get("summary") if isinstance(parsed.get("summary"), str) else "",
                "strengths": parsed.get("strengths") if isinstance(parsed.get("strengths"), list) else [],
                "weaknesses": parsed.get("weaknesses") if isinstance(parsed.get("weaknesses"), list) else [],
                "suggestions": parsed.get("suggestions") if isinstance(parsed.get("suggestions"), list) else []}
    except RuntimeError as e:
        code = str(e)
        _log_insert(db, merchant_id, "analysis", "failed", "LLM_CALL_FAILED" if code.startswith("LLM_HTTP_") else code)
        _raise_from_code(code)
    finally:
        _analysis_sem.release()


IMAGE_OPT_SYSTEM_PROMPT = (
    "你是拍拍二手商品主图优化专家。请分析这张商品主图，输出合规核查、问题清单与优化后的构图/文案方案。"
    "必须且只能输出一个 JSON 对象；不要 markdown 代码块，不要任何说明文字；键名严格用英文。"
    'JSON 结构：{"summary":"图片现状简短总结","compliance":["合规核查结论1","合规核查结论2"],'
    '"issues":[{"item":"问题项","priority":"重要|一般|可选","suggestion":"改进建议"}],'
    '"plan":{"layout":"构图方案","copy":"文案方案","action_steps":["可执行步骤1","步骤2"]}}'
)


def _normalize_image_result(parsed) -> Dict[str, Any]:
    """规整主图优化结果:优先英文键,兼容中文键(合规核查/问题清单/优化后的构图/文案方案)。"""
    if not isinstance(parsed, dict):
        parsed = {}
    summary = parsed.get("summary") or parsed.get("总结") or ""
    compliance = parsed.get("compliance")
    if not isinstance(compliance, list):
        comp = parsed.get("合规核查")
        if isinstance(comp, list):
            compliance = [str(x) for x in comp]
        elif isinstance(comp, dict):
            compliance = [f"{k}：{v}" for k, v in comp.items()]
        else:
            compliance = []
    compliance = [x for x in compliance if isinstance(x, str) and x.strip()]

    issues = parsed.get("issues")
    if not isinstance(issues, list):
        ql = parsed.get("问题清单")
        if isinstance(ql, list):
            issues = [{"item": str(x), "priority": "一般", "suggestion": ""} for x in ql if str(x).strip()]
        else:
            issues = []
    norm_issues = []
    for it in issues:
        if isinstance(it, dict):
            item = it.get("item") or it.get("问题项") or ""
            pri = it.get("priority") or it.get("优先级") or "一般"
            sug = it.get("suggestion") or it.get("建议") or ""
            norm_issues.append({"item": str(item), "priority": _norm(pri), "suggestion": str(sug)})

    plan = parsed.get("plan")
    if not isinstance(plan, dict):
        plan = parsed.get("优化后的构图/文案方案") or {}
    layout = plan.get("layout") or plan.get("构图建议") or plan.get("构图方案") or ""
    copy = plan.get("copy") or plan.get("文案") or plan.get("文案排版方案") or ""
    steps = plan.get("action_steps")
    if not isinstance(steps, list):
        steps = plan.get("步骤") or []
    steps = [str(x) for x in steps if str(x).strip()]
    return {"summary": str(summary), "compliance": compliance, "issues": norm_issues,
            "plan": {"layout": str(layout), "copy": str(copy), "action_steps": steps}}


def optimize_image(db: Session, merchant_id: str, mime: str, data_url: str, size: int) -> Dict[str, Any]:
    if not mime:
        raise ApiException("请上传图片文件", code=400, status_code=400)
    if mime not in ("image/jpeg", "image/png", "image/webp"):
        raise ApiException("仅支持 JPG/PNG/WebP 格式图片", code=400, status_code=400)
    if size > 5 * 1024 * 1024:
        raise ApiException("图片过大，请上传 5MB 以内的图片", code=400, status_code=400)
    cfg = resolve_config(db, "image_optimize")
    if cfg.daily_limit > 0 and _count_today_success(db, merchant_id, "image_optimize") >= cfg.daily_limit:
        raise ApiException("今日 AI 主图优化次数已用完，请明天再试", code=429, status_code=429)
    content = [{"type": "text", "text": "请严格按系统要求的 JSON 结构输出（仅 JSON，不要代码块/说明文字，键名用英文）。"},
               {"type": "image_url", "image_url": {"url": data_url}}]
    if not _img_sem.acquire(blocking=False):
        raise ApiException("AI 请求繁忙，请稍后重试", code=429, status_code=429)
    try:
        raw = _post_chat(cfg, IMAGE_OPT_SYSTEM_PROMPT, "", cfg.max_tokens,
                         timeout_ms=cfg.timeout_ms, content=content,
                         extra_body={"response_format": {"type": "json_object"}})
        parsed = _parse_json(raw)
        _log_insert(db, merchant_id, "image_optimize", "success", None)
        return _normalize_image_result(parsed)
    except RuntimeError as e:
        code = str(e); _log_insert(db, merchant_id, "image_optimize", "failed", code); _raise_from_code(code)
    finally:
        _img_sem.release()

def optimize_title(db: Session, merchant_id: str, dto: Dict[str, Any]) -> Dict[str, Any]:
    mode = dto.get("mode")
    if mode == "generate" and not any((dto.get(k) or "").strip() for k in ("brand", "model", "condition", "features", "keyAttrs", "saleAttrs")):
        raise ApiException("请至少填写品牌、型号、产品特点、成色、关键属性或销售属性中的一项", code=400, status_code=400)
    if mode == "optimize" and not (dto.get("currentTitle") or "").strip():
        raise ApiException("请提供现有标题", code=400, status_code=400)
    cfg = resolve_config(db, "title_optimize")
    if cfg.daily_limit > 0 and _count_today_success(db, merchant_id, "title_optimize") >= cfg.daily_limit:
        raise ApiException("今日 AI 标题优化次数已用完，请明天再试", code=429, status_code=429)
    if not _title_sem.acquire(blocking=False):
        raise ApiException("AI 请求繁忙，请稍后重试", code=429, status_code=429)
    try:
        # #PB-33:入参键中文化(只换键、结构与值不变);系统提示同时禁止英文字段名/camelCase 键。
        raw = _post_chat(cfg, SYSTEM_PROMPT_TITLE,
                         json.dumps(localized_title_input(dto), ensure_ascii=False),
                         cfg.max_tokens, timeout_ms=cfg.timeout_ms)
        parsed = _parse_json(raw)
        _log_insert(db, merchant_id, "title_optimize", "success", None)
        return {"spuTitle": (parsed.get("spuTitle") or parsed.get("title") or "").strip(),
                "skuTitle": (parsed.get("skuTitle") or "").strip() or None,
                "notes": (parsed.get("notes") or "").strip()}
    except RuntimeError as e:
        code = str(e); _log_insert(db, merchant_id, "title_optimize", "failed", code); _raise_from_code(code)
    finally:
        _title_sem.release()

