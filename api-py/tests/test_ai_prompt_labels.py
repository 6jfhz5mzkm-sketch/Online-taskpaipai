"""AI 经营分析中文指标名册回归(#PB-32)。

背景:用户反馈「AI 经营分析出来的内容里面有英文字段名(如 health_score)」——根因是 `analyze()` 把
`get_summary` 的英文键原样 JSON 化塞进 user prompt,模型照英文键作答。本用例给出**不依赖外部模型**的
确定性证据:① 名册覆盖 `get_summary` 的全部键(含嵌套区段键)且无差集;② 实际送模型的 user/system
prompt 里**不出现任何 snake_case 键**;③ 名册用词与前端 `SHOP_METRIC_LABELS` 逐项一致。

隔离:临时商家 + 六张 shop_* 表造数,收尾复用 `tests/conftest.py` 的 `cleanup_temp_merchant`;
`ai_analysis_log` 行由本用例**先记 id 再按 id 删除**(conftest 助手不覆盖该表,铁律 5)。**全程打桩,零外呼。**
"""
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set

import pytest
from sqlalchemy import text

from app.services import ai
from app.services.metric_labels import (
    ALL_LABELS,
    GENERIC_LABELS,
    METRIC_LABELS,
    SECTION_LABELS,
    TIME_RANGE_LABELS,
    TITLE_FIELD_LABELS,
    localized_summary,
    localized_title_input,
    time_range_label,
)
from app.services.shop import get_summary

from tests.conftest import cleanup_temp_merchant, make_temp_merchant

# 形如 health_score / trade_amount 的英文字段名(下划线命名);值(日期/数字/7d)不会命中
SNAKE_CASE = re.compile(r"\b[a-z][a-z0-9]*_[a-z0-9_]+\b")

FRONTEND_CONSTANTS = Path(__file__).resolve().parents[2] / "project" / "src" / "constants" / "stage2.ts"


def _seed_full_summary(session, merchant_id: str) -> None:
    """六张 shop_* 表各造一行(只填必填列),使 get_summary 的 6 个区段全部非 null。"""
    session.execute(text("INSERT INTO shop_star_data (merchant_id, data_date, shop_star) VALUES (:m, '2026-09-01', 4.5)"), {"m": merchant_id})
    session.execute(text("INSERT INTO shop_trade_data (merchant_id, data_date, time_range, trade_amount) VALUES (:m, '2026-09-01', '7d', 1000.50)"), {"m": merchant_id})
    session.execute(text("INSERT INTO shop_traffic_data (merchant_id, data_date, time_range, uv_value) VALUES (:m, '2026-09-01', '7d', 12.3)"), {"m": merchant_id})
    session.execute(text("INSERT INTO shop_product_data (merchant_id, data_date, time_range, active_spu_count) VALUES (:m, '2026-09-01', '7d', 9)"), {"m": merchant_id})
    session.execute(text("INSERT INTO shop_product_count (merchant_id, data_date, total_count) VALUES (:m, '2026-09-01', 80)"), {"m": merchant_id})
    session.execute(text("INSERT INTO shop_health_score (merchant_id, data_date, avg_score) VALUES (:m, '2026-09-01', 95.5)"), {"m": merchant_id})
    session.commit()


def _all_keys(payload: Dict[str, Any]) -> Set[str]:
    """汇总数据里出现的全部键(顶层 + 嵌套区段),用于与名册比对。"""
    keys: Set[str] = set()
    for key, value in payload.items():
        keys.add(key)
        if isinstance(value, dict):
            keys.update(value.keys())
    return keys


def _drop_analysis_log(session, merchant_id: str) -> List[int]:
    """先按 merchant_id 取到本次创建的 ai_analysis_log 主键并记录,再按 id 删除(铁律 5)。"""
    ids = [int(r[0]) for r in session.execute(
        text("SELECT id FROM ai_analysis_log WHERE merchant_id = :m ORDER BY id"), {"m": merchant_id}).all()]
    if ids:
        session.execute(text("DELETE FROM ai_analysis_log WHERE id IN :ids").bindparams(
            __import__("sqlalchemy").bindparam("ids", expanding=True)), {"ids": ids})
        session.commit()
    print(f"[#PB-32 清理] ai_analysis_log 按 id 删除 {len(ids)} 行: {ids}")
    return ids


