// Token管理工具

const TOKEN_KEY = 'admin_token'
const ADMIN_INFO_KEY = 'admin_info'

// 获取Token
export const getToken = (): string => {
  return localStorage.getItem(TOKEN_KEY) || ''
}

// 设置Token
export const setToken = (token: string): void => {
  localStorage.setItem(TOKEN_KEY, token)
}

// 移除Token
export const removeToken = (): void => {
  localStorage.removeItem(TOKEN_KEY)
}

// 获取管理员信息
export const getAdminInfo = (): any => {
  const info = localStorage.getItem(ADMIN_INFO_KEY)
  return info ? JSON.parse(info) : null
}

// 设置管理员信息
export const setAdminInfo = (info: any): void => {
  localStorage.setItem(ADMIN_INFO_KEY, JSON.stringify(info))
}

// 移除管理员信息
export const removeAdminInfo = (): void => {
  localStorage.removeItem(ADMIN_INFO_KEY)
}

// 清除所有认证信息
export const clearAuth = (): void => {
  removeToken()
  removeAdminInfo()
}

// 检查是否已登录
export const isLoggedIn = (): boolean => {
  return !!getToken()
}
