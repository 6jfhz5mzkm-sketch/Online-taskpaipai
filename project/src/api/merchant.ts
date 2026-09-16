/**
 * 商家登记信息接口（阶段二前引导填写；保存时服务端做格式校验：京麦商家ID 仅数字、店铺名称 仅汉字，
 * 空串与 null 同义 = 清空该字段；真源：project/docs/后端技术方案.md §5.2 API-20）
 * @description PUT /api/merchant/registration 保存（商家 JWT）；GET /api/merchant/registration 查询已填（预填）。
 */
import request from './request';

/** 商家登记信息（京东商家 ID + 店铺名称） */
export interface MerchantRegistration {
  /** 京东商家 ID */
  jd_merchant_id?: string;
  /** 店铺名称 */
  shop_name?: string;
}

/** 查询已填登记信息（进入引导弹窗前预填；无则字段为空） */
export const fetchMerchantRegistration = () =>
  request.get<MerchantRegistration>('/api/merchant/registration').then((res) => res.data);

/** 保存登记信息（服务端格式校验：京麦商家ID 仅数字、店铺名称 仅汉字；空串/ null = 清空该字段；真源 §5.2 API-20） */
export const saveMerchantRegistration = (payload: MerchantRegistration) =>
  request.put<{ ok?: boolean }>('/api/merchant/registration', payload).then((res) => res.data);
