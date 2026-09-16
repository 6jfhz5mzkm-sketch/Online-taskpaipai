import request from './request'

// 反馈分类与状态（与后端 FEEDBACK_CATEGORIES / FEEDBACK_STATUSES 对齐）
export const FEEDBACK_CATEGORIES = ['功能建议', '使用问题', '任务异常', '其他'] as const
export const FEEDBACK_STATUSES = ['pending', 'processing', 'resolved'] as const

export interface Feedback {
  id: number
  merchantId: string | null
  content: string
  category: string
  status: string
  adminReply: string | null
  handlerId: number | null
  createdAt: string
  updatedAt: string
}

// 列表响应（list/total/page/page_size 与后端对齐）
export interface FeedbackListData {
  list: Feedback[]
  total: number
  page: number
  page_size: number
}

export interface FeedbackQuery {
  status?: string
  category?: string
  page?: number
  page_size?: number
}

export interface HandleFeedbackParams {
  status?: string
  adminReply?: string
}

// 反馈列表（管理端，status/category 筛选 + 分页）
export const getFeedbackList = (params: FeedbackQuery) => {
  return request.get<FeedbackListData>('/admin/feedback', { params })
}

// 处理反馈（更新 status + adminReply，字段为驼峰）
export const handleFeedback = (id: number, data: HandleFeedbackParams) => {
  return request.patch(`/admin/feedback/${id}`, data)
}
