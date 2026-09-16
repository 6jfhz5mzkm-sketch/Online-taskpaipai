<!--
  @Component CategorySelectDropdown
  @Version 1.0.0
  @Description 类目选择的通用 dropdown 浮层（单选/多选**共用同一实现**，避免两份重复模板与样式）。
               归属：src/components/CategorySelectDropdown/（全局组件，PascalCase 文件夹 + index.vue）。
               原先位于页面私有目录 components-local/stage2/，#F-27 按开发规则 §三 / §4.3 / §4.4 提升为全局，
               供全局共享组件 components/TaskCard 与阶段二 CategoryPicker 共用（此前已按 §三 判为全局组件不得依赖页面私有目录）。
               层级约定（沿用 #F-23 实测结论）：与宿主 <Modal> 同级渲染（不放在 .modal-card 内，避免被
               卡片 overflow/层叠上下文影响），透明遮罩 z-index 10000 / 面板 z-index 10001，均高于共享
               Modal 的 .modal-overlay(9999)；面板位置由宿主实测（anchor）传入，组件只负责渲染与交互。
               锚点失效保护（#F-27）：打开期间监听 window 的 scroll / resize（捕获阶段，覆盖任意滚动容器），
               一旦滚动或视口变化即 close —— fixed 浮层相对「打开瞬间实测的锚点」定位，滚动后必然与触发器脱节；
               浮层自身子树内的滚动（选项列表 overflow-y: auto）不属于锚点失效，不收起。
                遮罩模式（#F-28-R1）：`maskMode: 'block' | 'passthrough'`，默认 'block'（全视口阻塞遮罩，阶段二弹窗沿用）；
                'passthrough'（任务卡场景）不渲染阻塞遮罩，改用 document 捕获阶段监听做「外部点击收起」，
                点在其它触发器上放行 → 同一次点击即完成「关旧开新」（唯一真源是宿主的单活 store）。
  @Props visible / options / selectedIds / multiple（false=单选选中即收起，true=多选可连续勾选）/ maxCount / anchor
         / maskMode / triggerEl（passthrough 时用于区分「点本实例触发器」与「点外部」）
  @Emits close（遮罩点击或单选选中后收起）/ pick（点击某个选项，由宿主决定选中或 toggle）
  @See project/docs/后端技术方案.md §5.2 API-05 / API-07
-->
<template>
  <view v-if="visible" ref="rootRef" class="category-select">
    <!-- 遮罩（仅 block 模式）：全视口阻塞层，只用于「点击浮层外收起」。
         passthrough 模式不渲染它 —— 由 document 捕获阶段监听做「外部点击收起」，
         点在其它触发器上时放行，让那一击同时完成「关旧 + 开新」（#F-28-R1）。 -->
    <view v-if="maskMode === 'block'" class="category-select__mask" @tap="emit('close')" />
    <view class="category-select__panel" :style="panelStyle">
      <view
        v-for="item in options"
        :key="item.id"
        class="category-select__item"
        :class="{
          'category-select__item--active': isPicked(item.id),
          'category-select__item--blocked': isBlocked(item.id),
        }"
        @tap="emit('pick', String(item.id))"
      >
        <text class="category-select__text">{{ item.name }}</text>
        <text v-if="isPicked(item.id)" class="category-select__mark">✓</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import type { CategoryNode } from '@/api/category';

