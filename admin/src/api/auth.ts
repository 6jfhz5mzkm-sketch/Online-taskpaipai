import request from './request'

export interface LoginParams {
  username: string
  password: string
}

export interface LoginResult {
  token: string
  admin: {
    id: number
    username: string
    realName: string
    role: string
  }
}

export interface ChangePasswordParams {
  oldPassword: string
  newPassword: string
}

// 管理员登录
export const login = (data: LoginParams) => {
  return request.post<LoginResult>('/admin/auth/login', data)
}

// 修改密码
export const changePassword = (data: ChangePasswordParams) => {
  return request.post('/admin/auth/change-password', data)
}

// 获取当前管理员信息
export const getProfile = () => {
  return request.get('/admin/auth/profile')
}
