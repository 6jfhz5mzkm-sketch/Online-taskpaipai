/**
 * 人机校验（阿里云「图形认证」GeeTest v4 / ct4.js）唯一接缝
 *
 * @description 对外**只暴露一个函数** `getCaptchaParam(): Promise<string>`：返回 **JSON 字符串**
 *              （`lot_number` / `captcha_output` / `pass_token` / `gen_time` + `captcha_id`），
 *              原样作为 `POST /api/auth/phone/send-code` 的 `captcha_verify_param` 提交。
 *              调用点唯一：登录页「获取验证码」按钮（pages/login/index.vue）。
 *
 * **fail-closed 契约**：SDK 未加载 / appId 未配置 / 初始化失败 / 用户未完成 / 超时 → **抛错**；
 * 调用方提示兜底文案并 `console.error`，**绝不发 send-code、绝不静默跳过、不提供跳过路径**。
 *
 * SDK 资产：`ct4.js` **自托管**（阿里云要求，不引 CDN）→ 仓库路径 `project/src/static/ct4.js`
 * （uni-app H5 把 `src/static/` 原样拷到产物根 ⇒ 运行期相对路径 `./static/ct4.js`）。
 * 交付自证：14,811 B / sha256 `4E2C819C87E7324B3C3A7F83243A2C8AD4F1415C0C8EE25661DC5454F1F08B96`。
 *
 * 加载方式：点击「获取验证码」时才动态注入 `<script>`（不阻塞首屏、不预初始化），全局单次加载。
 *
 * 取值口径（已定稿，非猜测）：官方 GeeTest v4 写法 —— `captcha.onSuccess` 内取
 * `captcha.getValidate()`，把 `captcha_id` 补回结果对象后整体 `JSON.stringify` 作为参数上送。
 *
 * 官方事件分流（#FE-25-R1，按阿里云「H5 客户端接入」文档逐条核对）：
 * - `onSuccess` 且 `getValidate()` 非空 → 成功；`getValidate()` 为空 → 视图未完成（按用户取消处理）；
 * - `onClose`（用户关闭验证弹层）→ **用户取消**：抛 `CaptchaCancelledError`，提示 #60，不发码；
 * - `onError(error)`（含 code / msg / desc.detail）→ **组件/资源/服务端故障**：抛 `CaptchaUnavailableError`，提示 #59；
 * - 初始化固定 `language: 'zho'`（全中文商家端）；业务处理完毕后调用导出的 `destroyCaptcha()` 释放实例与监听。
 * @see 官方示例 Demo/nine.html L80-121 与 public-demo-uniapp/pages/index/index.vue（#FE-25 提供）
 */

/** SDK 运行期路径（与 src/static/ct4.js 对应；官方示例用相对路径，随部署路径自适应） */
export const CAPTCHA_SCRIPT_PATH = './static/ct4.js';

/** 注入 <script> 用的 id（同页只注入一次） */
const CAPTCHA_SCRIPT_ID = 'aliyun-captcha-sdk';

/** 场景/应用标识（构建期配置 `VITE_CAPTCHA_APP_ID`；captchaId 非密钥，随前端产物公开，禁止配 secret） */
const CAPTCHA_APP_ID = (import.meta.env.VITE_CAPTCHA_APP_ID || '').trim();

/** 等待用户完成校验的上限（超时视为未完成 → fail-closed，绝不放行） */
const CAPTCHA_WAIT_TIMEOUT_MS = 120000;

/** 接缝错误类型（调用方据此区分「安全验证不可用」与后端业务错误） */
export class CaptchaUnavailableError extends Error {
  /** 内部原因（只进日志，不展示给用户） */
  readonly reason: string;

  constructor(reason: string) {
    super('captcha_unavailable');
    this.name = 'CaptchaUnavailableError';
    this.reason = reason;
  }
}

/** 取错误的可读原因（内层 fail-closed 原因优先，便于线上定位；不展示给用户） */
const reasonOf = (err: unknown): string => {
  const e = err as { reason?: string; message?: string } | null;
  return String(e?.reason || e?.message || err);
};

/**
 * 用户主动取消 / 未完成验证（**不是组件故障**，提示口径与 CaptchaUnavailableError 区分开）：
 * SDK 已成功唤起但用户关闭弹层、或 onSuccess 时 getValidate() 为空（官方示例的「未完成」分支）。
 */
export class CaptchaCancelledError extends Error {
  constructor() {
    super('captcha_cancelled');
    this.name = 'CaptchaCancelledError';
  }
}

/** 记录日志并抛出 fail-closed 错误 */
const failCaptcha = (reason: string): never => {
  console.error('[captcha] 安全验证不可用（拒绝发码）：' + reason);
  throw new CaptchaUnavailableError(reason);
};

/** 官方 onError 入参（H5 客户端文档：含 code / msg / desc.detail） */
interface CaptchaErrorDetail {
  code?: number | string;
  msg?: string;
  desc?: { detail?: string };
}

/** SDK 实例形状：仅声明本接缝真正调用的成员（官方链式 API） */
interface CaptchaInstance {
  showCaptcha?: () => void;
  onReady?: (handler: () => void) => CaptchaInstance;
  onSuccess?: (handler: () => void) => CaptchaInstance;
  /** 官方：用户关闭弹出来的验证时触发（与 onError 的组件/资源故障严格区分） */
  onClose?: (handler: () => void) => CaptchaInstance;
  onError?: (handler: (error: CaptchaErrorDetail) => void) => CaptchaInstance;
  getValidate?: () => Record<string, unknown> | null;
  reset?: () => void;
  /** 官方：验证成功且业务处理完毕后调用，移除实例与事件监听 */
  destroy?: () => void;
}

