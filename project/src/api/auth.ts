/**
 * 认证接口（商家端）
 * @description 唯一真源：`project/docs/后端技术方案.md` §5.2（接口/字段/错误码）；本单消费 #PB-23 的手机号登录两个端点：
 *              - `POST /api/auth/phone/send-code`（公开）：{ phone, captcha_verify_param } → 200 { sent, cooldown_seconds, expires_in_seconds, code_length }
 *              - `POST /api/auth/phone/login`（公开）：{ phone, code } → 201 { token, merchant, is_new_merchant }
 *              错误文案一律由后端 message 提供（400/403/429/502/503），前端不新造同义句（开发规则 §8）。
 * @see dev-docs/任务单/phone-sms-login-design.md §三 / §3.3
 */
import request from './request';

/** 发码响应（data 段） */
export interface SendPhoneCodeResult {
  /** 是否已发出 */
  sent: boolean;
  /** 冷却秒数（前端倒计时唯一来源，禁止硬编码） */
  cooldown_seconds: number;
  /** 验证码有效期（秒） */
  expires_in_seconds: number;
  /** 验证码位数 */
  code_length: number;
}

/** 登录响应中的商家信息（字段与后端契约一致，前端只消费不构造） */
export interface PhoneLoginMerchant {
  merchant_id: string;
  nickname?: string;
  avatar?: string;
  merchant_name?: string;
  current_stage?: string;
  status?: string;
}

/** 登录响应（data 段） */
export interface PhoneLoginResult {
  token: string;
  merchant: PhoneLoginMerchant;
  /** 本次是否为新注册商家 */
  is_new_merchant: boolean;
}

/**
 * 发送短信验证码（需携带人机校验串）
 * @param phone 手机号
 * @param captchaVerifyParam 人机校验接缝产出的不透明串（`utils/captcha.getCaptchaParam()`）
 * @description 静默模式：错误文案由调用方统一展示（一律展示后端 message）
 */
export const sendPhoneCode = (phone: string, captchaVerifyParam: string) =>
  request.post<SendPhoneCodeResult>(
    '/api/auth/phone/send-code',
    { phone, captcha_verify_param: captchaVerifyParam },
    { silent: true },
  );

/** 手机号 + 验证码登录（登录即注册；成功 201） */
export const phoneLogin = (phone: string, code: string) =>
  request.post<PhoneLoginResult>('/api/auth/phone/login', { phone, code }, { silent: true });
