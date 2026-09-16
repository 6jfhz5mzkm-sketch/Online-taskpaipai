import request from './request'

export interface AdminAccount {
  id: number
  username: string
  realName: string
  phone: string
  email: string
  role: string
  status: number
  lastLoginAt: string
  createdAt: string
}

export interface CreateAccountParams {
  username: string
  password: string
  realName?: string
  phone?: string
  email?: string
  role?: string
}

export interface UpdateAccountParams {
  realName?: string
  phone?: string
  email?: string
  role?: string
  status?: number
}

export interface GenerateAccountParams {
  username: string
  realName?: string
  phone?: string
  email?: string
  role?: string
}

export interface GenerateAccountResult {
  id: number
  username: string
  realName: string
  role: string
  // 明文密码仅返回一次，需提示立即保存
  password: string
  note: string
}

// 获取管理员列表
export const getAccountList = () => {
  return request.get<AdminAccount[]>('/admin/account/list')
}

// 获取管理员详情
export const getAccountDetail = (id: number) => {
  return request.get<AdminAccount>(`/admin/account/${id}`)
}

// 创建管理员
export const createAccount = (data: CreateAccountParams) => {
  return request.post('/admin/account/create', data)
}

// 更新管理员
export const updateAccount = (id: number, data: UpdateAccountParams) => {
  return request.put(`/admin/account/${id}`, data)
}

// 删除管理员
export const deleteAccount = (id: number) => {
  return request.delete(`/admin/account/${id}`)
}

// 重置密码
export const resetPassword = (id: number, password: string) => {
  return request.post(`/admin/account/${id}/reset-password`, { password })
}

// 生成管理员账号（系统随机强密码，仅 super_admin；明文密码仅返回一次）
export const generateAccount = (data: GenerateAccountParams) => {
  return request.post<GenerateAccountResult>('/admin/account/generate', data)
}
