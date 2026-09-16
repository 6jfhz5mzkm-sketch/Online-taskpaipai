<template>
  <view class="login-page">
    <!-- 背景装饰 -->
    <view class="login-bg">
      <view class="login-bg__circle login-bg__circle--1" />
      <view class="login-bg__circle login-bg__circle--2" />
      <view class="login-bg__circle login-bg__circle--3" />
    </view>

    <!-- 登录卡片 -->
    <view class="login-card">
      <!-- Logo 区域 -->
      <view class="login-card__logo">
        <view class="login-card__icon">
          <text class="login-card__icon-text">P</text>
        </view>
        <text class="login-card__title">商家成长任务助手</text>
      </view>

      <!-- 登录表单 -->
      <view class="login-card__form">
        <!-- 手机号 + 短信验证码登录（构建期 VITE_LOGIN_MODE=phone；生产默认） -->
        <view v-if="LOGIN_MODE === 'phone'" class="phone-login">
          <text class="phone-login__title">{{ PHONE_LOGIN_TITLE }}</text>

          <view class="phone-login__field">
            <input
              class="phone-login__input"
              type="number"
              inputmode="numeric"
              :maxlength="PHONE_LENGTH"
              :value="phone"
              :placeholder="PHONE_PLACEHOLDER"
              placeholder-class="phone-login__placeholder"
              @input="handlePhoneInput"
            />
          </view>
          <text v-if="phoneError" class="phone-login__error">{{ phoneError }}</text>

          <view class="phone-login__field phone-login__field--code">
            <input
              class="phone-login__input phone-login__input--code"
              type="number"
              inputmode="numeric"
              :maxlength="PHONE_CODE_LENGTH"
              :value="code"
              :placeholder="PHONE_CODE_PLACEHOLDER"
              placeholder-class="phone-login__placeholder"
              @input="handleCodeInput"
            />
            <view
              class="phone-login__send"
              :class="{ 'is-disabled': sendDisabled }"
              @tap="handleSendCode"
            >
              <text class="phone-login__send-text">{{ sendButtonText }}</text>
            </view>
          </view>

          <view class="login-btn" :class="{ 'is-loading': phoneLoading }" @tap="handlePhoneLogin">
            <view v-if="!phoneLoading" class="login-btn__content">
              <text class="login-btn__text">{{ PHONE_LOGIN_BUTTON_TEXT }}</text>
            </view>
            <view v-else class="login-btn__loading">
              <view class="login-btn__spinner" />
              <text class="login-btn__text">{{ PHONE_LOGIN_LOADING_TEXT }}</text>
            </view>
          </view>
        </view>

        <!-- 飞书授权入口：phone 模式不展示（feishu 为隐藏回退；mock 供本地验证） -->
        <template v-else>
        <view 
          class="login-btn" 
          :class="{ 'is-loading': loading }"
          @tap="handleFeishuLogin"
        >
          <view v-if="!loading" class="login-btn__content">
            <view class="login-btn__icon">
              <text class="login-btn__icon-text">飞</text>
            </view>
            <text class="login-btn__text">飞书授权登录</text>
          </view>
          <view v-else class="login-btn__loading">
            <view class="login-btn__spinner" />
            <text class="login-btn__text">登录中...</text>
          </view>
        </view>
        </template>

        <text class="login-card__tip">首次登录将自动创建账号</text>
      </view>

      <!-- 底部信息（含备案信息，工信部要求） -->
      <view class="login-card__footer">
        <text class="login-card__copyright">© 2024 商家成长任务体系</text>
        <IcpFooter />
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import request from '@/api/request';
import { phoneLogin, sendPhoneCode } from '@/api/auth';
import { destroyCaptcha, getCaptchaParam } from '@/utils/captcha';
import { trackLoginClick, trackLoginSuccess, trackLoginFail, trackPageView } from '@/utils/track';
import {
  CAPTCHA_INCOMPLETE_TEXT,
  CAPTCHA_UNAVAILABLE_TEXT,
  PHONE_CODE_LENGTH,
  PHONE_CODE_PLACEHOLDER,
  PHONE_INVALID_TEXT,
  PHONE_LENGTH,
  PHONE_LOGIN_BUTTON_TEXT,
  PHONE_LOGIN_LOADING_TEXT,
  PHONE_LOGIN_TITLE,
  PHONE_PATTERN,
  PHONE_PLACEHOLDER,
  PHONE_RESEND_CODE_TEXT,
  PHONE_SEND_CODE_LOADING_TEXT,
  PHONE_SEND_CODE_TEXT,
  resolveLoginMode,
} from '@/constants/auth';
import IcpFooter from '@/components/IcpFooter/index.vue';

