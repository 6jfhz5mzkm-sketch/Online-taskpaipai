/**
 * 当前登录商家信息读取（商家端唯一入口）
 *
 * 数据真源：登录页登录成功后持久化后端返回的 merchant 对象
 *   pages/login/index.vue → uni.setStorageSync('merchant', JSON.stringify(res.data.merchant))
 *   （storage 键名与写入方全项目仅此一处；字段见 api-py/app/services/auth.py 商家登录响应）
 *
 * 读取语义：uni-app H5 对「字符串写入」的值原样存储，getStorageSync 返回 JSON 字符串，
 *   故统一交给 utils/storage.ts 的 storage.get 解析（唯一解析入口，不在调用方重复解析）。
 *
 * 未登录 / 未写入 / 解析失败一律返回空串，由调用方据此不渲染用户区；不抛异常、不兜底伪造名称。
 */
import { storage } from './storage';
import type { MerchantProfile } from '@/types/user';

/** storage 中登录商家信息的键名（唯一写入方：pages/login/index.vue） */
export const MERCHANT_STORAGE_KEY = 'merchant';

/** 当前登录商家的展示名（nickname）；无有效商家信息时返回空串 */
export function getMerchantNickname(): string {
  const profile = storage.get<MerchantProfile>(MERCHANT_STORAGE_KEY);
  return (profile && profile.nickname) || '';
}