def test_registry_covers_every_summary_key(session):
    """名册必须覆盖 get_summary 实际返回的全部键(顶层 + 各区段内部),差集为空。"""
    merchant_id = make_temp_merchant(session)
    try:
        _seed_full_summary(session, merchant_id)
        summary = get_summary(session, merchant_id, "7d")
        assert all(summary[k] is not None for k in ("star", "trade", "traffic", "product", "product_count", "health_score"))

        actual = _all_keys(summary)
        covered = set(ALL_LABELS)
        print("[#PB-32] get_summary 实际键 =", sorted(actual))
        print("[#PB-32] 名册覆盖键     =", sorted(covered))
        print("[#PB-32] 未覆盖(差集)   =", sorted(actual - covered))
        print("[#PB-32] 名册多余       =", sorted(covered - actual))
        assert actual - covered == set(), "名册漏登记:" + str(sorted(actual - covered))
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_localized_summary_renames_keys_only_and_keeps_values(session):
    """中文化只换键:结构/层级/值逐项不变,且结果里不出现任何 snake_case 键。"""
    merchant_id = make_temp_merchant(session)
    try:
        _seed_full_summary(session, merchant_id)
        summary = get_summary(session, merchant_id, "7d")
        localized = localized_summary(summary)

        assert set(localized) == {label if label else key for key, label in
                                  [(k, ALL_LABELS[k]) for k in summary]}
        assert localized[SECTION_LABELS["health_score"]][METRIC_LABELS["avg_score"]] == summary["health_score"]["avg_score"]
        assert localized[SECTION_LABELS["star"]][METRIC_LABELS["shop_star"]] == summary["star"]["shop_star"]
        assert localized[SECTION_LABELS["trade"]][GENERIC_LABELS["data_date"]] == summary["trade"]["data_date"]
        assert localized[GENERIC_LABELS["time_range"]] == summary["time_range"]

        # get_summary 返回的是 ORM 原始值(含 date),与 analyze() 一致用 default=str 序列化
        dumped = json.dumps(localized, ensure_ascii=False, default=str)
        print("[#PB-32] 中文化后的汇总(片段) =", dumped[:400])
        assert SNAKE_CASE.findall(dumped) == [], "仍有英文字段名:" + str(SNAKE_CASE.findall(dumped))
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_analysis_prompts_contain_no_english_field_names(session, monkeypatch):
    """真实调用链(打桩 _post_chat)捕获的 system/user prompt:**零 snake_case**,且是中文指标名。"""
    merchant_id = make_temp_merchant(session)
    captured: List[Dict[str, str]] = []

    def fake_post_chat(cfg, prompt_system, prompt_user, max_tokens, timeout_ms, **kwargs):
        captured.append({"system": prompt_system, "user": prompt_user})
        return '{"summary":"经营平稳","strengths":[{"point":"客单价高","reason":"客单价高于同层"}],"weaknesses":[{"point":"转化偏低","reason":"加购转化率偏低"}],"suggestions":[{"action":"优化主图","priority":"high"}]}'

    monkeypatch.setattr(ai, "_post_chat", fake_post_chat)
    try:
        _seed_full_summary(session, merchant_id)
        result = ai.analyze(session, merchant_id, "7d", "127.0.0.1")
        assert result["summary"] == "经营平稳"
        assert len(captured) == 1

        system_prompt, user_prompt = captured[0]["system"], captured[0]["user"]
        print("[#PB-32] ===== SYSTEM PROMPT 原文 =====")
        print(system_prompt)
        print("[#PB-32] ===== USER PROMPT 原文 =====")
        print(user_prompt)
        print("[#PB-32] user prompt snake_case 命中 =", SNAKE_CASE.findall(user_prompt))
        print("[#PB-32] system prompt snake_case 命中 =", SNAKE_CASE.findall(system_prompt))

        assert SNAKE_CASE.findall(user_prompt) == []
        assert "商品信息健康分" in user_prompt and "成交金额" in user_prompt
        assert "时间维度：近7天" in user_prompt
        # system prompt 里出现的英文键只能是「被禁止的示例」(明确点名不得使用)
        assert "禁止出现英文字段名" in system_prompt
        assert "health_score" in system_prompt
    finally:
        _drop_analysis_log(session, merchant_id)
        cleanup_temp_merchant(session, merchant_id)