const loading = ref(false);
/**
 * 登录模式（构建期配置 VITE_LOGIN_MODE）：`phone`（生产）/ `feishu`（隐藏回退）/ `mock`（本地）；
 * 非法值/空值一律回落 `mock`（解析与回落规则见 constants/auth.ts，避免误配即坏）
 */
const LOGIN_MODE = resolveLoginMode(import.meta.env.VITE_LOGIN_MODE);
/** 飞书应用 App ID（构建期配置 VITE_FEISHU_APP_ID；app_id 非密钥，随授权 URL 公开，禁止在此配置任何 secret） */
const FEISHU_APP_ID = (import.meta.env.VITE_FEISHU_APP_ID || '').trim();
/** 飞书应用未配置时的失败提示（feishu 模式且 app_id 为空时使用，不构造空参 URL） */
const FEISHU_APP_ID_MISSING_TEXT = '飞书应用未配置';
/** 授权码失效（飞书错误码 20003）时的用户指引：不回显错误码，只给可执行动作 */
const AUTH_CODE_EXPIRED_TEXT = '登录链接已失效，请重新点击飞书登录';
/** 飞书错误码 20003：授权码无效/已过期（后端 message 形如「飞书授权失败，请重新登录（飞书错误码 20003）」） */
const FEISHU_INVALID_CODE = '20003';
const REDIRECT_URI = encodeURIComponent(window.location.origin);

/**
 * 已提交过的授权码（模块级而非组件级：组件重挂载/重复 onMounted 时仍生效）
 * @description 飞书授权码是一次性凭证，同一 code 只允许提交一次，杜绝重复 POST。
 */
let submittedAuthCode = '';
/** 自动重发起授权是否已用过（每次页面加载最多自动重试一次，避免失效码导致「前端↔飞书」无限跳转） */
let autoRetryUsed = false;

/**
 * 读取并**立即**从地址栏清除飞书授权码
 * @description 授权码是一次性凭证：无论后续换取成功还是失败，都必须先清掉，
 *              否则失败时 ?code 留在地址栏，每次页面加载都会重放同一个废码（生产 20003 循环根因）。
 *              保留 hash 路由，只去掉 query。
 */
const consumeAuthCode = (): string => {
  const code = new URLSearchParams(window.location.search).get('code') || '';
  if (code) {
    window.history.replaceState({}, '', window.location.pathname + window.location.hash);
  }
  return code;
};

/** 单次提交保护：同一 code 首次提交返回 true，重复提交返回 false */
const claimAuthCode = (code: string): boolean => {
  if (!code || submittedAuthCode === code) return false;
  submittedAuthCode = code;
  return true;
};

/** 授权码失效：提示可执行动作，并在未用过自动重试时重新发起授权（最多一次） */
const handleAuthCodeExpired = (): void => {
  loading.value = false;
  trackLoginFail('授权码失效');
  if (autoRetryUsed) {
    uni.showToast({ title: AUTH_CODE_EXPIRED_TEXT, icon: 'none', duration: 2500 });
    return;
  }
  autoRetryUsed = true;
  uni.showToast({ title: AUTH_CODE_EXPIRED_TEXT, icon: 'none', duration: 2000 });
  // 失效码由「重新授权」可解，故自动重发起一次；失败仍可由用户点击按钮重试
  setTimeout(() => {
    redirectToFeishuAuth();
  }, 2000);
};

/** 判断错误是否为「飞书授权码无效/过期」（20003）：按错误码识别，不向用户回显错误码原文 */
const isInvalidAuthCodeError = (err: unknown): boolean => {
  const message = (err as { message?: string } | null)?.message || '';
  return message.indexOf(FEISHU_INVALID_CODE) >= 0;
};

