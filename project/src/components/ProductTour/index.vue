<template>
  <view v-if="modelValue" class="tour">
    <!-- spotlight 遮罩：无目标（居中引导）时全屏变暗拦截；有目标时仅四周变暗，洞区域透明可点击 -->
    <view v-if="!rect" class="tour__veil" @tap.stop />
    <template v-if="rect">
      <view class="tour__mask" :style="{ top: 0, left: 0, right: 0, height: rect.top + 'px' }" />
      <view class="tour__mask" :style="{ top: rect.bottom + 'px', left: 0, right: 0, height: (winH - rect.bottom) + 'px' }" />
      <view class="tour__mask" :style="{ top: rect.top + 'px', left: 0, width: rect.left + 'px', height: rect.height + 'px' }" />
      <view class="tour__mask" :style="{ top: rect.top + 'px', left: rect.right + 'px', right: 0, height: rect.height + 'px' }" />
      <view class="tour__highlight" :style="{ top: rect.top + 'px', left: rect.left + 'px', width: rect.width + 'px', height: rect.height + 'px' }" />
    </template>

    <!-- tooltip 气泡（ref 用于实测尺寸后视口边界处理） -->
    <view ref="tipEl" class="tour__tip" :style="tipStyle">
      <text class="tour__title">{{ currentStep.title }}</text>
      <text class="tour__text">{{ currentStep.text }}</text>
      <view class="tour__progress">
        <text class="tour__progress-text">{{ current + 1 }} / {{ steps.length }}</text>
      </view>
      <view class="tour__actions">
        <view v-if="current > 0" class="tour__btn tour__btn--ghost" @tap="prev">
          <text class="tour__btn-text">上一步</text>
        </view>
        <view class="tour__btn tour__btn--ghost" @tap="skip">
          <text class="tour__btn-text">跳过</text>
        </view>
        <view class="tour__btn tour__btn--primary" @tap="next">
          <text class="tour__btn-text">{{ isLast ? '完成' : '下一步' }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
/**
 * ProductTour - 通用产品引导（spotlight 高亮 + tooltip 气泡 + 上一步/下一步/跳过）
 * @description 对目标元素（CSS 选择器）加 spotlight 高亮（四周变暗 + 高亮边框），tooltip 显示标题/文案/进度；
 *              无 target 或 focus=false 时居中引导；窗口滚动/尺寸变化重新定位；
 *              完成/跳过时写 localStorage(storageKey) 标记已看（首次进入自动触发的已看判断由调用方负责）。
 *
 * @example
 * <ProductTour v-model="tourActive" :steps="steps" storage-key="stage2_tour_seen" @complete="onComplete" @skip="onSkip" />
 */
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';

export interface TourStep {
  /** 目标元素 CSS 选择器（为空或 focus=false 时居中引导） */
  target?: string;
  /** 标题 */
  title: string;
  /** 文案 */
  text: string;
  /** tooltip 相对目标的位置：top（上方）/ bottom（下方）/ left / right；无 target 时居中 */
  placement?: 'top' | 'bottom' | 'left' | 'right';
  /** 是否 spotlight 聚焦目标（默认 true；false 时即使有 target 也全屏遮罩居中引导） */
  focus?: boolean;
}

interface Props {
  /** 步骤列表 */
  steps: TourStep[];
  /** 是否显示（v-model） */
  modelValue: boolean;
  /** 已看标记 storageKey（完成/跳过时写入 localStorage） */
  storageKey?: string;
}

const props = withDefaults(defineProps<Props>(), {
  storageKey: '',
});
const emit = defineEmits<{
  'update:modelValue': [value: boolean];
  complete: [];
  skip: [];
}>();

const current = ref(0);
const rect = ref<{ top: number; left: number; right: number; bottom: number; width: number; height: number } | null>(null);
const winH = ref(typeof window !== 'undefined' ? window.innerHeight : 0);
const winW = ref(typeof window !== 'undefined' ? window.innerWidth : 0);

const currentStep = computed(() => props.steps[current.value] || { title: '', text: '' });
const isLast = computed(() => current.value >= props.steps.length - 1);

/** 定位目标元素矩形（H5 DOM）；rect 无变化时不触发重渲染 */
function locate() {
  const step = currentStep.value;
  if (!step?.target || step.focus === false) {
    if (rect.value !== null) rect.value = null;
    return;
  }
  const el = document.querySelector(step.target);
  if (!el) {
    if (rect.value !== null) rect.value = null;
    return;
  }
  const r = el.getBoundingClientRect();
  const next = { top: r.top, left: r.left, right: r.right, bottom: r.bottom, width: r.width, height: r.height };
  const cur = rect.value;
  if (
    !cur ||
    cur.top !== next.top ||
    cur.left !== next.left ||
    cur.right !== next.right ||
    cur.bottom !== next.bottom
  ) {
    rect.value = next;
  }
}

/** 即时跟随：MutationObserver 监听目标元素样式/类/子节点变化 → rAF 下一帧重新定位（替代定时轮询，无感知延迟） */
let observer: MutationObserver | null = null;
function observeTarget() {
  disconnectObserver();
  const step = currentStep.value;
  if (!step?.target) return;
  const el = document.querySelector(step.target);
  if (!el) return;
  observer = new MutationObserver(() => {
    // 目标样式/尺寸变化（含展开/收起）→ 下一帧重定位高亮 + tooltip
    requestAnimationFrame(() => {
      locate();
      positionTip();
    });
  });
  observer.observe(el, { attributes: true, attributeFilter: ['style', 'class'], childList: true, subtree: true });
}
function disconnectObserver() {
  if (observer) {
    observer.disconnect();
    observer = null;
  }
}

/** tooltip 定位：贴近目标（上方/下侧/侧边，候选方向 + 避开目标可点击区），
 *  fixed + 渲染后 getBoundingClientRect 实测真实尺寸 + 严格 clamp 到视口四边（安全边距）——绝不超界。 */
const tipEl = ref<HTMLElement | null>(null);
const tipStyle = ref<Record<string, string>>({ position: 'fixed', zIndex: '10' });

/** 解析 tip 真实 DOM：uni-app H5 中 ref 可能是 uni-view 组件实例（非原生元素），取 $el 兜底自身 */
function resolveTipEl(): HTMLElement | null {
  const v = tipEl.value as { $el?: unknown } | HTMLElement | null;
  if (!v) return null;
  const el = (v as { $el?: HTMLElement }).$el ?? v;
  return (el as HTMLElement) || null;
}
const TIP_MARGIN = 12;
/** tooltip 与目标之间预留间隔（不压住目标可点击区） */
const TARGET_GAP = 8;

/** 计算某方向下 tooltip 左上角坐标（位置一律相对目标 rect：left=目标左侧/right=右侧/top=上方/bottom=下方） */
function calcTipPos(p: string, r: { left: number; top: number; right: number; bottom: number; width: number; height: number }, tw: number, th: number) {
  if (p === 'top') return { left: r.left + r.width / 2 - tw / 2, top: r.top - th - TIP_MARGIN };
  if (p === 'left') return { left: r.left - tw - TIP_MARGIN, top: r.top + r.height / 2 - th / 2 };
  if (p === 'right') return { left: r.right + TIP_MARGIN, top: r.top + r.height / 2 - th / 2 };
  return { left: r.left + r.width / 2 - tw / 2, top: r.bottom + TIP_MARGIN };
}

/** 是否完整落在视口内（四边安全边距） */
function inViewport(pos: { left: number; top: number }, tw: number, th: number, vw: number, vh: number) {
  return pos.left >= TIP_MARGIN && pos.left + tw <= vw - TIP_MARGIN && pos.top >= TIP_MARGIN && pos.top + th <= vh - TIP_MARGIN;
}

/** 是否与目标矩形重叠（外扩 TARGET_GAP 间隔；重叠即视为遮挡目标可点击区） */
function overlapsTarget(pos: { left: number; top: number }, tw: number, th: number, r: { left: number; top: number; right: number; bottom: number }) {
  return !(pos.left + tw <= r.left - TARGET_GAP || pos.left >= r.right + TARGET_GAP || pos.top + th <= r.top - TARGET_GAP || pos.top >= r.bottom + TARGET_GAP);
}

/** 测量 tooltip 真实渲染尺寸（getBoundingClientRect 优先；渲染前为 0 时兜底估算，防除零） */
function measureTipSize(): { tw: number; th: number } {
  const el = resolveTipEl();
  if (!el) return { tw: 240, th: 120 };
  const b = el.getBoundingClientRect();
  return { tw: b.width > 0 ? b.width : 240, th: b.height > 0 ? b.height : 120 };
}

function positionTip() {
  const r = rect.value;
  if (!r || !tipEl.value) {
    tipStyle.value = { position: 'fixed', zIndex: '10', top: '50%', left: '50%', transform: 'translate(-50%, -50%)' };
    return;
  }
  // 用真实渲染尺寸计算落点与不相交判断（不再用固定 240×120 估算）
  const { tw, th } = measureTipSize();
  positionTipWithSize(tw, th);
}

/** 核心定位：按给定真实尺寸 tw/th 选「与目标不相交」的落点（候选方向 → clamp 后不相交 → 视口内扫描兜底） */
function positionTipWithSize(tw: number, th: number, skipRecheck = false) {
  const r = rect.value;
  if (!r) return;
  const vw = winW.value;
  const vh = winH.value;
  const prefer = currentStep.value?.placement || 'bottom';
  // 候选顺序：placement 优先，其余按 left/right/top/bottom（去重）
  const order = [prefer, 'left', 'right', 'top', 'bottom'].filter((v, i, arr) => arr.indexOf(v) === i);
  const clampVp = (pos: { left: number; top: number }) => ({
    left: Math.max(TIP_MARGIN, Math.min(pos.left, vw - tw - TIP_MARGIN)),
    top: Math.max(TIP_MARGIN, Math.min(pos.top, vh - th - TIP_MARGIN)),
  });
  const applyTip = (pos: { left: number; top: number }) => {
    tipStyle.value = { position: 'fixed', zIndex: '10', left: pos.left + 'px', top: pos.top + 'px', maxWidth: '70vw' };
  };
  const afterApply = () => {
    if (!skipRecheck) requestAnimationFrame(() => recheckTipBounds());
  };

  // 1) 最高优先级：与目标不相交 + 完整落在视口内（位置 = f(目标 rect)，不遮目标、不超界）
  for (const p of order) {
    const pos = calcTipPos(p, r, tw, th);
    if (!overlapsTarget(pos, tw, th, r) && inViewport(pos, tw, th, vw, vh)) {
      applyTip(pos);
      afterApply();
      return;
    }
  }
  // 2) 次优先级：相对目标 clamp——每方向位置仍以 r 为锚（left 收进视口左、top 仍对齐 r 中线），
  //    选 clamp 后仍与目标不相交的方向（硬性不遮挡，允许贴近视口边）；不引入固定视口坐标
  for (const p of order) {
    const pos = calcTipPos(p, r, tw, th);
    const clamped = clampVp(pos);
    if (!overlapsTarget(clamped, tw, th, r)) {
      applyTip(clamped);
      afterApply();
      return;
    }
  }
  // 3) 极端兜底：所有方向 clamp 后仍相交（目标贴视口边严重）时，
  //    仍以目标为锚——取目标正上方 / 正下方（r 中心 x 对齐，相对目标），
  //    **left 与 top 均完整 clamp 到视口（四边安全边距）**：三条硬约束同时满足——
  //    ①相对目标（位置 = f(r)）②不相交（overlapsTarget 检查）③完整在视口（clamp 数学保证）
  const clampX = (v: number) => Math.max(TIP_MARGIN, Math.min(v, vw - tw - TIP_MARGIN));
  const clampY = (v: number) => Math.max(TIP_MARGIN, Math.min(v, vh - th - TIP_MARGIN));
  const extremeCandidates: Array<{ left: number; top: number }> = [
    { left: clampX(r.left + r.width / 2 - tw / 2), top: clampY(r.top - th - TARGET_GAP) },
    { left: clampX(r.left + r.width / 2 - tw / 2), top: clampY(r.bottom + TARGET_GAP) },
  ];
  for (const pos of extremeCandidates) {
    if (!overlapsTarget(pos, tw, th, r)) {
      applyTip(pos);
      afterApply();
      return;
    }
  }
  // 理论物理极限（目标占满整个视口）：取目标正上方（r 中心 x，完整 clamp 到视口），recheck 兜底；
  // 常规目标（按钮/任务卡）不会触发此分支
  applyTip(extremeCandidates[0]);
  afterApply();
}

/** tooltip 渲染后校正（真实尺寸）：1) 与目标相交 → 用真实尺寸重新定位（选不相交落点）；
 *  2) 超出视口四边 clamp（clamp 若引入相交则同样重定位）；3) 保持原位置不变时不动。
 *  skipRecheck 由本函数触发的重定位调用，避免重入循环 */
function recheckTipBounds() {
  const el = resolveTipEl();
  if (!el || !rect.value) return;
  const b = el.getBoundingClientRect();
  const r = rect.value;
  const tw = b.width > 0 ? b.width : 240;
  const th = b.height > 0 ? b.height : 120;
  const pos = { left: b.left, top: b.top };
  // 真实尺寸与目标相交 → 用真实尺寸重定位（候选方向/扫描落点均以真实尺寸判不相交）
  if (overlapsTarget(pos, tw, th, r)) {
    positionTipWithSize(tw, th, true);
    return;
  }
  // 视口 clamp（安全边距）
  const vw = winW.value;
  const vh = winH.value;
  let left = b.left;
  let top = b.top;
  if (left < TIP_MARGIN) left = TIP_MARGIN;
  if (left + tw > vw - TIP_MARGIN) left = Math.max(TIP_MARGIN, vw - tw - TIP_MARGIN);
  if (top < TIP_MARGIN) top = TIP_MARGIN;
  if (top + th > vh - TIP_MARGIN) top = Math.max(TIP_MARGIN, vh - th - TIP_MARGIN);
  if (left !== b.left || top !== b.top) {
    // clamp 后检查是否与目标相交（clamp 可能推向目标）→ 相交则用真实尺寸重定位
    if (overlapsTarget({ left, top }, tw, th, r)) {
      positionTipWithSize(tw, th, true);
      return;
    }
    tipStyle.value = { position: 'fixed', zIndex: '10', left: left + 'px', top: top + 'px', transform: 'none', maxWidth: '70vw' };
  }
}

/** 目标不在视口时滚动使其可见（居中），下帧重定位（高亮/引导对正） */
function scrollTargetIntoView() {
  const step = currentStep.value;
  if (!step?.target) return;
  const el = document.querySelector(step.target) as HTMLElement | null;
  if (!el) return;
  const r = el.getBoundingClientRect();
  if (r.top < 0 || r.bottom > winH.value || r.left < 0 || r.right > winW.value) {
    el.scrollIntoView({ block: 'center', behavior: 'auto' });
    requestAnimationFrame(() => {
      locate(); // 滚动后 rect 相对视口变化，重定位高亮
      positionTip();
    });
  }
}

function updateWinSize() {
  winH.value = window.innerHeight;
  winW.value = window.innerWidth;
  locate();
  positionTip();
}

function onScroll() {
  locate();
  positionTip();
}

watch(() => props.modelValue, (v) => {
  if (v) {
    current.value = 0;
    nextTickLocate();
    observeTarget(); // 目标样式/尺寸变化即时跟随
  } else {
    disconnectObserver();
    rect.value = null;
  }
});

watch(current, () => {
  scrollTargetIntoView(); // 目标进视口（高亮/引导对正）
  nextTickLocate();
  observeTarget();
});

/** rect 更新后重定位 tooltip（实测尺寸 + 视口边界）；deep 监听确保仅 bottom/height 变化的 rect 更新也触发 */
watch(
  rect,
  () => {
    nextTick(() => positionTip());
  },
  { deep: true },
);

function nextTickLocate() {
  setTimeout(() => locate(), 60);
  setTimeout(() => positionTip(), 80);
}

function markSeen() {
  if (props.storageKey) {
    try { localStorage.setItem(props.storageKey, '1'); } catch { /* ignore */ }
  }
}

function next() {
  if (isLast.value) {
    markSeen();
    emit('complete');
    emit('update:modelValue', false);
  } else {
    current.value += 1;
  }
}

function prev() {
  if (current.value > 0) current.value -= 1;
}

function skip() {
  markSeen();
  emit('skip');
  emit('update:modelValue', false);
}

onMounted(() => {
  if (props.modelValue) nextTickLocate();
  if (typeof window !== 'undefined') {
    window.addEventListener('scroll', onScroll, true);
    window.addEventListener('resize', updateWinSize);
  }
});

onBeforeUnmount(() => {
  disconnectObserver();
  if (typeof window !== 'undefined') {
    window.removeEventListener('scroll', onScroll, true);
    window.removeEventListener('resize', updateWinSize);
  }
});
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.tour {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 10000;
  pointer-events: none;

  /* 全屏变暗层：纯视觉底色（pointer-events:none 不拦截点击；
     四周拦截由 mask 承担，目标洞区域与 tooltip 均可正常点击） */
  &__veil {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: rgba($u-main-color, 0.55);
    pointer-events: none;
  }

  /* 目标四周遮罩：层级 1，拦截四周点击（目标洞区域无遮罩，目标可点击展开） */
  &__mask {
    position: fixed;
    background-color: rgba($u-main-color, 0.55);
    pointer-events: auto;
    z-index: 1;
  }

  /* 目标高亮：无色填充 + inset 内描边（box-shadow 不占布局尺寸，尺寸与目标 rect 完全一致，无溢出），
     圆角 $up-radius-lg 对齐任务块；单一元素精确覆盖目标 */
  &__highlight {
    position: fixed;
    background-color: transparent;
    border-radius: $up-radius-lg;
    box-shadow: inset 0 0 0 2rpx rgba($u-white, 0.7);
    pointer-events: none;
    z-index: 2;
  }

  /* tooltip 气泡：层级最高（10），可正常点击按钮（上一步/下一步/跳过）；
     尺寸收紧（maxWidth ≤340px，文案换行/字号紧凑）以便贴近目标旁放得下、随目标移动 */
  &__tip {
    position: fixed;
    pointer-events: auto;
    background-color: $u-white;
    border-radius: $up-radius-lg;
    box-shadow: $up-shadow-xl;
    padding: $up-space-3 $up-space-4;
    width: auto;
    max-width: min(340px, 78vw);
    z-index: 10;
  }

  &__title {
    display: block;
    font-size: $up-font-size-body-sm;
    font-weight: 600;
    color: $u-main-color;
    margin-bottom: $up-space-1;
  }

  &__text {
    display: block;
    font-size: $up-font-size-caption;
    color: $u-content-color;
    line-height: 1.6;
  }

  &__progress {
    margin-top: $up-space-2;
  }

  &__progress-text {
    font-size: $up-font-size-mini;
    color: $u-tips-color;
  }

  &__actions {
    display: flex;
    gap: $up-space-2;
    margin-top: $up-space-3;
    justify-content: flex-end;
  }

  &__btn {
    padding: $up-space-2 $up-space-4;
    border-radius: $up-radius-sm;
    text-align: center;
    transition: transform $up-ease-fast, background-color $up-ease-fast;

    &:active {
      transform: scale(0.97);
    }

    &--ghost {
      background-color: $u-white;
      border: 1rpx solid $u-border-color;

      .tour__btn-text { color: $u-content-color; }
    }

    &--primary {
      background-color: $u-primary;
      border: 1rpx solid $u-primary;

      .tour__btn-text { color: $u-white; font-weight: 500; }
    }
  }

  &__btn-text {
    font-size: $up-font-size-body-sm;
  }
}
</style>