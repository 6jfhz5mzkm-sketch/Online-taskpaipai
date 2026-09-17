/**
 * 商家管理页（admin 端）用户可见文案 —— 管理后台唯一真源
 *
 * @description 登记：project/docs/任务管理后台开发标准.md §十一（#AF-15 / #AF-14 商家清单）。
 *              字段标签与商家端 H5（project/src/constants/merchant.ts #33/#34）措辞一致；
 *              两端是独立应用、无法共享常量文件，故各自单点定义：管理后台改动同步本文档 §十一，商家端改动同步 project/docs/开发规则.md §8.2。
 */

/** 抽屉顶部登记信息区标题 */
export const MERCHANT_INFO_TITLE = '商家登记信息'

/** 字段标签（与商家端 project/docs/开发规则.md §8.2 #33/#34 同措辞） */
export const MERCHANT_INFO_JD_ID_LABEL = '京麦商家ID'
export const MERCHANT_INFO_SHOP_NAME_LABEL = '店铺名称'

/** 空值态：字段为 null / 空串时展示，不显示 null、不隐藏该行 */
export const MERCHANT_INFO_UNREGISTERED_TEXT = '未登记'

/** 加载态 */
export const MERCHANT_INFO_LOADING_TEXT = '加载中…'

/** 取数失败态（与「未登记」区分，避免把请求失败误读成未登记） */
export const MERCHANT_INFO_FAILED_TEXT = '登记信息获取失败'

/**
 * 取回商家登记信息时的页大小：后端 keyword 为 LIKE 模糊匹配（merchant_id/nickname），
 * 需在返回集合中按 merchant_id 精确命中；20 既可覆盖少量同名/同前缀碰撞，又远低于后端上界 100。
 */
export const MERCHANT_INFO_QUERY_PAGE_SIZE = 20

/* ------------------------------------------------------------------ *
 * 商家清单页（/merchant-list）：筛选选项与表格文案
 * ------------------------------------------------------------------ */

/** 页面标题 */
export const MERCHANT_LIST_TITLE = '商家清单'

/** 关键词输入占位（与后端 #PB-29 的 4 字段匹配范围一致） */
export const MERCHANT_LIST_KEYWORD_PLACEHOLDER = '商家ID / 昵称 / 京麦商家ID / 店铺名'

/** 操作按钮 */
export const MERCHANT_LIST_SEARCH_TEXT = '查询'
export const MERCHANT_LIST_RESET_TEXT = '重置'

/** 下拉「全部」选项文案（值为空串 = 不传该筛选参数） */
export const MERCHANT_LIST_ALL_OPTION_LABEL = '全部'

/** 表格列标签 */
export const MERCHANT_LIST_COLUMN_LABELS = {
  merchantId: '商家ID',
  nickname: '昵称',
  jdMerchantId: '京麦商家ID',
  shopName: '店铺名',
  currentStage: '当前阶段',
  status: '状态',
  lastLoginAt: '最近活跃',
  createdAt: '注册时间',
  action: '操作',
} as const

/** 阶段筛选项与展示标签（值与后端契约一致） */
export const MERCHANT_STAGE_OPTIONS = [
  { value: 'onboarding', label: '入驻准备' },
  { value: 'shop_setup', label: '开店搭建' },
] as const

/** 阶段取值 → 中文标签（列表展示用；未登记取值回退原值） */
export const MERCHANT_STAGE_LABELS: Record<string, string> = {
  onboarding: '入驻准备',
  shop_setup: '开店搭建',
}

/** 状态筛选项与展示标签（值与后端契约一致） */
export const MERCHANT_STATUS_OPTIONS = [
  { value: '1', label: '正常' },
  { value: '0', label: '禁用' },
  { value: '2', label: '已退出' },
] as const

/** 状态取值 → 中文标签（列表展示用；未登记取值回退原值） */
export const MERCHANT_STATUS_LABELS: Record<string, string> = {
  '1': '正常',
  '0': '禁用',
  '2': '已退出',
}

/** 详情入口文案（商家清单操作列 + 商家进度操作列共用；点击后跳进度页并自动打开该商家抽屉） */
export const MERCHANT_DETAIL_ENTRY_TEXT = '进度详情'

/** 列表单元格空值占位（时间列为空、字段缺失时统一展示，禁止各处写死） */
export const MERCHANT_LIST_VALUE_PLACEHOLDER = '—'

/** 列表加载失败提示 */
export const MERCHANT_LIST_FAILED_TEXT = '商家列表加载失败'

/** 列表空态文案（无符合条件的商家） */
export const MERCHANT_LIST_EMPTY_TEXT = '没有符合条件的商家'

/** 分页默认页大小（与后端默认 20 一致） */
export const MERCHANT_LIST_DEFAULT_PAGE_SIZE = 20