const handleFeishuLogin = async () => {
  if (loading.value) return;
  loading.value = true;
    trackLoginClick();
  try {
    if (LOGIN_MODE === 'mock') {
      await mockLogin();
    } else if (!(await feishuOAuthLogin())) {
      // 飞书应用未配置：已提示用户且未跳转，复位按钮态
      loading.value = false;
    }
  } catch (err) {
    console.error('登录失败:', err);
    uni.showToast({ title: '登录失败，请重试', icon: 'none' });
    trackLoginFail('网络异常');
    loading.value = false;
  }
};

const mockLogin = async () => {
  await new Promise(resolve => setTimeout(resolve, 800));
  const res = await request.post('/api/auth/feishu/callback', { code: 'mock_code_001' });
  if (res.code === 0 && res.data?.token) {
    uni.setStorageSync('token', res.data.token);
    uni.setStorageSync('merchant', JSON.stringify(res.data.merchant));
    uni.showToast({ title: '登录成功', icon: 'success' });
    // #FE-25：不再调用 /api/feishu/notify/welcome（本期不给商家发飞书通知）
    trackLoginSuccess();
    setTimeout(() => { uni.reLaunch({ url: '/pages/index/index' }); }, 1000);
  } else {
    uni.showToast({ title: res.message || '登录失败', icon: 'none' });
    loading.value = false;
  }
};

/**
 * 飞书授权登录：带 code 回调则换取 token，否则跳转飞书授权页
 * @description 读到 code 立即从地址栏清除（无论成败），并对同一 code 做单次提交保护。
 */
const feishuOAuthLogin = async (): Promise<boolean> => {
  const code = consumeAuthCode();
  if (code) {
    if (!claimAuthCode(code)) return true; // 同一 code 已提交过：忽略，不重放、不重跳
    await exchangeCodeForToken(code);
    return true;
  }
  return redirectToFeishuAuth();
};

/** 跳转飞书授权页；未配置 app_id 时提示并中止（返回 false），不构造 app_id 空参 URL */
const redirectToFeishuAuth = (): boolean => {
  if (!FEISHU_APP_ID) {
    uni.showToast({ title: FEISHU_APP_ID_MISSING_TEXT, icon: 'none' });
    return false;
  }
  const authUrl = 'https://open.feishu.cn/open-apis/authen/v1/authorize'
    + '?app_id=' + FEISHU_APP_ID
    + '&redirect_uri=' + REDIRECT_URI
    + '&response_type=code';
  window.location.href = authUrl;
  return true;
};

/**
 * 用授权码换取登录态
 * @description 静默请求（silent）：错误提示由本页接管，避免把含飞书错误码的后端 message 直接抛给用户。
 */
const exchangeCodeForToken = async (code: string) => {
  try {
    const res = await request.post('/api/auth/feishu/callback', { code }, { silent: true });
    if (!(res.code === 0 && res.data?.token)) {
      // request 对非 0 会 reject，此分支仅兜底
      loading.value = false;
      uni.showToast({ title: res.message || '登录失败，请重试', icon: 'none' });
      return;
    }
    uni.setStorageSync('token', res.data.token);
    uni.setStorageSync('merchant', JSON.stringify(res.data.merchant));
    uni.showToast({ title: '登录成功', icon: 'success' });

    // #FE-25：不再调用 /api/feishu/notify/welcome（本期不给商家发飞书通知）
    setTimeout(() => { uni.reLaunch({ url: '/pages/index/index' }); }, 1000);
  } catch (err) {
    loading.value = false;
    if (isInvalidAuthCodeError(err)) {
      // 授权码无效/过期（20003）：不回显错误码，改给可执行指引（含最多一次自动重发起）
      handleAuthCodeExpired();
      return;
    }
    // 其它错误：沿用「后端 message 透传」的既有真源策略，不新造语义
    const message = (err as { message?: string } | null)?.message || '登录失败，请重试';
    uni.showToast({ title: message, icon: 'none' });
    trackLoginFail(message);
  }
};

/* ---------------- 手机号 + 短信验证码登录（VITE_LOGIN_MODE=phone） ---------------- */

