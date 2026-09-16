import request from './request'

/** 三入口枚举（与后端 services/ai_config.py ENTRIES 一致） */
export type AiConfigEntry = 'analysis' | 'image_optimize' | 'title_optimize'

/** 字段级生效来源：db=后台配置 / env=环境变量回落 */
export interface AiConfigEffectiveSource {
  apiKey: 'db' | 'env'
  baseUrl: 'db' | 'env'
  model: 'db' | 'env'
  timeoutMs: 'db' | 'env'
  maxTokens: 'db' | 'env'
  dailyLimit: 'db' | 'env'
}

/** GET /admin/ai-config/list 单项投影（只含掩码 + 指纹 + 状态，永不含密钥原文/密文） */
export interface AiConfigItem {
  entry: AiConfigEntry
  enabled: boolean
  apiKeySet: boolean
  apiKeyMasked: string | null
  apiKeyFingerprint: string | null
  apiKeyStatus: 'ok' | 'decrypt_failed' | 'none'
  baseUrl: string
  model: string
  timeoutMs: number
  maxTokens: number
  dailyLimit: number
  effectiveSource: AiConfigEffectiveSource
  updatedBy: string | null
  updatedAt: string | null
}

/**
 * PUT /admin/ai-config/{entry} 部分更新体（P7 §5.3 契约）：
 * - 字段省略 = 不修改；
 * - 显式 null = 清除该字段并回落 env；
 * - 空串会被后端拒 400（前端提交前拦截）；
 * - api_key 只接受密钥原文，禁止提交掩码/指纹。
 */
export interface AiConfigPatch {
  api_key?: string | null
  base_url?: string | null
  model?: string | null
  timeout_ms?: number | null
  max_tokens?: number | null
  daily_limit?: number | null
  enabled?: boolean
}

export interface AiConfigVerifyResult {
  entry: AiConfigEntry
  model: string
  baseUrl: string
  message: string
  effectiveSource: { apiKey: 'db' | 'env'; baseUrl: 'db' | 'env' }
}

/** 配置总览（仅 super_admin；非 super_admin 后端 403） */
export const getAiConfigList = () => {
  return request.get<AiConfigItem[]>('/admin/ai-config/list')
}

/** 部分更新某入口配置；成功返回该入口更新后的投影（与 list 单项同形） */
export const updateAiConfig = (entry: AiConfigEntry, patch: AiConfigPatch) => {
  return request.put<AiConfigItem>(`/admin/ai-config/${entry}`, patch)
}

/** 用当前生效配置做连通性自检（不落库、不改配置）；失败恒 502 且 message 尾部含「（错误码 X）」 */
export const verifyAiConfig = (entry: AiConfigEntry) => {
  return request.post<AiConfigVerifyResult>(`/admin/ai-config/${entry}/verify`)
}
