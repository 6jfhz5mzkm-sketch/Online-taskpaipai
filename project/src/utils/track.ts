/**
 * 埋点工具
 * @description 统一的事件追踪工具，用于记录用户行为
 * @see docs/设计规范.md - 数据埋点规范
 */

import { BASE_URL } from '@/api/request';

/** 事件类型枚举 */
export const EventType = {
  // 页面事件
  PAGE_VIEW: 'page_view',           // 页面访问
  PAGE_LEAVE: 'page_leave',         // 页面离开
  
  // 任务事件
  TASK_VIEW: 'task_view',           // 查看任务
  TASK_EXPAND: 'task_expand',       // 展开任务详情
  TASK_COLLAPSE: 'task_collapse',   // 收起任务详情
  TASK_COMPLETE: 'task_complete',   // 完成任务
  TASK_UNCOMPLETE: 'task_uncomplete', // 取消完成任务
  
  // 类目事件
  CATEGORY_SELECT: 'category_select',     // 选择类目
  SUBCATEGORY_SELECT: 'subcategory_select', // 选择二级类目
  
  // 资费事件
  FEE_VIEW: 'fee_view',             // 查看资费
  FEE_CATEGORY_SELECT: 'fee_category_select', // 选择资费类目
  
  // 登录事件
  LOGIN_CLICK: 'login_click',       // 点击登录
  LOGIN_SUCCESS: 'login_success',   // 登录成功
  LOGIN_FAIL: 'login_fail',         // 登录失败
  
  // 弹窗事件
  MODAL_OPEN: 'modal_open',         // 打开弹窗
  MODAL_CLOSE: 'modal_close',       // 关闭弹窗
  
  // 阶段事件
  STAGE_COMPLETE: 'stage_complete', // 完成阶段
  STAGE_VIEW: 'stage_view',         // 查看阶段
  
  // 飞书事件（预留）
  FEISHU_NOTIFY_SEND: 'feishu_notify_send',   // 发送飞书通知
  FEISHU_NOTIFY_CLICK: 'feishu_notify_click', // 点击飞书通知
  
  // 操作按钮事件
  ACTION_CLICK: 'action_click',       // 点击操作按钮（打开收集表/入驻页面/二维码等） // 点击飞书通知
} as const;

/** 事件类型 */
export type EventType = typeof EventType[keyof typeof EventType];

/** 埋点数据结构 */
export interface TrackEvent {
  event_type: string;
  page_name?: string;
  task_key?: string;
  stage_key?: string;
  element?: string;
  meta?: Record<string, any>;
}

/** 获取当前页面路径 */
function getCurrentPage(): string {
  const pages = getCurrentPages();
  if (pages.length > 0) {
    return pages[pages.length - 1].route || 'unknown';
  }
  return 'unknown';
}

/**
 * 追踪事件
 * @param eventType 事件类型
 * @param options 可选参数
 */
export function trackEvent(
  eventType: EventType,
  options: {
    pageName?: string;
    taskKey?: string;
    stageKey?: string;
    element?: string;
    meta?: Record<string, any>;
  } = {}
) {
  const eventData: TrackEvent = {
    event_type: eventType,
    page_name: options.pageName || getCurrentPage(),
    task_key: options.taskKey,
    stage_key: options.stageKey,
    element: options.element,
    meta: {
      ...options.meta,
      timestamp: Date.now(),
      url: window.location.href,
    },
  };

  // 开发环境打印日志
  if (import.meta.env.DEV) {
    console.log('[埋点]', eventType, eventData);
  }

  // 异步发送到后端（不阻塞主流程）
  sendToBackend(eventData).catch(() => {
    // 发送失败静默处理
  });
}

/**
 * 发送事件到后端
 */
async function sendToBackend(eventData: TrackEvent) {
  try {
    await uni.request({
      url: `${BASE_URL}/api/event/track`,
      method: 'POST',
      header: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${uni.getStorageSync('token') || ''}`,
      },
      data: eventData,
    });
  } catch (err) {
    // 静默处理，不影响用户体验
  }
}

/**
 * 页面访问埋点（在onShow中调用）
 */
export function trackPageView(pageName?: string) {
  trackEvent(EventType.PAGE_VIEW, { pageName });
}

/**
 * 任务完成埋点
 */
export function trackTaskComplete(taskKey: string, stageKey?: string) {
  trackEvent(EventType.TASK_COMPLETE, { taskKey, stageKey });
}

/**
 * 任务展开埋点
 */
export function trackTaskExpand(taskKey: string) {
  trackEvent(EventType.TASK_EXPAND, { taskKey });
}

/**
 * 类目选择埋点
 */
export function trackCategorySelect(categoryName: string, taskId?: string) {
  trackEvent(EventType.CATEGORY_SELECT, {
    taskKey: taskId,
    meta: { category_name: categoryName },
  });
}

/**
 * 登录埋点
 */
export function trackLoginClick() {
  trackEvent(EventType.LOGIN_CLICK, { pageName: 'login' });
}

export function trackLoginSuccess() {
  trackEvent(EventType.LOGIN_SUCCESS, { pageName: 'login' });
}

export function trackLoginFail(error: string) {
  trackEvent(EventType.LOGIN_FAIL, {
    pageName: 'login',
    meta: { error },
  });
}

export default {
  EventType,
  trackEvent,
  trackPageView,
  trackTaskComplete,
  trackTaskExpand,
  trackCategorySelect,
  trackLoginClick,
  trackLoginSuccess,
  trackLoginFail,
};