/** 手机号输入值（只保留数字，最多 11 位） */
const phone = ref('');
/** 验证码输入值（只保留数字，最多 code_length 位） */
const code = ref('');
/** 手机号就地错误提示（空串 = 无错误） */
const phoneError = ref('');
/** 发码请求中（防连点：与既有登录按钮同范式 `if (x) return` + disabled 态） */
const sendLoading = ref(false);
/** 登录请求中 */
const phoneLoading = ref(false);
/** 冷却剩余秒数（唯一来源 = 后端响应 `cooldown_seconds`，前端不硬编码） */
const countdown = ref(0);
/** 倒计时定时器（组件卸载必须清理，禁止常驻） */
let countdownTimer: ReturnType<typeof setInterval> | null = null;

/** 发码按钮是否禁用（请求中或倒计时内） */
const sendDisabled = computed(() => sendLoading.value || countdown.value > 0);

/** 发码按钮文案：发送中… / 重新获取(Ns) / 获取验证码 */
const sendButtonText = computed(() => {
  if (sendLoading.value) return PHONE_SEND_CODE_LOADING_TEXT;
  if (countdown.value > 0) return `${PHONE_RESEND_CODE_TEXT}(${countdown.value}s)`;
  return PHONE_SEND_CODE_TEXT;
});

/** 停止倒计时并清理定时器 */
const stopCountdown = (): void => {
  if (countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
  }
  countdown.value = 0;
};

/** 启动倒计时（秒数来自后端 cooldown_seconds；≤0 视为无需冷却） */
const startCountdown = (seconds: number): void => {
  stopCountdown();
  const total = Number.isFinite(seconds) && seconds > 0 ? Math.floor(seconds) : 0;
  if (total <= 0) return;
  countdown.value = total;
  countdownTimer = setInterval(() => {
    countdown.value -= 1;
    if (countdown.value <= 0) stopCountdown();
  }, 1000);
};

/** 手机号输入：仅数字 + 长度上界；输入即清除就地错误 */
const handlePhoneInput = (e: { detail: { value: string } }): void => {
  phone.value = String(e.detail?.value || '').replace(/\D/g, '').slice(0, PHONE_LENGTH);
  if (phoneError.value) phoneError.value = '';
};

/** 验证码输入：仅数字 + 长度上界 */
const handleCodeInput = (e: { detail: { value: string } }): void => {
  code.value = String(e.detail?.value || '').replace(/\D/g, '').slice(0, PHONE_CODE_LENGTH);
};

/** 手机号就地校验（提交与失焦同口径） */
const validatePhone = (): boolean => {
  if (!PHONE_PATTERN.test(phone.value)) {
    phoneError.value = PHONE_INVALID_TEXT;
    return false;
  }
  phoneError.value = '';
  return true;
};

/**
 * 获取验证码：人机校验接缝 → 发码接口
 * @description 接缝 fail-closed：拿不到校验串就**不发请求**，只提示兜底文案（绝不静默跳过）。
 *              倒计时秒数取后端 `cooldown_seconds`。
 */
const handleSendCode = async (): Promise<void> => {
  if (sendDisabled.value) return;
  if (!validatePhone()) return;
  sendLoading.value = true;
  trackLoginClick();
  try {
    const captchaVerifyParam = await getCaptchaParam();
    const res = await sendPhoneCode(phone.value, captchaVerifyParam);
    startCountdown(Number(res.data?.cooldown_seconds));
    // 验证成功且业务（发码）处理完毕 → 释放验证码实例与事件监听（官方 destroy；幂等）
    destroyCaptcha();
  } catch (err) {
    const errName = (err as Error)?.name;
    if (errName === 'CaptchaCancelledError') {
      // 用户主动取消/未完成：不是组件故障，给准确轻提示；按钮已在 finally 复位，可立即重试
      uni.showToast({ title: CAPTCHA_INCOMPLETE_TEXT, icon: 'none', duration: 2000 });
    } else if (errName === 'CaptchaUnavailableError') {
      // 组件/配置/加载失败、SDK 404、超时：fail-closed 兜底文案（内部原因已由接缝 console.error 记录）
      uni.showToast({ title: CAPTCHA_UNAVAILABLE_TEXT, icon: 'none', duration: 2500 });
    } else {
      // 后端错误（400/403/429/502/503）：一律展示后端 message，前端不新造同义文案
      const message = (err as { message?: string } | null)?.message;
      if (message) uni.showToast({ title: message, icon: 'none', duration: 2500 });
    }
  } finally {
    sendLoading.value = false;
  }
};

