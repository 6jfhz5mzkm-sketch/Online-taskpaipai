/**
 * 展示层脱敏工具（仅用于管理后台页面展示，不改动接口、请求参数与存储）。
 * 空值统一展示为 '-'，避免出现 null / 空白单元格。
 */

/** 手机号脱敏：保留前 3 位与后 4 位，如 138****1234；短于 7 位时仅保留首位 */
export const maskPhone = (value?: string | null): string => {
  const text = (value ?? '').trim()
  if (!text) return '-'
  if (text.length >= 7) return `${text.slice(0, 3)}****${text.slice(-4)}`
  return `${text.slice(0, 1)}${'*'.repeat(Math.max(text.length - 1, 1))}`
}

/** 邮箱脱敏：保留邮箱名前 2 位与域名，如 ab***@example.com；无 @ 时按普通文本处理 */
export const maskEmail = (value?: string | null): string => {
  const text = (value ?? '').trim()
  if (!text) return '-'
  const at = text.lastIndexOf('@')
  if (at <= 0) return `${text.slice(0, 2)}***`
  return `${text.slice(0, at).slice(0, 2)}***${text.slice(at)}`
}
