/**
 * AI 配置页（仅 super_admin）用户可见文案 —— 管理后台唯一真源
 *
 * @description 登记：project/docs/开发规则.md §8.2（#AF-14）。§8.1 第 1 条：同一句文案 ≥2 处出现必须抽常量。
 *              字段标签 / 按钮 / 提示 / 空态 / 确认框文案一律走本文件，组件内不写字面量。
 */

import type { AiConfigEntry } from '@/api/ai-config'

/** 页面与菜单标题 */
export const AI_CONFIG_MENU_TEXT = 'AI 配置'

/** 页面顶部说明（写入语义：留空=不修改、清除=回落 env） */
export const AI_CONFIG_PAGE_INTRO_TEXT =
  '密钥保存后只显示掩码与指纹，不提供查看原文；未修改的字段不会被提交；密钥输入框留空表示不修改；清空其它字段并保存表示清除自定义值、回落 env。'

/** 三入口展示名 */
export const AI_CONFIG_ENTRY_LABELS: Record<AiConfigEntry, string> = {
  analysis: 'AI 经营分析',
  image_optimize: '主图优化',
  title_optimize: '标题优化',
}

/** 字段标签 */
export const AI_CONFIG_FIELD_LABELS = {
  apiKey: '密钥（api_key）',
  baseUrl: '接口地址（base_url）',
  model: '模型（model）',
  timeoutMs: '超时（ms）',
  maxTokens: '最大 tokens',
  dailyLimit: '每日限流',
  enabled: '启用',
} as const

/** 按钮文案 */
export const AI_CONFIG_SAVE_TEXT = '保存'
export const AI_CONFIG_VERIFY_TEXT = '测试连接'
export const AI_CONFIG_CLEAR_KEY_TEXT = '清除自定义密钥'

/** 生效来源标签（只读） */
export const AI_CONFIG_SOURCE_LABELS = { db: 'DB', env: 'env' } as const

/** 密钥状态文案 */
export const AI_CONFIG_KEY_STATUS_OK_TEXT = '密钥正常'
export const AI_CONFIG_KEY_STATUS_NONE_TEXT = '未配置密钥（回落 env）'
export const AI_CONFIG_KEY_STATUS_DECRYPT_FAILED_TEXT = '加密密钥不匹配，当前回落 env'

/** 密钥输入框占位（不预填掩码，只把当前掩码放进 placeholder） */
export const AI_CONFIG_SECRET_PLACEHOLDER_CONFIGURED_PREFIX = '已配置：'
export const AI_CONFIG_SECRET_PLACEHOLDER_SUFFIX = '（留空表示不修改）'
export const AI_CONFIG_SECRET_PLACEHOLDER_EMPTY = '未配置（留空表示不修改）'

/** 只读元信息 */
export const AI_CONFIG_FINGERPRINT_PREFIX = '指纹：'
export const AI_CONFIG_FINGERPRINT_EMPTY_TEXT = '指纹：—'
export const AI_CONFIG_UPDATED_PREFIX = '最近修改：'
export const AI_CONFIG_UPDATED_EMPTY_TEXT = '最近修改：—'

/** 提交前本地校验（与后端 §5.3 契约一致，避免发出必然 400 的请求） */
export const AI_CONFIG_API_KEY_LENGTH_TEXT = '密钥长度需在 8-256 之间'
export const AI_CONFIG_API_KEY_MASK_REJECT_TEXT = '检测到掩码内容，请填写完整密钥'
export const AI_CONFIG_BASE_URL_FORMAT_TEXT = '接口地址需以 http:// 或 https:// 开头'

/** 保存结果 */
export const AI_CONFIG_SAVE_OK_TEXT = '已保存，当前进程立即生效；其它 worker 最多 60 秒后生效'

/** 清除自定义密钥（显式 null = 回落 env） */
export const AI_CONFIG_CLEAR_CONFIRM_TITLE = '清除自定义密钥'
export const AI_CONFIG_CLEAR_CONFIRM_MESSAGE = '清除后该入口将回落使用环境变量（env）中的密钥，确认清除吗？'
export const AI_CONFIG_CLEAR_CONFIRM_OK_TEXT = '确认清除'
export const AI_CONFIG_CLEAR_CONFIRM_CANCEL_TEXT = '取消'
export const AI_CONFIG_CLEAR_OK_TEXT = '已清除自定义密钥，该入口已回落 env'

/** 路由守卫：非 super_admin 直连被拦截时的提示 */
export const AI_CONFIG_ROLE_DENIED_TEXT = '无权访问该页面（仅超级管理员）'

/** 密钥掩码形态正则（与后端 looks_like_mask 同形；仅用于提交前拦截） */
export const AI_CONFIG_MASK_PATTERN = /^.{0,8}\*{4}.{0,8}$/

/** 字段取值上界（与后端 admin_ai_config.AiConfigPatchBody 的 ge/le 一致，防呆） */
export const AI_CONFIG_LIMITS = {
  apiKey: { min: 8, max: 256 },
  timeoutMs: { min: 1000, max: 600000 },
  maxTokens: { min: 1, max: 32000 },
  dailyLimit: { min: 0, max: 100 },
} as const

/** 未产生任何 dirty 字段时的提示 */
export const AI_CONFIG_NO_DIRTY_TEXT = '没有需要保存的修改'

/** 列表空态 */
export const AI_CONFIG_EMPTY_TEXT = '暂无 AI 配置'

/** 启用开关旁提示（关闭 = 整行回落 env） */
export const AI_CONFIG_ENABLED_HINT_TEXT = '关闭后该入口整体回落 env 配置（不清空已存字段）'
