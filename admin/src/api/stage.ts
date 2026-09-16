import request from './request'

export interface Stage {
  id: number
  stageId: string
  stageNum: number
  title: string
  description: string
  status: number
  sortOrder: number
  // 所属大阶段（1=阶段一/2=阶段二）；列表接口返回
  phaseNum: number
  createdAt: string
  updatedAt: string
}

export interface CreateStageParams {
  stageId: string
  stageNum: number
  title: string
  description?: string
  // 所属大阶段（1=阶段一/2=阶段二）；后端 CreateStageDto 当前未声明，提交前需后端补 DTO 支持
  phaseNum?: number
  sortOrder?: number
}

// 获取阶段列表
export const getStageList = () => {
  return request.get<Stage[]>('/admin/stage/list')
}

// 获取阶段详情
export const getStageDetail = (id: number) => {
  return request.get<Stage>(`/admin/stage/${id}`)
}

// 创建阶段
export const createStage = (data: CreateStageParams) => {
  return request.post('/admin/stage/create', data)
}

// 更新阶段
export const updateStage = (id: number, data: Partial<CreateStageParams>) => {
  return request.put(`/admin/stage/${id}`, data)
}

// 删除阶段
export const deleteStage = (id: number) => {
  return request.delete(`/admin/stage/${id}`)
}