/**
 * 手机号 + 验证码登录
 * @description 成功路径沿用既有实现：写 token / merchant → reLaunch 首页；
 *              **不再调用** /api/feishu/notify/welcome（本期不给商家发飞书通知）。
 */
const handlePhoneLogin = async (): Promise<void> => {
  if (phoneLoading.value) return;
  if (!validatePhone()) return;
  if (!code.value) {
    uni.showToast({ title: PHONE_CODE_PLACEHOLDER, icon: 'none' });
    return;
  }
  phoneLoading.value = true;
  trackLoginClick();
  try {
    const res = await phoneLogin(phone.value, code.value);
    uni.setStorageSync('token', res.data.token);
    uni.setStorageSync('merchant', JSON.stringify(res.data.merchant));
    // 登录成功：验证码实例已无用途 → 销毁（官方 destroy；幂等）
    destroyCaptcha();
    uni.showToast({ title: '登录成功', icon: 'success' });
    trackLoginSuccess();
    setTimeout(() => { uni.reLaunch({ url: '/pages/index/index' }); }, 1000);
  } catch (err) {
    // 后端 message 透传（含 400 验证码错误 / 403 禁用 / 429 频控）；网络异常由 request 层提示
    const message = (err as { message?: string } | null)?.message;
    if (message) {
      uni.showToast({ title: message, icon: 'none' });
      trackLoginFail(message);
    }
    phoneLoading.value = false;
  }
};

onMounted(() => {
  trackPageView('login');
  if (LOGIN_MODE !== 'feishu') return;
  // 回调带回授权码：交由 feishuOAuthLogin 统一「读取 → 立即清除 → 单次提交」
  if (new URLSearchParams(window.location.search).get('code')) {
    handleFeishuLogin();
  }
});

onBeforeUnmount(() => stopCountdown());
</script>

<style lang="scss" scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, $u-bg-color 0%, $u-primary-light 100%);
  position: relative;
  overflow: hidden;
}

.login-bg {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
}

.login-bg__circle {
  position: absolute;
  border-radius: 50%;
  opacity: 0.5;
}

.login-bg__circle--1 {
  width: 600rpx;
  height: 600rpx;
  background: radial-gradient(circle, rgba($u-primary, 0.1) 0%, transparent 70%);
  top: -200rpx;
  right: -100rpx;
}

.login-bg__circle--2 {
  width: 400rpx;
  height: 400rpx;
  background: radial-gradient(circle, rgba($u-primary, 0.08) 0%, transparent 70%);
  bottom: -100rpx;
  left: -100rpx;
}

.login-bg__circle--3 {
  width: 300rpx;
  height: 300rpx;
  background: radial-gradient(circle, rgba($u-info, 0.05) 0%, transparent 70%);
  top: 30%;
  left: 20%;
}

.login-card {
  width: 680rpx;
  /* 窄屏兜底：不超过视口 92%，避免 375/414 档横向溢出（设计规范 §5.5） */
  max-width: 92vw;
  box-sizing: border-box;
  background: $u-white;
  border-radius: $up-radius-lg;
  box-shadow: $up-shadow-lg;
  padding: $up-space-10 $up-space-8;
  position: relative;
  z-index: 1;
  /* 卡片入场微动效（0.3s 淡入上移，克制） */
  animation: login-card-in $up-ease-slow ease-out both;
}

.login-card__logo {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: $up-space-10;
}