def test_time_range_label_matches_frontend_wording():
    """时间维度文案对齐前端 SHOP_SUMMARY_TIME_RANGES;未知取值原样返回(不吞)。"""
    assert time_range_label("yesterday") == "昨天"
    assert time_range_label("7d") == "近7天"
    assert time_range_label("30d") == "近30天"
    assert time_range_label("abc") == "abc"
    assert set(TIME_RANGE_LABELS) == {"yesterday", "7d", "30d"}


def _frontend_block(source: str, marker: str) -> str:
    start = source.index(marker)
    end = source.index("};", start)
    return source[start:end]


def test_metric_labels_match_frontend_registry():
    """后端名册用词与前端 SHOP_METRIC_LABELS 逐项一致(前端为只读参考,本单不改前端)。"""
    if not FRONTEND_CONSTANTS.exists():
        pytest.skip("跨仓校验:未找到 project/src/constants/stage2.ts(仅在本仓库根下有意义)")
    source = FRONTEND_CONSTANTS.read_text(encoding="utf-8")
    block = _frontend_block(source, "export const SHOP_METRIC_LABELS")
    frontend = dict(re.findall(r"^\s*([a-z0-9_]+):\s*'([^']*)',", block, flags=re.M))
    backend = {**GENERIC_LABELS, **METRIC_LABELS}

    print("[#PB-32] 前端名册键数 =", len(frontend), " 后端名册键数 =", len(backend))
    print("[#PB-32] 仅前端有 =", sorted(set(frontend) - set(backend)))
    print("[#PB-32] 仅后端有 =", sorted(set(backend) - set(frontend)))
    print("[#PB-32] 用词不一致 =",
          sorted(k for k in set(frontend) & set(backend) if frontend[k] != backend[k]))
    assert set(frontend) == set(backend)
    assert all(frontend[k] == backend[k] for k in frontend)

    # 区段名与前端 SHOP_SUMMARY_TYPES **逐项字面一致**(#PB-33 用户裁决:health_score 统一取「商品信息健康分」)
    types_block = _frontend_block(source, "export const SHOP_SUMMARY_TYPES")
    titles = dict(re.findall(r"\{ key: '([a-z_]+)', title: '([^']*)'", types_block))
    print("[#PB-33] 前端区段标题 =", titles)
    for key, label in SECTION_LABELS.items():
        assert titles.get(key) == label, (key, titles.get(key), label)

# ---- 标题优化同类治理(#PB-33):入参键中文化 + 系统提示禁止 camelCase 字段名 ----

# camelCase 字段名(如 keyAttrs / currentTitle / saleAttrs);中文与纯小写取值不会命中。
# 注意:该正则对**取值**里的品牌/型号名(如 iPhone)会误报,故断言以「键位置」为准:
#   ① 名册里 9 个 camelCase 字段名不得出现在 prompt 任何位置(最严,零误报);
#   ② JSON 键位置正则 `"key":` 命中必须为 0。
CAMEL_CASE = re.compile(r"\b[a-z]+[A-Z][A-Za-z0-9]*\b")
JSON_KEY_CAMEL = re.compile(r"\"([a-z]+[A-Z][A-Za-z0-9]*)\"\s*:")
JSON_KEY_SNAKE = re.compile(r"\"([a-z][a-z0-9]*_[a-z0-9_]+)\"\s*:")


def test_title_field_labels_cover_title_opt_body():
    """标题优化名册必须覆盖 `TitleOptBody` 的全部 camelCase 字段(差集为空)。"""
    from app.api.v1.shop import TitleOptBody

    fields = set(TitleOptBody.model_fields)
    covered = set(TITLE_FIELD_LABELS)
    print("[#PB-33] TitleOptBody 实际字段 =", sorted(fields))
    print("[#PB-33] 名册覆盖            =", sorted(covered))
    print("[#PB-33] 未覆盖(差集)        =", sorted(fields - covered))
    print("[#PB-33] 名册多余            =", sorted(covered - fields))
    assert fields - covered == set(), "标题优化名册漏登记:" + str(sorted(fields - covered))
    assert covered - fields == set(), "标题优化名册多余:" + str(sorted(covered - fields))


