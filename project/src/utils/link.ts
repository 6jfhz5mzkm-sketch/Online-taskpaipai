/**
 * 外链打开统一封装（商家端 H5 主线）
 *
 * @description 商家端为 uni-app H5（PC Web + 移动端）；小程序/App 端没有 `window.open`，
 *              故在此用平台条件编译收口，避免各调用点散落裸 `window.open`（非 H5 端会直接报错）。
 *              调用纪律：必须在 tap/click 用户手势的**同步调用栈**内调用——
 *              移动端浏览器会拦截非手势来源的新窗口，任何 await 之后再调用都会被拦。
 *
 * @param url 目标地址；为空/null 时不做任何事（调用方应先用 v-if 决定是否渲染入口）
 * @returns 是否已交给平台打开（非 H5 端恒为 false，调用方可据此自行降级）
 *
 * @example
 * // 模板：v-if="task.actionUrl" 决定渲染；点击处理函数内同步调用
 * function handleTaskAction(task: SecondLevelTask) {
 *   openExternalLink(task.actionUrl);
 * }
 */
export function openExternalLink(url?: string | null): boolean {
  if (!url) return false;

  // #ifdef H5
  if (typeof window !== 'undefined' && typeof window.open === 'function') {
    /* noopener：新窗口拿不到 window.opener，防反向标签劫持（与 IcpFooter 既有外链一致） */
    window.open(url, '_blank', 'noopener');
    return true;
  }
  // #endif

  return false;
}
