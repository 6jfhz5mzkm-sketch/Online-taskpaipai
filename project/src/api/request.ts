/**
 * 请求封装
 * @description 基于 uni.request 的统一请求拦截、响应处理
 */
import { clearAuthStorage, redirectToLogin } from '@/utils/auth';

interface RequestOptions {
  url: string;
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  data?: Record<string, any>;
  header?: Record<string, string>;
  /** 静默模式：跳过默认错误 toast（由调用方自行提示用户），仍按业务码 reject */
  silent?: boolean;
}

interface ApiResponse<T = any> {
  code: number;
  message: string;
  data: T;
}

export const BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

/**
 * 登录相关公开接口：其 401 属业务语义（授权失败），不触发会话过期处理，避免与登录流程互相打断
 * （#FE-25 追加手机号登录两个端点：登录页尚未持有 token，不能因 401 触发「清登录态 + 回登录页」）
 */
const AUTH_EXEMPT_URLS = ['/api/auth/feishu/callback', '/api/auth/phone/send-code', '/api/auth/phone/login'];

/** 会话过期处理去重标记：并发多个 401 只处理一次 */
let sessionExpiredHandled = false;

/** 请求是否属于免会话处理的登录接口 */
const isAuthExempt = (url: string): boolean => AUTH_EXEMPT_URLS.some((path) => url.indexOf(path) >= 0);

/**
 * 会话过期统一处理（全项目唯一入口，禁止各页面各写一套）
 * @description 清理与跳转复用 utils/auth（与「退出登录」同一套实现）；此处只加去重，避免并发 401 重复处理。
 */
const handleSessionExpired = (): void => {
  if (sessionExpiredHandled) return;
  sessionExpiredHandled = true;
  clearAuthStorage();
  redirectToLogin();
  setTimeout(() => {
    sessionExpiredHandled = false;
  }, 1000);
};

const getAuthHeader = (): Record<string, string> => {
  const token = uni.getStorageSync('token');
  if (token) {
    return { 'Authorization': `Bearer ${token}` };
  }
  return {};
};

const request = <T = any>(options: RequestOptions): Promise<ApiResponse<T>> => {
  return new Promise((resolve, reject) => {
    uni.request({
      url: BASE_URL + options.url,
      method: options.method || 'GET',
      data: options.data,
      header: {
        'Content-Type': 'application/json',
        ...getAuthHeader(),
        ...options.header,
      },
      success: (res) => {
        const data = res.data as ApiResponse<T>;
        if (data.code === 0) {
          resolve(data);
          return;
        }
        // 401（HTTP 或业务码）→ 会话过期：清本地登录态并回登录页；登录接口豁免
        const statusCode = (res as unknown as { statusCode?: number }).statusCode;
        if (!isAuthExempt(options.url) && (statusCode === 401 || data.code === 401)) {
          handleSessionExpired();
        }
        if (!options.silent) {
          uni.showToast({ title: data.message || '请求失败', icon: 'none' });
        }
        reject(data);
      },
      fail: (err) => {
        uni.showToast({ title: '网络异常', icon: 'none' });
        reject(err);
      },
    });
  });
};

// 快捷方法
request.get = <T = any>(url: string, options?: Omit<RequestOptions, 'url' | 'method'>) => {
  return request<T>({ url, method: 'GET', ...options });
};

request.post = <T = any>(url: string, data?: Record<string, any>, options?: Omit<RequestOptions, 'url' | 'method' | 'data'>) => {
  return request<T>({ url, method: 'POST', data, ...options });
};

request.put = <T = any>(url: string, data?: Record<string, any>, options?: Omit<RequestOptions, 'url' | 'method' | 'data'>) => {
  return request<T>({ url, method: 'PUT', data, ...options });
};

export default request;