def test_localized_title_input_renames_keys_only():
    """只换键:取值与顺序不变,`null` 语义不变,结果不含任何 camelCase 键。"""
    dto = {"mode": "generate", "category": "二手手机", "brand": "苹果", "model": "iPhone 15",
           "features": "全网通5G", "condition": "95新", "keyAttrs": "256G", "saleAttrs": "官方标配",
           "currentTitle": None}
    out = localized_title_input(dto)
    assert list(out.keys()) == list(TITLE_FIELD_LABELS.values())
    assert list(out.values()) == list(dto.values())            # 值不变、顺序不变
    assert out["现有标题"] is None                               # null 语义不变
    dumped = json.dumps(out, ensure_ascii=False)
    assert [k for k in out if CAMEL_CASE.search(k)] == []
    assert [k for k in TITLE_FIELD_LABELS if k in dumped] == []   # 9 个 camelCase 字段名不得出现


def test_title_optimize_prompts_contain_no_camel_case(session, monkeypatch):
    """真实调用链(打桩 `_post_chat`)捕获标题优化 prompt:user 侧 camelCase 命中 = 0。"""
    merchant_id = make_temp_merchant(session)
    captured: List[Dict[str, str]] = []

    def fake_post_chat(cfg, prompt_system, prompt_user, max_tokens, timeout_ms, **kwargs):
        captured.append({"system": prompt_system, "user": prompt_user})
        return '{"spuTitle":"二手 苹果 iPhone 15 256G 95新","skuTitle":"苹果 iPhone 15 256G","notes":"突出容量与成色"}'

    monkeypatch.setattr(ai, "_post_chat", fake_post_chat)
    dto = {"mode": "generate", "category": "二手手机", "brand": "苹果", "model": "iPhone 15",
           "features": "全网通5G、大容量电池", "condition": "95新", "keyAttrs": "256G、深空黑",
           "saleAttrs": "官方标配", "currentTitle": ""}
    try:
        result = ai.optimize_title(session, merchant_id, dto)
        assert set(result) == {"spuTitle", "skuTitle", "notes"}     # 响应结构不变
        assert result["spuTitle"].startswith("二手")

        system_prompt, user_prompt = captured[0]["system"], captured[0]["user"]
        print("[#PB-33] ===== 标题优化 SYSTEM PROMPT 原文 =====")
        print(system_prompt)
        print("[#PB-33] ===== 标题优化 USER PROMPT 原文 =====")
        print(user_prompt)
        print("[#PB-33] user prompt 中出现的 camelCase 字段名 =",
              [k for k in TITLE_FIELD_LABELS if k in user_prompt])
        print("[#PB-33] user prompt JSON 键位置 camelCase 命中 =", JSON_KEY_CAMEL.findall(user_prompt))
        print("[#PB-33] user prompt JSON 键位置 snake_case 命中 =", JSON_KEY_SNAKE.findall(user_prompt))
        print("[#PB-33] user prompt 宽正则 camelCase 命中(含取值品牌名,仅供参考) =", CAMEL_CASE.findall(user_prompt))
        print("[#PB-33] system prompt camelCase 命中(应仅是被禁示例) =", CAMEL_CASE.findall(system_prompt))

        assert [k for k in TITLE_FIELD_LABELS if k in user_prompt] == []
        assert JSON_KEY_CAMEL.findall(user_prompt) == []
        assert JSON_KEY_SNAKE.findall(user_prompt) == []
        assert "现有标题" in user_prompt and "关键属性" in user_prompt and "销售属性" in user_prompt
        # system prompt 的命中必须都是「被禁止的示例」(明确点名不得使用)
        assert "禁止出现英文字段名或 camelCase 字段名" in system_prompt
        for forbidden_example in ("keyAttrs", "currentTitle", "saleAttrs"):
            assert forbidden_example in system_prompt
    finally:
        _drop_analysis_log(session, merchant_id)
        cleanup_temp_merchant(session, merchant_id)

