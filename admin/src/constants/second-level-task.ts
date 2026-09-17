/**
 * 二级任务「行为类型 / 行为参数」文案与选项（#AF-20）
 *
 * 契约真源：project/docs/后端技术方案.md §8.3.9（v1.11 / #DB-23 + #PB-39）；
 * 设计单：dev-docs/任务单/action-type-design.md §2.1。
 * 枚举 10 值，none 为默认且置首；data_form / data_upload 必须带非空 actionParam，其余必须为空。
 * 说明：本文件的选项文案与后端枚举语义一一对应（不新造业务措辞），仅用于管理后台配置页展示。
 */

export interface SelectOption {
  value: string
  label: string
}

/** 必须携带非空 actionParam 的行为类型（与后端 §8.3.9「参数规则」同口径） */
export const ACTION_PARAM_REQUIRED_TYPES: readonly string[] = ['data_form', 'data_upload']

/** 行为类型下拉项（none 置首） */
export const ACTION_TYPE_OPTIONS: readonly SelectOption[] = [
  { value: 'none', label: '无特殊行为（有外链则打开外链）' },
  { value: 'advisor_qr', label: '弹商家顾问企微二维码' },
  { value: 'category_picker', label: '卡内经营类目选择器' },
  { value: 'fee_picker', label: '卡内资费选择器 + fee 锚点定位' },
  { value: 'trademark_lookup', label: '商标注册号查询表单' },
  { value: 'title_optimize', label: 'AI 标题优化面板' },
  { value: 'image_optimize', label: '图片优化区块' },
  { value: 'advisor_entry', label: '顾问入口区块' },
  { value: 'data_form', label: '数据分析专区表单录入' },
  { value: 'data_upload', label: '数据分析专区文件上传' },
] as const

/**
 * 行为类型取值 → **展示文案（短）**：列表/详情只读展示用。
 * 口径（总控裁定 2026-09-16，与 COMPLETION_TYPE_LABELS 一致）：**键 → 主文案在 `*_OPTIONS` 与 `*_LABELS` 必须一致**；
 * 括号内的辅助说明属「选择时提示」，**只出现在 `*_OPTIONS` 下拉**，不进展示位。
 * 故本表不按下拉项派生，逐项显式给出（`none` 的括注仅保留在下拉项里）。
 * 未知取值由调用侧回退原值，不隐藏。
 */
export const ACTION_TYPE_LABELS: Record<string, string> = {
  none: '无特殊行为',
  advisor_qr: '弹商家顾问企微二维码',
  category_picker: '卡内经营类目选择器',
  fee_picker: '卡内资费选择器 + fee 锚点定位',
  trademark_lookup: '商标注册号查询表单',
  title_optimize: 'AI 标题优化面板',
  image_optimize: '图片优化区块',
  advisor_entry: '顾问入口区块',
  data_form: '数据分析专区表单录入',
  data_upload: '数据分析专区文件上传',
}

/** 行为类型默认值（未声明 = none） */
export const ACTION_TYPE_DEFAULT = 'none'

/* ------------------------------------------------------------------ *
 * 任务类型 type / 完成方式 completionType 下拉（#AF-21；配合 #PB-40）
 * 口径：既有 3 值的标签与顺序**保持不变**，仅**追加**库里真实存在的其余取值；
 *       不得把 form / upload / jump 映射到既有标签上（每个取值独立成项）。
 * ------------------------------------------------------------------ */

/** 任务类型 type 下拉项（既有 3 值顺序不动，追加 form / jump / upload） */
export const TASK_TYPE_OPTIONS: readonly SelectOption[] = [
  { value: 'mandatory', label: '必做' },
  { value: 'suggested', label: '建议' },
  { value: 'guide', label: '引导' },
  { value: 'form', label: '表单' },
  { value: 'jump', label: '跳转' },
  { value: 'upload', label: '上传' },
] as const

/**
 * 任务类型取值 → **展示文案（短）**：列表/详情只读展示用。
 * 同 ACTION_TYPE_LABELS / COMPLETION_TYPE_LABELS 口径：逐项显式给出（**不再由 OPTIONS 派生**），
 * 以免将来某个下拉项加了括注提示后被带进展示位。本组取值目前无括注，故两套文案逐项相同。
 */
export const TASK_TYPE_LABELS: Record<string, string> = {
  mandatory: '必做',
  suggested: '建议',
  guide: '引导',
  form: '表单',
  jump: '跳转',
  upload: '上传',
}

/**
 * 完成方式 completionType **下拉选值文案**（可带选择提示；仅用于下拉，不进列表）。
 * 既有 3 值顺序与主文案不动，追加 form_submit / file_upload。
 */
export const COMPLETION_TYPE_OPTIONS: readonly SelectOption[] = [
  { value: 'click_read', label: '点击已读' },
  { value: 'manual_submit', label: '手动提交' },
  { value: 'system_check', label: '系统检测（兼容旧任务）' },
  { value: 'form_submit', label: '表单提交' },
  { value: 'file_upload', label: '文件上传' },
] as const

/**
 * 完成方式取值 → **展示文案（短）**：列表/详情只读展示用。
 * 口径（总控裁定 2026-09-16）：**键 → 主文案在 `*_OPTIONS` 与 `*_LABELS` 必须一致**；
 * 括号内的辅助说明属「选择时提示」，**只出现在 `*_OPTIONS` 下拉**，不进列表列。
 * 故本表不按下拉项派生，逐项显式给出。
 */
export const COMPLETION_TYPE_LABELS: Record<string, string> = {
  click_read: '点击已读',
  manual_submit: '手动提交',
  system_check: '系统检测',
  form_submit: '表单提交',
  file_upload: '文件上传',
}

/** 表单字段标签 */
export const ACTION_TYPE_FIELD_LABEL = '行为类型'
export const ACTION_PARAM_FIELD_LABEL = '行为参数'

/** 列表列标签 */
export const ACTION_TYPE_COLUMN_LABEL = '行为类型'

/**
 * 行为参数校验提示：**复用后端统一校验出口原文**
 * （app/core/error_handlers.py::VALIDATION_MESSAGE「提交的内容有误，请检查后重试」），
 * 与后端 400 同句，不新造同义句（设计单 §8.3.9「参数规则」）。
 */
export const ACTION_PAIR_VALIDATION_MESSAGE = '提交的内容有误，请检查后重试'
