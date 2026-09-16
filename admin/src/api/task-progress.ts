import request from './request'

export interface MerchantProgressItem {
  id: number
  merchantId: string
  taskId: string
  status: string
  completedAt: string | null
  createdAt: string
  updatedAt: string
}

export interface UnlockResult {
  success: boolean
  stage2_unlocked: boolean
}

// 商家任务进度（全部；不带 merchantId 时返回所有商家的任务进度行，前端聚合为商家列表）
export const getMerchantProgressList = (merchantId?: string) => {
  const params = merchantId ? { merchantId } : {}
  return request.get<MerchantProgressItem[]>('/admin/merchant/progress', { params })
}

// 指定商家任务进度
export const getMerchantProgressDetail = (merchantId: string) => {
  return request.get<MerchantProgressItem[]>(`/admin/merchant/progress/${encodeURIComponent(merchantId)}`)
}

// 商家阶段一解锁（:id 即 merchant_id 字符串；幂等）
export const unlockMerchantPhase1 = (merchantId: string) => {
  return request.post<UnlockResult>(`/admin/merchant/${encodeURIComponent(merchantId)}/unlock-phase1`)
}
