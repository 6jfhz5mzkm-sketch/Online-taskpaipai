/**
 * 退出登录 · 两侧壳层共用实现入口（唯一真源）
 *
 * @description 阶段一（pages/index/index.vue）与阶段二
 *              （components-local/stage2/Stage2Sidebar.vue）共用本模块：
 *              文案常量在此单点定义（开发规则 §8.1 第 1 条：同一句文案 ≥2 处必须抽常量）。
 *              登出动作的唯一 owner 是 project/src/utils/auth.ts（工具函数归 utils），
 *              调用方一律从 '@/utils/auth' 导入登出动作，本文件不再转出。
 *              登记：project/docs/开发规则.md §8.2（新增或修改文案必须同步该表）。
 */

/** 退出登录入口按钮（侧栏用户区） */
export const LOGOUT_ENTRY_TEXT = '退出登录';

/** 退出登录二次确认弹窗标题 */
export const LOGOUT_CONFIRM_TITLE = '退出登录';

/** 退出登录二次确认弹窗说明（不回显技术细节，只给可执行动作） */
export const LOGOUT_CONFIRM_MESSAGE = '退出后需重新登录才能继续完成任务，确认退出吗？';

/** 退出登录二次确认弹窗 · 取消按钮（不退出） */
export const LOGOUT_CONFIRM_CANCEL_TEXT = '取消';

/** 退出登录二次确认弹窗 · 确认按钮 */
export const LOGOUT_CONFIRM_OK_TEXT = '确认退出';

/* ------------------------------------------------------------------
 * 手机号 + 短信验证码登录（#FE-25）
 * 文案/正则/模式解析的唯一真源；调用方（pages/login/index.vue）只消费，不再各自字面量。
 * 后端文案（400/403/429/502/503）不在本文件登记：前端只展示后端 message（开发规则 §8 文案真源）。
 * ------------------------------------------------------------------ */

/** 登录模式（构建期 `VITE_LOGIN_MODE`）：phone（生产）/ feishu（隐藏回退）/ mock（本地） */
export type LoginMode = 'phone' | 'feishu' | 'mock';

/**
 * 解析登录模式：非法值/空值一律回落 `mock`（沿用既有「误配即坏」防护）
 * @param raw 原始值（一般传 `import.meta.env.VITE_LOGIN_MODE`）
 */
export const resolveLoginMode = (raw: unknown): LoginMode => {
  const value = String(raw ?? '').trim();
  return value === 'phone' || value === 'feishu' || value === 'mock' ? value : 'mock';
};

/** 中国大陆手机号正则（就地校验用，与服务端 Pydantic regex 同口径） */
export const PHONE_PATTERN = /^1[3-9]\d{9}$/;

/** 手机号长度（input maxlength） */
export const PHONE_LENGTH = 11;

/** 短信验证码长度（后端 `code_length` 默认 6；此处仅作输入 maxlength 上界） */
export const PHONE_CODE_LENGTH = 6;

/** 表单标题 */
export const PHONE_LOGIN_TITLE = '手机号登录';

/** 手机号输入框占位 */
export const PHONE_PLACEHOLDER = '请输入手机号';

/** 验证码输入框占位（同时用作「未填验证码」的就地提示，避免同一句文案两处字面量） */
export const PHONE_CODE_PLACEHOLDER = '请输入验证码';

/** 获取验证码按钮（默认态） */
export const PHONE_SEND_CODE_TEXT = '获取验证码';

/** 获取验证码按钮（请求中） */
export const PHONE_SEND_CODE_LOADING_TEXT = '发送中...';

/** 重新获取验证码按钮前缀（倒计时展示为「重新获取(60s)」，秒数以后端 `cooldown_seconds` 为准） */
export const PHONE_RESEND_CODE_TEXT = '重新获取';

/** 手机号格式不合法（就地提示） */
export const PHONE_INVALID_TEXT = '手机号格式不正确';

/** 登录按钮（默认态） */
export const PHONE_LOGIN_BUTTON_TEXT = '登录';

/** 登录按钮（请求中） */
export const PHONE_LOGIN_LOADING_TEXT = '登录中...';

/** 人机校验（ct4.js）不可用时的兜底提示：不含内部码/供应商名，只给可执行动作（组件/配置/加载失败、SDK 404、超时） */
export const CAPTCHA_UNAVAILABLE_TEXT = '安全验证组件加载失败，请刷新重试或稍后再试';

/** 用户主动取消/未完成安全验证时的轻提示（不是组件故障，措辞必须准确；#FE-25-R1 裁决） */
export const CAPTCHA_INCOMPLETE_TEXT = '请完成安全验证后再获取验证码';