/** 分页可选页大小（沿用反馈处理页既有取值，后端上界 100） */
export const MERCHANT_LIST_PAGE_SIZES = [10, 20, 50] as const
/** 商家进度页标题（侧栏菜单 / 面包屑 / 首页入口共用；原菜单名为「商家管理」，已按 #PB-24 契约拆分） */
export const MERCHANT_PROGRESS_TITLE = '商家进度'

/** 进度详情空态：该商家在进度列表里查不到 / 抽屉内无任务进度行时展示（原为页面内字面量，提取以复用与登记） */
export const MERCHANT_PROGRESS_EMPTY_DETAIL_TEXT = '该商家暂无任务进度记录'

/** 首页快捷入口描述 */
export const MERCHANT_LIST_QUICK_DESC = '查看商家清单'
export const MERCHANT_PROGRESS_QUICK_DESC = '查看商家进度'
/* ------------------------------------------------------------------ *
 * 同店账号绑定区（商家进度详情抽屉；设计单 §6.2 交互与文案）
 * ------------------------------------------------------------------ */

/** 区块标题 */
export const MERCHANT_BINDING_TITLE = '同店账号'

/** 未登记京麦商家ID 时的区内提示 + 绑定按钮 tooltip */
export const MERCHANT_BINDING_UNREGISTERED_TEXT = '该商家尚未登记京麦商家ID'
export const MERCHANT_BINDING_UNREGISTERED_TOOLTIP_TEXT = '需先在商家端登记京麦商家ID，才能绑定同店账号'

/** 按钮 */
export const MERCHANT_BINDING_BIND_TEXT = '绑定账号'
export const MERCHANT_BINDING_UNBIND_TEXT = '解绑'
export const MERCHANT_BINDING_SEARCH_TEXT = '搜索'
export const MERCHANT_BINDING_CANCEL_TEXT = '取消'

/** 本账号标记（自身行不可解绑） */
export const MERCHANT_BINDING_SELF_TAG_TEXT = '本账号'

/** 成员表列标签（设计单 §6.2 列清单） */
export const MERCHANT_BINDING_COLUMN_LABELS = {
  merchantId: '商家ID',
  nickname: '昵称',
  status: '状态',
  boundAt: '绑定时间',
  boundBy: '绑定人',
  action: '操作',
} as const

/** 绑定弹窗候选表列标签（只展示 3 列，**绝不展示手机号**） */
export const MERCHANT_BINDING_CANDIDATE_COLUMN_LABELS = {
  merchantId: '商家ID',
  nickname: '昵称',
  status: '状态',
} as const

/** 状态与空态 */
export const MERCHANT_BINDING_EMPTY_TEXT = '暂无同店账号绑定'
export const MERCHANT_BINDING_FAILED_TEXT = '同店账号信息加载失败'
export const MERCHANT_BINDING_CANDIDATE_EMPTY_TEXT = '没有匹配的账号'
export const MERCHANT_BINDING_SELECTED_REQUIRED_TEXT = '请先选择一个账号'

/** 绑定弹窗 */
export const MERCHANT_BINDING_DIALOG_TITLE = '绑定账号'
export const MERCHANT_BINDING_SEARCH_PLACEHOLDER = '商家ID / 昵称'
/** 二次确认文案（设计单 §6.2 原文，仅共享进度、账号级标记不共享） */
export const MERCHANT_BINDING_CONFIRM_TITLE = '确认绑定'
export const MERCHANT_BINDING_CONFIRM_MESSAGE =
  '绑定后两个账号共享阶段/任务进度；账号级标记（新手引导、欢迎消息、数据专区解锁标记）不共享'
export const MERCHANT_BINDING_CONFIRM_OK_TEXT = '确认绑定'
/** 解绑二次确认文案（设计单 §6.2 原文；默认档：组内 >= 3 个账号，组仍在、其余账号继续共享） */
export const MERCHANT_BINDING_UNBIND_CONFIRM_TITLE = '确认解绑'
export const MERCHANT_BINDING_UNBIND_CONFIRM_MESSAGE =
  '解绑后该账号不再共享本店进度；已完成的进度记录保持不变'
/** 解绑二次确认文案（2 人档：店内仅 2 个账号，解绑任一方 ⇒ 绑定关系整体解除，#PB-37-E 语义） */
export const MERCHANT_BINDING_UNBIND_CONFIRM_MESSAGE_TWO_MEMBERS =
  '解绑后该账号不再共享本店进度；本店当前仅 2 个账号，解绑后绑定关系将整体解除（另一个账号也不再共享本店进度）。已完成的进度记录保持不变。'
export const MERCHANT_BINDING_UNBIND_CONFIRM_OK_TEXT = '确认解绑'

/** 候选搜索页大小（复用 API-17 列表；后端上界 100） */
export const MERCHANT_BINDING_CANDIDATE_PAGE_SIZE = 20
