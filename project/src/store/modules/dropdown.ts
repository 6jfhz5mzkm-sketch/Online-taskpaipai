/**
 * 下拉浮层状态管理
 */
import { defineStore } from 'pinia';
import { ref } from 'vue';

/**
 * 下拉浮层（CategorySelectDropdown）的全局展开状态
 * @description 唯一真源：同一时刻全局至多一个浮层展开（跨卡片/跨宿主）。
 *              宿主（TaskCard 等）只读 `activeKey` 推导自己的可见状态，不另存一份 local 副本，
 *              因此「打开另一个 → 前一个自动收起」是状态本身的语义，不需要宿主之间互相通知。
 *              key 约定：`<宿主标识>::<字段>`（如 `<taskId>::category`）。
 */
export const useDropdownStore = defineStore('dropdown', () => {
  /** 当前展开的浮层 key（'' = 全部收起） */
  const activeKey = ref('');

  /** 该 key 是否为当前展开项 */
  const isOpen = (key: string) => activeKey.value === key;

  /** 展开指定浮层（直接覆盖 → 上一个自动收起） */
  const open = (key: string) => {
    activeKey.value = key;
  };

  /** 收起当前浮层（无参：收起「当前展开的那一个」，供遮罩点击等使用） */
  const close = () => {
    activeKey.value = '';
  };

  return { activeKey, isOpen, open, close };
});
