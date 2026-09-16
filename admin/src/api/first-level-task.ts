import request from './request'

export interface FirstLevelTask {
  id: number
  taskId: string
  stageId: string
  title: string
  description: string
  buttonText: string
  status: number
  sortOrder: number
  createdAt: string
  updatedAt: string
}

export interface CreateFirstLevelTaskParams {
  taskId: string
  stageId: string
  title: string
  description?: string
  buttonText?: string
  sortOrder?: number
}

// 获取一级任务列表
export const getFirstLevelTaskList = (stageId?: string) => {
  const params = stageId ? { stageId } : {}
  return request.get<FirstLevelTask[]>('/admin/group/list', { params })
}

// 获取一级任务详情
export const getFirstLevelTaskDetail = (id: number) => {
  return request.get<FirstLevelTask>(`/admin/group/${id}`)
}

// 创建一级任务
export const createFirstLevelTask = (data: CreateFirstLevelTaskParams) => {
  return request.post('/admin/group/create', data)
}

// 更新一级任务
export const updateFirstLevelTask = (id: number, data: Partial<CreateFirstLevelTaskParams>) => {
  return request.put(`/admin/group/${id}`, data)
}

// 删除一级任务
export const deleteFirstLevelTask = (id: number) => {
  return request.delete(`/admin/group/${id}`)
}