interface Props {
  /** 浮层是否展开 */
  visible: boolean;
  /** 选项（一级类目或某一级下的二级类目） */
  options: CategoryNode[];
  /** 已选 id（单选至多 1 个；多选 0..maxCount） */
  selectedIds: string[];
  /** false=单选：选中后由宿主收起；true=多选：面板保持展开以便连续勾选 */
  multiple?: boolean;
  /** 多选上界：达到后未选中项按 blocked 样式弱化（点击仍上抛，由宿主给出提示） */
  maxCount?: number;
  /** 面板锚点（宿主实测的选择器矩形：left / 下沿 top / width，单位 px） */
  anchor?: { left: number; top: number; width: number } | null;
  /**
   * 遮罩模式：
   * - `block`（默认，阶段二弹窗）：全视口透明遮罩，点遮罩即收起；遮罩会吃掉其它元素的点击；
   * - `passthrough`（任务卡场景）：不渲染阻塞遮罩，改用 document 捕获阶段监听「外部点击」，
   *   点在其它触发器上时放行，使「关旧开新」在同一次点击内完成。
   */
  maskMode?: 'block' | 'passthrough';
  /** 本实例触发器取值器（仅 passthrough 需要）：用于区分「点本实例触发器（交给它自己 toggle）」与「点外部」 */
  triggerEl?: () => HTMLElement | null;
  /**
   * 「其它下拉触发器」选择器（仅 passthrough 需要，由宿主提供自己全部触发器的合集，如
   * `.category-selector__picker, .fee-selector__picker`）：命中它的外部点击**不吞**，
   * 放行以保留「同一次点击关旧开新」；未命中它的其它外部点击会被吞掉（见 onDocumentClick ④）。
   */
  triggerSelector?: string;
}

const props = withDefaults(defineProps<Props>(), {
  multiple: false,
  maxCount: 3,
  anchor: null,
  maskMode: 'block',
  triggerEl: undefined,
  triggerSelector: '',
});

const emit = defineEmits<{
  /** 收起浮层（遮罩点击 / 单选选中后由宿主决定） */
  close: [];
  /** 点击某个选项（单选=选中并收起；多选=由宿主 toggle） */
  pick: [id: string];
}>();

/** 浮层根节点（用于区分「浮层内部滚动」与「宿主滚动」） */
const rootRef = ref<HTMLElement | null>(null);

/** 面板几何（仅 left/top/width；间距、圆角、阴影、颜色一律在 SCSS 取 Token） */
const panelStyle = computed<Record<string, string>>(() => {
  const box = props.anchor;
  if (!box) return {};
  return {
    left: Math.round(box.left) + 'px',
    top: Math.round(box.top) + 'px',
    width: Math.round(box.width) + 'px',
  };
});

/** 是否已选中（id 统一按字符串比较，避免后端 int/string 形态差异） */
function isPicked(id: unknown): boolean {
  return props.selectedIds.indexOf(String(id)) >= 0;
}

/** 多选达上界后的未选中项：弱化显示（点击仍上抛，由宿主提示数量上限） */
function isBlocked(id: unknown): boolean {
  return props.multiple && props.selectedIds.length >= props.maxCount && !isPicked(id);
}

/**
 * 锚点失效即收起：浮层是 position: fixed，位置来自宿主打开瞬间实测的触发器矩形（anchor），
 * 页面/任意滚动容器滚动或视口尺寸变化后该矩形不再成立（浮层会与触发器脱节）。
 * scroll 事件不冒泡，故用捕获阶段监听 window 以覆盖所有滚动容器（共用组件统一负责，
 * 宿主不必各自实现）。收起通过既有 close 事件上抛，语义与点击遮罩一致。
 */
function closeOnAnchorInvalid(e: Event): void {
  // 面板内部滚动（选项列表 overflow-y: auto）不是锚点失效：捕获阶段监听 window 也会收到
  // 后代元素的 scroll（scroll 不冒泡但会经过捕获路径），故先排除浮层自身子树内的事件。
  const root = ((rootRef.value as { $el?: HTMLElement } | null)?.$el || (rootRef.value as HTMLElement | null)) || null;
  // 注意：window / document 上的 scroll、resize 事件 target 可能是 window（非 Node），
  // root.contains(window) 会抛 TypeError 并被事件分发吞掉 —— 必须先判 instanceof Node。
  const target = e.target as Node | null;
  if (root && target instanceof Node && root.contains(target)) return;
  emit('close');
}

function bindAnchorGuard(bind: boolean): void {
  if (typeof window === 'undefined') return;
  const fn = bind ? window.addEventListener : window.removeEventListener;
  fn.call(window, 'scroll', closeOnAnchorInvalid, true);
  fn.call(window, 'resize', closeOnAnchorInvalid, true);
}

