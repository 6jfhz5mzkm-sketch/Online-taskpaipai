"""指标/字段中文名册(#PB-32 经营分析 · #PB-33 标题优化):把送模型的英文字段名映射为中文名。

用途:AI 分析/标题优化把数据 JSON 化塞进 user prompt 时,**键必须是中文**(否则模型照着英文键作答,
商家端就会出现 `health_score` / `trade_amount` / `keyAttrs` 这类英文字段名)。

用词来源(**只读参考,不反向改前端**):
- 指标名:前端名册 `project/src/constants/stage2.ts::SHOP_METRIC_LABELS`(44 键),本模块逐字对齐;
- 区段名:前端 `SHOP_SUMMARY_TYPES` 的 title;**`health_score` 统一取「商品信息健康分」**
  (#PB-33 用户 2026-09-15 裁决「前端看板那个区块标题是「商品信息健康分」，叫这个」;此前 #PB-32 暂用「健康评分」已废);
- 时间维度文案:对齐前端 `SHOP_SUMMARY_TIME_RANGES`(昨天 / 近7天 / 近30天);
- 标题优化字段名:前端标题优化面板的可见字段标签(品牌 / 型号 / 产品特点 / 成色 / 关键属性 / 销售属性 / 现有标题),
  见 `project/src/components-local/stage2/TitleOptimizePanel.vue`。

边界:本模块只做「键 -> 中文名」映射,不改任何值、不改响应结构;未登记的键原样返回,
由 `tests/test_ai_prompt_labels.py` 保证 `get_summary` 与 `TitleOptBody` 的键集合被完全覆盖。
"""
from typing import Any, Dict, Optional

# 顶层区段键 -> 中文区段名(get_summary 的 6 个数据区段)
SECTION_LABELS: Dict[str, str] = {
    "star": "店铺星级",
    "trade": "交易数据",
    "traffic": "流量数据",
    "product": "商品数据",
    "product_count": "商品数量",
    # #PB-33:与前端 SHOP_SUMMARY_TYPES 的该区段 title 字面一致(不再用 #PB-32 暂定的「健康评分」)
    "health_score": "商品信息健康分",
}

# 通用键(出现在汇总根与各数据区段内)
GENERIC_LABELS: Dict[str, str] = {
    "data_date": "数据日期",
    "time_range": "时间范围",
}

# 指标键 -> 中文指标名(逐字对齐前端 SHOP_METRIC_LABELS,顺序按 shop_* 表分组)
METRIC_LABELS: Dict[str, str] = {
    # 星级(shop_star_data)
    "shop_star": "店铺星级",
    "service_score": "客服咨询因子",
    "logistics_score": "物流履约因子",
    "after_sale_score": "售后服务因子",
    "product_score": "商品体验因子",
    # 交易(shop_trade_data)
    "trade_amount": "成交金额",
    "trade_orders": "成交单量",
    "trade_customers": "成交客户数",
    "shop_visitors": "店铺访客数",
    "shop_page_views": "店铺浏览量",
    "trade_items": "成交商品件数",
    "conversion_rate": "成交转化率",
    "customer_unit_price": "客单价",
    "avg_stay_duration": "平均停留时长",
    "cart_customers": "加购客户数",
    "cart_items": "加购商品件数",
    "cart_conversion_rate": "加购转化率",
    # 流量(shop_traffic_data)
    "product_visitors": "商品访客数",
    "product_page_views": "商品浏览量",
    "product_avg_page_views": "商品人均浏览量",
    "product_avg_stay_duration": "商品平均停留时长",
    "uv_value": "UV价值",
    "product_exposure_count": "商品曝光次数",
    "product_exposure_users": "商品曝光人数",
    "cart_amount": "加购金额",
    "trade_conversion_rate": "成交转化率",
    # 商品(shop_product_data)
    "active_spu_count": "动销SPU数",
    "spu_active_rate": "SPU动销率",
    "item_unit_price": "件单价",
    "cart_spu_count": "加购SPU数",
    "spu_cart_rate": "SPU加购率",
    "visit_spu_count": "访问SPU数",
    "listed_spu_count": "上架SPU数",
    # 商品数量(shop_product_count)
    "total_count": "全部商品数量",
    "on_sale_count": "售卖中商品数量",
    "off_sale_count": "已下架商品数量",
    "audit_count": "商品审核中数量",
    # 健康分(shop_health_score)
    "avg_score": "店铺平均信息分",
    "score_gte_90_count": "信息分≥90 商品数",
    "score_78_90_count": "信息分 78-90 商品数",
    "score_60_77_count": "信息分 60-77 商品数",
    "score_lt_60_count": "信息分 <60 商品数",
}

# 时间维度键 -> 中文口径(对齐前端 SHOP_SUMMARY_TIME_RANGES)
TIME_RANGE_LABELS: Dict[str, str] = {
    "yesterday": "昨天",
    "7d": "近7天",
    "30d": "近30天",
}

# 标题优化入参字段名 -> 中文名(#PB-33;键 = `app/api/v1/shop.py::TitleOptBody` 的 camelCase 字段,
# 与用例 `test_ai_prompt_labels.py` 的穷尽枚举断言绑定)
# 用词对齐前端标题优化面板的可见字段标签(`TitleOptimizePanel.vue`:品牌/型号/产品特点/成色/关键属性/销售属性/现有标题);
# `mode`/`category` 前端无同名标签,由后端定名(模式 / 类目)。
TITLE_FIELD_LABELS: Dict[str, str] = {
    "mode": "模式",
    "category": "类目",
    "brand": "品牌",
    "model": "型号",
    "features": "产品特点",
    "condition": "成色",
    "keyAttrs": "关键属性",
    "saleAttrs": "销售属性",
    "currentTitle": "现有标题",
}

ALL_LABELS: Dict[str, str] = {**SECTION_LABELS, **GENERIC_LABELS, **METRIC_LABELS}


def label_for(key: str) -> str:
    """键 -> 中文名;未登记的键原样返回(不得静默丢字段)。"""
    return ALL_LABELS.get(key, key)


def time_range_label(time_range: Optional[str]) -> str:
    """`time_range` 取值 -> 中文口径;未登记取值原样返回。"""
    return TIME_RANGE_LABELS.get(time_range or "", time_range or "")


def localized_title_input(dto: Dict[str, Any]) -> Dict[str, Any]:
    """把标题优化的入参 dto 的**键**换成中文(结构与值不变),供 AI prompt 使用。

    与 `localized_summary` 同模式:只换键;未登记键原样返回(由用例保证不漏)。
    """
    return {TITLE_FIELD_LABELS.get(k, k): v for k, v in dto.items()}


def localized_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    """把汇总数据的**键**换成中文标签(层级与值不变),供 AI prompt 使用。

    只处理「键」:数值/字符串/None 原样透传;嵌套 dict(数据区段)递归一层后同样只换键。
    """
    out: Dict[str, Any] = {}
    for key, value in summary.items():
        if isinstance(value, dict):
            out[label_for(key)] = {label_for(k): v for k, v in value.items()}
        else:
            out[label_for(key)] = value
    return out
