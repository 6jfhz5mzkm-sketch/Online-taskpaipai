/**
 * 校验工具函数
 */

/** 校验手机号 */
export const isValidPhone = (phone: string): boolean => {
  return /^1[3-9]\d{9}$/.test(phone);
};

/** 京麦商家ID 允许的字符（^[0-9]+$：仅数字，不含空格/符号/字母/汉字） */
export const JD_MERCHANT_ID_PATTERN = /^[0-9]+$/;

/** 店铺名称允许的字符（^[\u4e00-\u9fa5]+$：仅汉字，不含空格/符号/数字/字母） */
export const SHOP_NAME_PATTERN = /^[\u4e00-\u9fa5]+$/;

/** 实时过滤：仅保留数字（供输入框 @input 实时拦截非法字符用） */
export const filterDigitsOnly = (value: string): string => (value || '').replace(/[^0-9]/g, '');

/** 实时过滤：仅保留汉字（供输入框 @input 实时拦截非法字符用） */
export const filterChineseOnly = (value: string): string => (value || '').replace(/[^\u4e00-\u9fa5]/g, '');

/** 京麦商家ID 格式校验：仅数字；空值视为「未填写」（格式合法），是否允许留空由业务口径决定 */
export const isValidJdMerchantId = (value: string): boolean => !value || JD_MERCHANT_ID_PATTERN.test(value);

/** 店铺名称格式校验：仅汉字；空值视为「未填写」（格式合法），是否允许留空由业务口径决定 */
export const isValidShopName = (value: string): boolean => !value || SHOP_NAME_PATTERN.test(value);

/** 校验非空 */
export const isNotEmpty = (value: any): boolean => {
  if (value === null || value === undefined) return false;
  if (typeof value === 'string') return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  return true;
};
