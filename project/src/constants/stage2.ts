/**
 * 阶段二（开店搭建）常量
 * @description 对齐 R2《阶段隔离规则与阶段二任务清单》§1.2 命名规范：
 *              阶段二大阶段标识 = shop_setup；4 个一级任务各自独立 stage_id：
 *              brand / listing / optimize / activity；禁止使用 setup。
 *              T2.5 店铺数据上传（shopdata）已剥离至数据分析专区（数据分析专区方案 v2.0），
 *              不再计入阶段二导航与进度，由 DATA_CENTER_STAGE_ID 单独管理。
 */

/** 阶段二解锁后 merchant.current_stage 约定值 */
export const STAGE2_UNLOCK_STAGE_ID = 'shop_setup';

/** 阶段一 stage_id（入驻准备，与后端 PHASE1_STAGE_IDS 对齐） */
export const PHASE1_STAGE_IDS = ['onboarding', 'application', 'review', 'opening'] as const;

/** 阶段二 stage_id（开店搭建，与后端 PHASE2_STAGE_IDS 对齐；不含 shopdata） */
export const PHASE2_STAGE_IDS = ['brand', 'listing', 'optimize', 'activity'] as const;

/** 数据分析专区（数据上传/数据看板）stage_id（原阶段二 T2.5 店铺数据上传，独立记录） */
export const DATA_CENTER_STAGE_ID = 'shopdata';

/** 表单字段配置（T2.5.1 / T2.5.5 / T2.5.6；字段为 UI 展示配置，任务数据仍来自后端） */
export interface Stage2FormField {
  key: string;
  label: string;
  required?: boolean;
  /**
   * 留空时是否以 0 提交（#F-29，用户口径「5 个字段全留空视为全是 0」）。
   * 仅商品信息健康分（表单 key = health-score）启用：空值必须显式发 0（不是 null、不是省略），
   * 后端语义「全 0 = 该商家本次无该项数据」；其它表单一律保持「留空即不提交该字段」。
   */
  emptyAsZero?: boolean;
  placeholder?: string;
  min?: number;
  max?: number;
  integer?: boolean;
}

/** 表单字段 schema（key 与后端 DTO 字段对齐） */
export const STAGE2_FORM_SCHEMAS: Record<string, Stage2FormField[]> = {
  star: [
    { key: 'shopStar', label: '店铺星级（1-5）', required: true, min: 1, max: 5, placeholder: '如 4.5' },
    { key: 'serviceScore', label: '客服咨询因子得分（5.5-10）', min: 0, max: 10, placeholder: '如 9.1' },
    { key: 'logisticsScore', label: '物流履约因子得分（5.5-10）', min: 0, max: 10, placeholder: '如 8.8' },
    { key: 'afterSaleScore', label: '售后服务因子得分（5.5-10）', min: 0, max: 10, placeholder: '如 8.6' },
    { key: 'productScore', label: '商品体验因子得分（5.5-10）', min: 0, max: 10, placeholder: '如 9.0' },
  ],
  'product-count': [
    { key: 'totalCount', label: '全部商品数量', required: true, min: 0, integer: true, placeholder: '如 120' },
    { key: 'onSaleCount', label: '售卖中商品数量', min: 0, integer: true, placeholder: '如 80' },
    { key: 'offSaleCount', label: '已下架商品数量', min: 0, integer: true, placeholder: '如 30' },
    { key: 'auditCount', label: '商品审核中数量', min: 0, integer: true, placeholder: '如 10' },
  ],
  /* 商品信息健康分（T2.5.6）：5 个字段全部非必填（#F-29，用户口径「全留空 = 全 0」）；
     留空值由 emptyAsZero 统一以 0 提交，范围约束（0-100 / 非负整数）保持不变 */
  'health-score': [
    { key: 'avgScore', label: '店铺平均信息分（0-100）', min: 0, max: 100, emptyAsZero: true, placeholder: '如 85' },
    { key: 'scoreGte90Count', label: '信息分≥90 商品数量', min: 0, integer: true, emptyAsZero: true, placeholder: '如 20' },
    { key: 'score78_90Count', label: '信息分 78-90 商品数量', min: 0, integer: true, emptyAsZero: true, placeholder: '如 40' },
    { key: 'score60_77Count', label: '信息分 60-77 商品数量', min: 0, integer: true, emptyAsZero: true, placeholder: '如 30' },
    { key: 'scoreLt60Count', label: '信息分 <60 商品数量', min: 0, integer: true, emptyAsZero: true, placeholder: '如 10' },
  ],
};