function resolveRoot(): HTMLElement | null {
  return ((rootRef.value as { $el?: HTMLElement } | null)?.$el || (rootRef.value as HTMLElement | null)) || null;
}

/**
 * passthrough 模式的「外部点击」处理：document **捕获阶段** 监听 click，四分支（#F-28-R1 / R2）：
 * ① 目标在浮层（面板）内 → 放行（交给面板项自己的 pick 处理器）；
 * ② 目标是本实例触发器 → 放行（交给它自己 toggle，避免「先收起又被 toggle 打开」）；
 * ③ 目标是**其它下拉触发器** → 先 close（写 store 唯一真源），**不吞**：那一击继续走它自己的 open
 *    （store.open 覆盖式写入）→ 同一次点击完成「关旧开新」；
 * ④ 其余外部点击（页面空白 / 其它卡片 / 侧栏按钮…）→ close **且吞掉该击**
 *    （stopPropagation 在捕获阶段即可阻断后续传播 + preventDefault）：
 *    避免「只想关掉下拉」却误触下层交互 —— 实测误触另一张卡的 checkbox 会切换完成态并触发
 *    POST /api/task/progress（有副作用）。取舍：面板打开时点其它按钮，第一击只收起，需第二击触发原动作。
 * 注意：捕获阶段的 stopPropagation 会阻止事件继续沿传播路径下行，因此目标与冒泡阶段都收不到该 click。
 */
function onDocumentClick(e: Event): void {
  const target = e.target as Node | null;
  if (!target || !(target instanceof Node)) return;
  const root = resolveRoot();
  if (root && root.contains(target)) return; // ①
  const trigger = props.triggerEl ? props.triggerEl() : null;
  if (trigger && trigger.contains(target)) return; // ②
  emit('close');
  const isOtherTrigger =
    !!props.triggerSelector && target instanceof Element && !!target.closest(props.triggerSelector);
  if (isOtherTrigger) return; // ③
  if (e.cancelable) e.preventDefault();
  e.stopPropagation(); // ④
}

function bindDocumentClick(bind: boolean): void {
  if (typeof document === 'undefined') return;
  const fn = bind ? document.addEventListener : document.removeEventListener;
  fn.call(document, 'click', onDocumentClick, true);
}

/** 浮层展开/收起（或遮罩模式切换）时统一装拆监听：锚点失效保护（两种模式）+ 外部点击（仅 passthrough） */
function syncListeners(): void {
  const open = props.visible;
  bindAnchorGuard(open);
  bindDocumentClick(open && props.maskMode === 'passthrough');
}

watch([() => props.visible, () => props.maskMode], syncListeners, { immediate: true });

onBeforeUnmount(() => {
  bindAnchorGuard(false);
  bindDocumentClick(false);
});
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

/* 遮罩：透明，仅用于「点击浮层外收起」；层级高于共享 Modal 的 .modal-overlay(9999) */
.category-select__mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 10000;
}

.category-select__panel {
  position: fixed;
  z-index: 10001;
  margin-top: $up-space-1;
  max-height: 480rpx;
  overflow-y: auto;
  background-color: $u-white;
  border: 1rpx solid $u-border-color;
  border-radius: $up-radius-md;
  box-shadow: $up-shadow-lg;
}

.category-select__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $up-space-3 $up-space-4;
  border-bottom: 1rpx solid $u-border-color;
  transition: background-color $up-ease-fast;

  &:last-child {
    border-bottom: none;
  }

  &:active {
    background-color: $u-primary-light;
  }

  &--active {
    background-color: $u-primary-light;
  }

  &--blocked {
    opacity: 0.5;
  }
}

.category-select__text {
  font-size: $up-font-size-body-sm;
  color: $u-content-color;

  .category-select__item--active & {
    color: $u-primary-dark;
    font-weight: 500;
  }
}

.category-select__mark {
  font-size: $up-font-size-caption;
  color: $u-primary;
}
</style>