/** 最近一次创建的实例（供业务处理完毕后 destroy，避免残留监听器） */
let lastInstance: CaptchaInstance | null = null;

/** 把官方 error 对象格式化为可排障的日志串（code / msg / desc.detail；只进日志，不展示给用户） */
const formatCaptchaError = (error: CaptchaErrorDetail | undefined): string => {
  if (!error) return 'captcha 组件报错（无明细）';
  return 'captcha 组件报错 code=' + String(error.code ?? '-')
    + ' msg=' + String(error.msg ?? '-')
    + ' detail=' + String(error.desc?.detail ?? '-');
};

/**
 * 销毁当前实例（官方 destroy：移除 UI 与事件监听）
 * @description 幂等；在「验证成功且业务处理完毕」后调用（发码请求结束、或登录成功）
 */
export const destroyCaptcha = (): void => {
  try {
    lastInstance?.destroy?.();
  } catch (err) {
    console.error('[captcha] destroy 失败：' + reasonOf(err));
  }
  lastInstance = null;
};

/** 动态注入 SDK 脚本（全局单次；失败不缓存，允许刷新后重试） */
let scriptPromise: Promise<void> | null = null;

const loadCaptchaScript = (): Promise<void> => {
  if (scriptPromise) return scriptPromise;
  scriptPromise = new Promise<void>((resolve, reject) => {
    const existing = document.getElementById(CAPTCHA_SCRIPT_ID) as HTMLScriptElement | null;
    if (existing) {
      resolve();
      return;
    }
    // #ifdef H5
    const script = document.createElement('script');
    script.id = CAPTCHA_SCRIPT_ID;
    script.src = CAPTCHA_SCRIPT_PATH;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      scriptPromise = null;
      reject(new CaptchaUnavailableError('脚本加载失败：' + CAPTCHA_SCRIPT_PATH));
    };
    document.body.appendChild(script);
    // #endif
    // #ifndef H5
    // 非 H5 平台无 document：显式 fail-closed（该分支在 H5 下即便未被条件编译剥离也是空操作）
    if (typeof document === 'undefined') reject(new CaptchaUnavailableError('非 H5 平台不支持图形认证'));
    // #endif
  });
  return scriptPromise;
};

/**
 * 获取人机校验串（唯一对外函数）
 * @returns 后端 `captcha_verify_param`（JSON 字符串）
 * @throws CaptchaUnavailableError fail-closed（未配置 / 加载失败 / 初始化失败 / 用户未完成 / 超时）
 */
export async function getCaptchaParam(): Promise<string> {
  if (!CAPTCHA_APP_ID) failCaptcha('未配置 VITE_CAPTCHA_APP_ID');
  await loadCaptchaScript().catch((err: unknown) => failCaptcha(reasonOf(err)));

  const initAlicom4 = (window as unknown as {
    initAlicom4?: (config: Record<string, unknown>, cb: (captcha: CaptchaInstance) => void) => void;
  }).initAlicom4;
  if (typeof initAlicom4 !== 'function') failCaptcha('ct4.js 未暴露 initAlicom4');

  return await new Promise<string>((resolve, reject) => {
    let settled = false;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      reject(new CaptchaUnavailableError('用户未完成安全验证（等待超时）'));
    }, CAPTCHA_WAIT_TIMEOUT_MS);
    const finish = (fn: () => void): void => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      fn();
    };

    initAlicom4(
      // language 固定简体中文（官方默认跟随浏览器语言；全中文商家端避免出现英文界面）
      { captchaId: CAPTCHA_APP_ID, product: 'bind', protocol: 'https://', language: 'zho' },
      (captcha: CaptchaInstance) => {
        lastInstance = captcha || null;
        if (!captcha || typeof captcha.showCaptcha !== 'function') {
          finish(() => reject(new CaptchaUnavailableError('验证码实例缺少 showCaptcha')));
          return;
        }
        captcha
          .onReady?.(() => {})
          .onSuccess?.(() => {
            // 官方取值口径：onSuccess 内取 getValidate()；未完成/无效则不放行
            const result = captcha.getValidate?.();
            if (!result) {
              // 官方示例的「未完成」分支：用户关掉了弹层或未完成验证 → 取消（不发码、不报组件故障）
              finish(() => reject(new CaptchaCancelledError()));
              return;
            }
            const param = { ...result, captcha_id: CAPTCHA_APP_ID };
            finish(() => resolve(JSON.stringify(param)));
          })
          .onClose?.(() => {
            // 官方 onClose：用户关闭验证弹层 → 用户取消（不发码、给准确轻提示 #60），不是组件故障
            captcha.reset?.();
            finish(() => reject(new CaptchaCancelledError()));
          })
          .onError?.((error: CaptchaErrorDetail) => {
            // 官方 onError：组件/资源/服务端故障（60001 / 60100 / 60101 / 60200-60205 / 60500…）→ fail-closed
            // 明细（code / msg / desc.detail）只进日志供真机排障；用户可见文案仍按 #59 兜底
            captcha.reset?.();
            finish(() => reject(new CaptchaUnavailableError(formatCaptchaError(error))));
          });
        // 点击「获取验证码」时弹出（product: 'bind' → showCaptcha，非 popup appendTo 用法）
        captcha.showCaptcha?.();
      },
    );
  }).catch((err: unknown) => {
    if (err instanceof CaptchaCancelledError) {
      // 用户取消不是故障：只记 info，不报 error（调用方给准确轻提示）
      console.info('[captcha] 用户取消/未完成安全验证（不发码）');
      throw err;
    }
    failCaptcha(reasonOf(err));
  });
}
