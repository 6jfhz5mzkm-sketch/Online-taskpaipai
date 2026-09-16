import { onMounted, onBeforeUnmount } from 'vue';

/**
 * useEscapeClose - 弹窗 ESC 键关闭（可复用逻辑）
 *
 * @description 监听 window keydown，按 Escape 且弹窗可见时调用关闭回调；
 *              onMounted 注册、onBeforeUnmount 移除监听（避免泄漏）；
 *              多个弹窗可各自调用本 composable（各实例独立监听，互斥打开时仅可见者响应）。
 *
 * @param enabled 弹窗可见状态函数（仅返回 true 时 ESC 生效；弹窗关闭后不误触发）
 * @param onClose 关闭回调（置弹窗显隐为 false / emit update）
 *
 * @example
 * const visible = ref(false);
 * useEscapeClose(() => visible.value, () => { visible.value = false; });
 */
export function useEscapeClose(enabled: () => boolean, onClose: () => void) {
  function onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape' && enabled()) {
      onClose();
    }
  }

  onMounted(() => window.addEventListener('keydown', onKeydown));
  onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown));
}
