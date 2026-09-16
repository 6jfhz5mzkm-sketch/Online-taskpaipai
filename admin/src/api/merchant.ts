import request from './request'

/** 管理端商家主表列表项（GET /api/admin/merchant，API-17 投影；snake_case 与后端一致） */
export interface AdminMerchantItem {
  merchant_id: string
  nickname: string | null
  merchant_name: string | null
  current_stage: string
  /** 京麦商家ID（未登记为 null） */
  jd_merchant_id: string | null
  /** 店铺名称（未登记为 null） */
  shop_name: string | null
  last_login_at: string | null
  created_at: string | null
  /**
   * 商家状态（1=正常 / 0=禁用 / 2=已退出）。
   * 说明：当前投影（api-py/app/services/merchant.py list_all）**未返回**该字段，
   * 冻结契约的 list 项亦未列出 —— 故此处声明为可选；#PB-24 落地后自动可用，
   * 未返回时列表按「空值占位」展示，不隐藏该行、不伪造取值。
   */
  status?: number | null
}

export interface AdminMerchantListResult {
  list: AdminMerchantItem[]
  total: number
  page: number
  page_size: number
}

/** 商家阶段（后端契约：onboarding=入驻准备 / shop_setup=开店搭建；非法值 400） */
export type AdminMerchantStage = 'onboarding' | 'shop_setup'

/** 商家状态查询值（后端契约：1=正常 / 0=禁用 / 2=已退出；非法值 400；Query 为字符串） */
export type AdminMerchantStatus = '1' | '0' | '2'

export interface AdminMerchantQuery {
  /** 对 商家ID / 昵称 / 京麦商家ID / 店铺名 4 字段 OR 模糊匹配（#PB-29） */
  keyword?: string
  stage?: AdminMerchantStage
  status?: AdminMerchantStatus
  page?: number
  /** 后端上界 100（services/merchant.list_all: min(100, ...)） */
  page_size?: number
}

/**
 * 商家主表列表（API-17，权限=需登录）。
 * 用途：① 商家清单页的列表查询（keyword/stage/status/page/page_size）；
 *      ② 商家进度页按 merchantId 精确取回单个商家（传 keyword=<merchantId> 后由调用方按 merchant_id 命中）。
 */
export const getAdminMerchantList = (params: AdminMerchantQuery) => {
  return request.get<AdminMerchantListResult>('/admin/merchant', { params })
}
/* ------------------------------------------------------------------ *
 * 同店账号绑定（API-22；设计单 dev-docs/任务单/merchant-account-binding-design.md §6.3）
 * 读 = 需登录；写 = admin / super_admin（viewer 403 由后端保证）
 * ------------------------------------------------------------------ */

/**
 * request 响应拦截器已把 AxiosResponse 解包为后端统一响应体 `{code, message, data}`
 * （见 `api/request.ts` 拦截器 return data），但其 TS 类型仍是 AxiosResponse ——
 * 绑定三接口按运行时契约收窄，便于直接展示后端 `message` 原文（不新造同义句）。
 */
export interface MerchantApiEnvelope<T> {
  code: number
  message: string
  data: T
}

/** 绑定成员行（API-22 投影；status 为 merchant.status 数值，1=正常/0=禁用/2=已退出） */
export interface MerchantBindingMember {
  merchant_id: string
  nickname: string | null
  status: number | null
  current_stage: string | null
  bound_at: string | null
  bound_by: string | null
  /** 是否为当前查询商家自身（自身行不可解绑） */
  is_self: boolean
}

export interface MerchantBindingsResult {
  /** 未登记京麦商家ID 时为 null（前端据此禁用绑定入口） */
  jd_merchant_id: string | null
  /** 未绑定时为 null */
  group_id: number | null
  /** 未绑定时仅含自身一行 */
  members: MerchantBindingMember[]
}

export interface MerchantBindResult {
  success: boolean
  group_id: number | null
  members: MerchantBindingMember[]
}

export interface MerchantReleaseResult {
  success: boolean
}

/** 同店账号绑定关系（GET /api/admin/merchant/{merchantId}/bindings） */
export const getMerchantBindings = (merchantId: string) => {
  return request.get<MerchantBindingsResult>(
    `/admin/merchant/${encodeURIComponent(merchantId)}/bindings`,
  ) as unknown as Promise<MerchantApiEnvelope<MerchantBindingsResult>>
}

/** 绑定成员账号（POST，body {member_merchant_id}；幂等：目标已在同组则返回现状） */
export const bindMerchantMember = (merchantId: string, memberMerchantId: string) => {
  return request.post<MerchantBindResult>(
    `/admin/merchant/${encodeURIComponent(merchantId)}/bindings`,
    { member_merchant_id: memberMerchantId },
  ) as unknown as Promise<MerchantApiEnvelope<MerchantBindResult>>
}

/** 解绑成员账号（DELETE；path 只含两个 merchantId，不暴露内部 binding id） */
export const releaseMerchantMember = (merchantId: string, memberMerchantId: string) => {
  return request.delete<MerchantReleaseResult>(
    `/admin/merchant/${encodeURIComponent(merchantId)}/bindings/${encodeURIComponent(memberMerchantId)}`,
  ) as unknown as Promise<MerchantApiEnvelope<MerchantReleaseResult>>
}