/** 数据看板时间维度（对应 GET /api/shop/summary 的 time_range 取值） */
export const SHOP_SUMMARY_TIME_RANGES: Array<{ key: 'yesterday' | '7d' | '30d'; label: string }> = [
  { key: 'yesterday', label: '昨天' },
  { key: '7d', label: '近7天' },
  { key: '30d', label: '近30天' },
];

/** 数据看板展示类型（对应 shop_* 表/T2.5 任务） */
export const SHOP_SUMMARY_TYPES: Array<{ key: string; title: string; desc: string }> = [
  { key: 'star', title: '店铺星级', desc: 'T2.5.1' },
  { key: 'trade', title: '交易数据', desc: 'T2.5.2' },
  { key: 'traffic', title: '流量数据', desc: 'T2.5.3' },
  { key: 'product', title: '商品数据', desc: 'T2.5.4' },
  { key: 'product_count', title: '商品数量', desc: 'T2.5.5' },
  { key: 'health_score', title: '商品信息健康分', desc: 'T2.5.6' },
];

/* ---------- Excel 导入结果展示文案（#PB-24-3；唯一真源，禁止在组件里另写字面量） ---------- */

/** 汇总行标签：共 N 行 / 写入 X 行 / 跳过 Y 行 / 修正 Z 行（数值取后端 total_rows/count/skipped/normalized） */
export const EXCEL_RESULT_SUMMARY_LABELS = {
  total: '共',
  written: '写入',
  skipped: '跳过',
  normalized: '修正',
} as const;

/** 汇总行单位与分隔符（与上述标签组合成一行） */
export const EXCEL_RESULT_ROW_UNIT = '行';
export const EXCEL_RESULT_SEPARATOR = ' / ';

/** 问题清单截断提示（后端 issues_truncated=true；上界 200 条由后端契约固定，见 #PB-24-2） */
export const EXCEL_ISSUES_TRUNCATED_TEXT = '仅显示前 200 条问题，完整记录见服务端日志';

/** 问题条目行模板：{row}=Excel 物理行号（表头=1）/ {field}=字段中文名或库列名 / {message}=后端 message */
export const EXCEL_ISSUE_LINE_TEMPLATE = '第 {row} 行 · {field} · {message}';

/** 指标字段中文标签（与 shop_* 实体字段对齐；未收录字段回退显示原始 key） */
export const SHOP_METRIC_LABELS: Record<string, string> = {
  // 通用
  data_date: '数据日期',
  time_range: '时间范围',
  // 星级（shop_star_data）
  shop_star: '店铺星级',
  service_score: '客服咨询因子',
  logistics_score: '物流履约因子',
  after_sale_score: '售后服务因子',
  product_score: '商品体验因子',
  // 交易（shop_trade_data）
  trade_amount: '成交金额',
  trade_orders: '成交单量',
  trade_customers: '成交客户数',
  shop_visitors: '店铺访客数',
  shop_page_views: '店铺浏览量',
  trade_items: '成交商品件数',
  conversion_rate: '成交转化率',
  customer_unit_price: '客单价',
  avg_stay_duration: '平均停留时长',
  cart_customers: '加购客户数',
  cart_items: '加购商品件数',
  cart_conversion_rate: '加购转化率',
  // 流量（shop_traffic_data）
  product_visitors: '商品访客数',
  product_page_views: '商品浏览量',
  product_avg_page_views: '商品人均浏览量',
  product_avg_stay_duration: '商品平均停留时长',
  uv_value: 'UV价值',
  product_exposure_count: '商品曝光次数',
  product_exposure_users: '商品曝光人数',
  cart_amount: '加购金额',
  trade_conversion_rate: '成交转化率',
  // 商品（shop_product_data）
  active_spu_count: '动销SPU数',
  spu_active_rate: 'SPU动销率',
  item_unit_price: '件单价',
  cart_spu_count: '加购SPU数',
  spu_cart_rate: 'SPU加购率',
  visit_spu_count: '访问SPU数',
  listed_spu_count: '上架SPU数',
  // 商品数量（shop_product_count）
  total_count: '全部商品数量',
  on_sale_count: '售卖中商品数量',
  off_sale_count: '已下架商品数量',
  audit_count: '商品审核中数量',
  // 健康分（shop_health_score）
  avg_score: '店铺平均信息分',
  score_gte_90_count: '信息分≥90 商品数',
  score_78_90_count: '信息分 78-90 商品数',
  score_60_77_count: '信息分 60-77 商品数',
  score_lt_60_count: '信息分 <60 商品数',
};
