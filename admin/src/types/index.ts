// 管理员信息
export interface AdminInfo {
  id: number
  username: string
  realName: string
  role: string
}

// 通用响应
export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}

// 分页响应
export interface PaginatedResponse<T = any> {
  list: T[]
  total: number
  page: number
  pageSize: number
}