.login-card__icon {
  width: 120rpx;
  height: 120rpx;
  border-radius: $up-radius-xl;
  background: linear-gradient(135deg, $u-primary 0%, $u-primary-dark 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: $up-space-5;
  box-shadow: 0 8rpx 24rpx rgba($u-primary, 0.3);
}

.login-card__icon-text {
  font-size: 48rpx;
  font-weight: 700;
  color: $u-white;
}

.login-card__title {
  font-size: $up-font-size-h1;
  font-weight: 600;
  color: $u-main-color;
  margin-bottom: $up-space-2;
}

.login-card__subtitle {
  font-size: $up-font-size-body;
  color: $u-tips-color;
}

.login-card__form {
  margin-bottom: $up-space-8;
}

.login-btn {
  width: 100%;
  height: 96rpx;
  border-radius: $up-radius-lg;
  background: linear-gradient(135deg, $u-primary 0%, $u-primary-dark 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: $up-shadow-btn;
  transition: all $up-ease-fast;
  cursor: pointer;
  
  /* H5 hover：主色加深（对应 §3.3 主按钮 hover 态） */
  &:hover:not(.is-loading) {
    background: linear-gradient(135deg, $u-primary-dark 0%, $u-primary-dark 100%);
  }

  &:active:not(.is-loading) {
    transform: scale(0.98);
    box-shadow: 0 2px 8px rgba($u-primary, 0.2);
  }
  
  &.is-loading {
    opacity: 0.7;
    cursor: not-allowed;
  }
}

/* 登录卡片入场：淡入 + 上移（页面级克制动效） */
@keyframes login-card-in {
  from {
    opacity: 0;
    transform: translateY(24rpx);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.login-btn__content,
.login-btn__loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: $up-space-2;
}

.login-btn__icon {
  width: 48rpx;
  height: 48rpx;
  border-radius: $up-radius-sm;
  background: rgba($u-white, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-btn__icon-text {
  font-size: $up-font-size-caption;
  font-weight: 600;
  color: $u-white;
}

.login-btn__text {
  font-size: $up-font-size-body;
  font-weight: 600;
  color: $u-white;
}

.login-btn__spinner {
  width: 32rpx;
  height: 32rpx;
  border: 4rpx solid rgba($u-white, 0.3);
  border-top-color: $u-white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.login-card__tip {
  display: block;
  text-align: center;
  margin-top: $up-space-4;
  font-size: $up-font-size-caption;
  color: $u-tips-color;
}

.login-card__footer {
  text-align: center;
  padding-top: $up-space-6;
  border-top: 1rpx solid $u-border-color;
}

.login-card__copyright {
  font-size: $up-font-size-caption;
  color: $u-light-color;
}

/* ---------------- 手机号 + 短信验证码表单（#FE-25）----------------
   颜色/字号/间距/圆角一律取设计 Token（设计规范 §三），无硬编码色值 */
.phone-login {
  display: flex;
  flex-direction: column;
}

.phone-login__title {
  display: block;
  text-align: center;
  font-size: $up-font-size-h3;
  color: $u-main-color;
  margin-bottom: $up-space-5;
}

.phone-login__field {
  display: flex;
  align-items: center;
  min-height: 88rpx;
  padding: 0 $up-space-4;
  background-color: $u-white;
  border: 1rpx solid $u-border-color;
  border-radius: $up-radius-sm;
  transition: border-color $up-ease-fast;

  &:focus-within {
    border-color: $u-primary;
  }
}

.phone-login__field--code {
  margin-top: $up-space-3;
  padding-right: $up-space-2;
}

.phone-login__input {
  flex: 1;
  /* flex 子项显式 min-width: 0，避免窄视口被内容撑破（设计规范 §5.5） */
  min-width: 0;
  height: 88rpx;
  font-size: $up-font-size-body;
  color: $u-main-color;
}

.phone-login__placeholder {
  font-size: $up-font-size-body;
  color: $u-tips-color;
}

.phone-login__error {
  display: block;
  margin-top: $up-space-2;
  font-size: $up-font-size-caption;
  color: $u-error;
}

.phone-login__send {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  min-height: 64rpx;
  margin-left: $up-space-2;
  padding: 0 $up-space-3;
  background-color: $u-primary-light;
  border-radius: $up-radius-sm;
  transition: opacity $up-ease-fast;

  &.is-disabled {
    opacity: 0.6;
  }
}

.phone-login__send-text {
  font-size: $up-font-size-body-sm;
  color: $u-primary-dark;
}

.phone-login .login-btn {
  margin-top: $up-space-6;
}

/* 移动端主断点（设计规范 §5.3）：卡片内边距收一档，避免窄屏拥挤 */
@media (max-width: 600px) {
  .login-card {
    padding: $up-space-8 $up-space-5;
  }
}
</style>


