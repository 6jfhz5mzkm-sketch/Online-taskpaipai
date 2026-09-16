import request from './request'

export interface SecondLevelTask {
  id: number
  taskId: string
  firstLevelTaskId: string
  stageId: string
  title: string
  description: string
  detail: string
  type: string
  completionType: string
  actionText: string
  actionUrl: string
  tag: string
  defaultCompleted: number
  status: number
  sortOrder: number
  createdAt: string
  updatedAt: string
}

export interface CreateSecondLevelTaskParams {
  taskId: string
  firstLevelTaskId: string
  stageId: string
  title: string
  description?: string
  detail?: string
  type: string
  completionType: string
  actionText?: string
  actionUrl?: string
  tag?: string
  defaultCompleted?: number
  sortOrder?: number
}

// 获取二级任务列表
export const getSecondLevelTaskList = (firstLevelTaskId?: string, stageId?: string) => {
  const params: any = {}
  if (firstLevelTaskId) params.firstLevelTaskId = firstLevelTaskId
  if (stageId) params.stageId = stageId
  return request.get<SecondLevelTask[]>('/admin/task/list', { params })
}

// 获取二级任务详情
export const getSecondLevelTaskDetail = (id: number) => {
  return request.get<SecondLevelTask>(`/admin/task/${id}`)
}

// 创建二级任务
export const createSecondLevelTask = (data: CreateSecondLevelTaskParams) => {
  return request.post('/admin/task/create', data)
}

// 更新二级任务
export const updateSecondLevelTask = (id: number, data: Partial<CreateSecondLevelTaskParams>) => {
  return request.put(`/admin/task/${id}`, data)
}

// 删除二级任务
export const deleteSecondLevelTask = (id: number) => {
  return request.delete(`/admin/task/${id}`)
}
