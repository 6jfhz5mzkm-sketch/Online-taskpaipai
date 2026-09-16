/**
 * 用户相关类型定义
 */
export interface UserInfo {
  id: string;
  nickname: string;
  avatar: string;
  merchantId: string;
  merchantName: string;
}

/**
 * 登录接口返回、并持久化到 storage('merchant') 的商家信息（前端展示名来源）。
 * 字段真源：api-py/app/services/auth.py 商家登录响应的 merchant 对象
 * （merchant_id / nickname / current_stage / feishu_open_id）。
 * 本类型只声明前端当前消费的字段；需要其它字段时按后端真源补充，不要在此臆造。
 */
export interface MerchantProfile {
  /** 展示名（后端昵称；mock 登录下为「测试商家」） */
  nickname?: string;
}
