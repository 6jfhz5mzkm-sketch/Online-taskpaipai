<template>
  <!-- visible 由 modelValue 计算而来（v-model 双向绑定），true 显示、false 隐藏 -->
  <view v-if="visible" class="pg-modal" @tap="close">
    <view class="pg-modal__box" @tap.stop>
      <view class="pg-modal__header">
        <text class="pg-modal__title">{{ title || '图片示例' }}</text>
        <text class="pg-modal__close" @tap="close">×</text>
      </view>

      <view v-if="images.length === 0" class="pg-modal__empty">
        <text class="pg-modal__empty-text">暂无图片示例</text>
      </view>

      <!-- 大图展示区：一次展示一张（扑克牌卡片切换；切换时本图滑出层与新图滑入同帧衔接，无间隙） -->
      <view v-else class="pg-modal__stage">
        <!-- 本图滑出层：切换时存在，CSS animation 向切换方向滑出（下一张左滑出/上一张右滑出） -->
        <view
          v-if="leaving"
          :key="leaving.src"
          class="pg-modal__slide pg-modal__slide--leave"
          :class="leaving.sign === -1 ? 'pg-modal__slide--leave-left' : 'pg-modal__slide--leave-right'"
        >
          <image class="pg-modal__img" :src="leaving.src" mode="aspectFit" />
        </view>

        <view
          :key="currentIdx"
          class="pg-modal__slide"
          :class="enterClass"
          :style="{ transform: slideTransform, transition: slideTransition }"
          @touchstart="onTouchStart"
          @touchmove="onTouchMove"
          @touchend="onTouchEnd"
          @mousedown="onMouseDown"
          @mousemove="onMouseMove"
          @mouseup="onMouseUp"
          @mouseleave="onMouseUp"
        >
          <!-- 图片始终挂载（关键：@load/@error 依赖 image 渲染触发；
               若 v-if 仅在 loaded 时渲染 image 会死锁在 loading 一直显示占位）。
               未拖拽时点击放大查看（previewImage）。 -->
          <image
            :key="currentSrc + attempt"
            class="pg-modal__img"
            :style="imgStyle"
            :src="currentSrc"
            mode="aspectFit"
            @load="onLoad(currentSrc)"
            @error="onError(currentSrc)"
          />
          <!-- 覆盖层：加载中 spinner 占位（图片上方） -->
          <ImageSkeleton v-if="imgStatus(currentSrc) === 'loading'" class="pg-modal__skeleton" />
          <!-- 覆盖层：加载失败占位 + 点击重试 -->
          <view
            v-else-if="imgStatus(currentSrc) === 'error'"
            class="pg-modal__error"
            @tap.stop="retry(currentSrc)"
          >
            <text class="pg-modal__error-text">图片加载失败</text>
            <text class="pg-modal__retry-text">点击重试</text>
          </view>
        </view>

        <!-- 左右切换按钮（多图显示；首/尾对应方向不渲染） -->
        <view
          v-if="images.length > 1 && currentIdx > 0"
          class="pg-modal__nav pg-modal__nav--prev"
          @tap.stop="goPrev"
        >
          <text class="pg-modal__nav-text">‹</text>
        </view>
        <view
          v-if="images.length > 1 && currentIdx < images.length - 1"
          class="pg-modal__nav pg-modal__nav--next"
          @tap.stop="goNext"
        >
          <text class="pg-modal__nav-text">›</text>
        </view>

        <!-- 分页角标：第 x / N 张（多图显示） -->
        <view v-if="images.length > 1" class="pg-modal__pager">
          <text class="pg-modal__pager-text">第 {{ currentIdx + 1 }} / {{ images.length }} 张</text>
        </view>

        <!-- 缩放工具：图片加载完成后显示，缩小/放大（0.5x~3x 步进 0.25x） -->
        <view v-if="imgStatus(currentSrc) === 'loaded'" class="pg-modal__zoom">
          <view class="pg-modal__zoom-btn" @tap.stop="zoomOut">
            <text class="pg-modal__zoom-text">－</text>
          </view>
          <text class="pg-modal__zoom-scale">{{ zoomPercent }}%</text>
          <view class="pg-modal__zoom-btn" @tap.stop="zoomIn">
            <text class="pg-modal__zoom-text">＋</text>
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { reactive, ref, computed, watch, nextTick, getCurrentInstance } from 'vue';
import ImageSkeleton from './ImageSkeleton.vue';
import { useEscapeClose } from '@/composables/useEscapeClose';

/**
 * ProductGuideModal - 商品发布任务图片示例弹窗
 * @description 大图展示 + 扑克牌卡片切换（左右按钮 / 拖拽切换，不足阈值回弹、超阈值滑动切换 + 新图滑入）；
 *              图片始终挂载以触发 @load/@error（避免 v-if 死锁一直显示占位），加载中覆盖层为 spinner 占位、
 *              失败显示占位可重试；图片支持缩放（0.5x~3x 步进 0.25x），放大态拖拽平移查看细节（边界约束）、
 *              非缩放态拖拽为扑克牌切换；ESC 键关闭弹窗；未拖拽时点击图片调用 uni.previewImage 放大查看；
 *              单图任务不显示切换按钮与分页。
 *
 * @example
 * <ProductGuideModal v-model="visible" :images="['/static/.../a.png']" title="任务标题" />
 */
interface Props {
  /** 是否显示弹窗（v-model） */
  modelValue: boolean;
  /** 图片路径数组（多图扑克牌切换） */
  images: string[];
  /** 弹窗标题（默认「图片示例」） */
  title?: string;
}

const props = withDefaults(defineProps<Props>(), {
  title: '图片示例',
});

const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>();

/** 弹窗可见性：由 v-model（modelValue）驱动（模板 v-if="visible"） */
const visible = computed(() => props.modelValue);

/** 每张图加载状态：loading 加载中（spinner） | loaded 完成 | error 失败（可重试） */
interface ImgState {
  status: 'loading' | 'loaded' | 'error';
}
const imgState = reactive<Record<string, ImgState>>({});
/** 重试计数：变化时 image :key 重建，强制重新加载 */
const attempt = ref(0);

/** 图片状态兜底：未初始化按 loading（保证打开/切换时必然先显示占位） */
function imgStatus(src: string): 'loading' | 'loaded' | 'error' {
  return imgState[src]?.status || 'loading';
}

/** 当前展示索引（扑克牌切换） */
const currentIdx = ref(0);
const currentSrc = computed(() => props.images[currentIdx.value] || '');

/* ---------- 缩放（0.5x~3x，步进 0.25x）+ 放大态拖拽平移（查看细节） ----------
 *  transform 组合：translate(panX,panY) scale(z) —— translate 在前不被 scale 放大，视觉 1:1 跟随；
 *  平移边界：图片内容放大后每边溢出 (z-1)*stage/2，clamp 到该范围 */
const ZOOM_MIN = 0.5;
const ZOOM_MAX = 3;
const ZOOM_STEP = 0.25;
const zoomScale = ref(1);
const zoomPercent = computed(() => Math.round(zoomScale.value * 100));

/** 放大态拖拽平移偏移（px）与平移状态 */
const panOffset = ref({ x: 0, y: 0 });
const panning = ref(false);
let panStart = { x: 0, y: 0 };
let panDragStart = { x: 0, y: 0 };
/** stage 可视区尺寸（弹窗打开时测量，用于平移边界 clamp） */
const stageSize = ref({ width: 0, height: 0 });

const imgStyle = computed(() => {
  const idle = zoomScale.value === 1 && panOffset.value.x === 0 && panOffset.value.y === 0;
  if (idle && !dragging.value && !panning.value) {
    return undefined;
  }
  // 拖拽/平移中 transition:none 实时跟手（不延迟）；松手后恢复 §3.10 $up-ease-normal（回弹/缩放平滑）
  const transition =
    dragging.value || panning.value ? 'none' : `transform ${SWIPE_EASE_NORMAL}`;
  return {
    transform: `translate(${panOffset.value.x}px, ${panOffset.value.y}px) scale(${zoomScale.value})`,
    transition,
  };
});

/** 测量大图展示区尺寸（弹窗显示后执行） */
function measureStage() {
  uni
    .createSelectorQuery()
    .in(getCurrentInstance()?.proxy)
    .select('.pg-modal__stage')
    .boundingClientRect((rect) => {
      if (rect) {
        stageSize.value = {
          width: (rect as { width: number }).width,
          height: (rect as { height: number }).height,
        };
      }
    })
    .exec();
}

/** 平移边界约束：|pan| ≤ (zoom-1)*stage/2（图片内容边缘不越出可视区） */
function clampPan() {
  const maxX = Math.max(0, ((zoomScale.value - 1) * stageSize.value.width) / 2);
  const maxY = Math.max(0, ((zoomScale.value - 1) * stageSize.value.height) / 2);
  panOffset.value = {
    x: Math.min(maxX, Math.max(-maxX, panOffset.value.x)),
    y: Math.min(maxY, Math.max(-maxY, panOffset.value.y)),
  };
}

function zoomIn() {
  zoomScale.value = Math.min(ZOOM_MAX, +(zoomScale.value + ZOOM_STEP).toFixed(2));
  clampPan(); // 缩放后约束平移边界
}
function zoomOut() {
  zoomScale.value = Math.max(ZOOM_MIN, +(zoomScale.value - ZOOM_STEP).toFixed(2));
  clampPan();
}

/* ---------- 拖拽切换（扑克牌卡片：拖动跟随、不足回弹、超阈值滑动切换 + 新图滑入） ---------- */
const SWIPE_THRESHOLD = 60; // 松手判定阈值 px
/** §3.10 过渡动效 Token（script 无法引用 SCSS 变量，取与 Token 等值的字面量）：
 *  $up-ease-normal = 0.2s cubic-bezier(0.4,0,0.2,1) —— 滑动切换滑出
 *  $up-ease-bounce = 0.4s cubic-bezier(0.34,1.56,0.64,1) —— 拖拽不足回弹（弹性）
 */
const SWIPE_EASE_NORMAL = '0.2s cubic-bezier(0.4, 0, 0.2, 1)';
const SWIPE_EASE_BOUNCE = '0.4s cubic-bezier(0.34, 1.56, 0.64, 1)';
const dragOffset = ref(0); // 拖动中实时 px 偏移
const dragging = ref(false);
/** 切换动画进行中（互斥：动画未完成忽略新切换请求，防连点跳图） */
const swipeAnimating = ref(false);
/** 本图滑出层（切换时存在）：{ src 本图路径, sign 滑出方向 -1 左 / +1 右 } */
const leaving = ref<{ src: string; sign: number } | null>(null);
const enterDir = ref(0); // 新图进入方向（1 从右进 / -1 从左进 / 0 无动画）

/** 打开弹窗或切换图片集：重置索引、缩放/平移与全部图片加载状态
 *  （置于 leaving/swipeAnimating 等依赖声明之后，避免 immediate 回调 TDZ ReferenceError） */
watch(
  () => [props.modelValue, props.images] as const,
  () => {
    currentIdx.value = 0;
    zoomScale.value = 1;
    panOffset.value = { x: 0, y: 0 };
    panning.value = false;
    leaving.value = null;
    swipeAnimating.value = false;
    attempt.value = 0;
    for (const src of props.images) {
      imgState[src] = { status: 'loading' };
    }
    if (props.modelValue) {
      nextTick(() => measureStage()); // 弹窗显示后测量 stage，供平移边界使用
    }
  },
  { immediate: true },
);
let dragStartX = 0;
let lastTouchEnd = 0; // 防触屏 synthetic mouse 事件干扰

/* slide 位移：仅拖拽切换模式使用（拖动跟随/松手回弹）；切出由 leaving 层 CSS 动画承担 */
const slideTransform = computed(() =>
  dragging.value ? `translateX(${dragOffset.value}px)` : 'translateX(0)',
);
const slideTransition = computed(() =>
  dragging.value ? 'none' : `transform ${SWIPE_EASE_BOUNCE}`, // 拖拽不足回弹，弹性（§3.10 bounce）
);

/** 新图滑入动画 class（slide :key 重建时播放一次） */
const enterClass = computed(() => {
  if (enterDir.value === 1) return 'pg-modal__slide--enter-right';
  if (enterDir.value === -1) return 'pg-modal__slide--enter-left';
  return '';
});

function getClientX(e: unknown): number {
  const ev = e as { touches?: Array<{ clientX: number }>; changedTouches?: Array<{ clientX: number }>; clientX?: number };
  const touch = ev.touches?.[0] ?? ev.changedTouches?.[0];
  return touch ? touch.clientX : (ev.clientX ?? 0);
}

function getClientY(e: unknown): number {
  const ev = e as { touches?: Array<{ clientY: number }>; changedTouches?: Array<{ clientY: number }>; clientY?: number };
  const touch = ev.touches?.[0] ?? ev.changedTouches?.[0];
  return touch ? touch.clientY : (ev.clientY ?? 0);
}

function onDragStart(e: unknown) {
  if (props.images.length <= 1 || swipeAnimating.value) return;
  // 缩放态（zoomScale>1）→ 拖拽平移图片查看细节；非缩放态 → 扑克牌切换
  if (zoomScale.value > 1) {
    panning.value = true;
    enterDir.value = 0;
    panDragStart = { x: getClientX(e), y: getClientY(e) };
    panStart = { ...panOffset.value };
    return;
  }
  dragging.value = true;
  enterDir.value = 0; // 移除进入动画，避免动画 transform 覆盖拖拽
  dragStartX = getClientX(e);
  dragOffset.value = 0;
}

function onDragMove(e: unknown) {
  if (panning.value) {
    panOffset.value = {
      x: panStart.x + (getClientX(e) - panDragStart.x),
      y: panStart.y + (getClientY(e) - panDragStart.y),
    };
    return;
  }
  if (!dragging.value) return;
  dragOffset.value = getClientX(e) - dragStartX;
}

function onDragEnd() {
  // 平移分支：边界约束后结束（未移动视为点击放大查看）
  if (panning.value) {
    const movedX = Math.abs(panOffset.value.x - panStart.x);
    const movedY = Math.abs(panOffset.value.y - panStart.y);
    panning.value = false;
    clampPan();
    if (movedX < 5 && movedY < 5) {
      preview(currentIdx.value);
    }
    return;
  }
  if (!dragging.value) return;
  const offset = dragOffset.value;
  const wasTap = Math.abs(offset) < 5;
  dragging.value = false;
  dragOffset.value = 0;

  if (wasTap) {
    // 未发生实质拖拽 → 视为点击，放大查看
    preview(currentIdx.value);
    return;
  }
  const next = currentIdx.value + (offset > 0 ? -1 : 1);
  if (Math.abs(offset) >= SWIPE_THRESHOLD && next >= 0 && next < props.images.length) {
    swipeTo(next);
  }
  // 不足阈值或到边界 → 回弹（slideTransform 回 0，transition 生效）
}

/** 切换图片（双图同屏衔接）：本图进入滑出层（CSS animation ±100% 滑出），
 *  目标图同帧成为当前（slide :key 重建，从对侧 ±100% 滑入）——同一指令内连续动画，无两段式间隙。
 *  方向语义（同向推牌）：
 *  - 下一张（sign=+1）：本图向左滑出（--leave-left），新图从右侧滑入（enterDir=+1 → pg-slide-in-right）
 *  - 上一张（sign=-1）：本图向右滑出（--leave-right），新图从左侧滑入（enterDir=-1 → pg-slide-in-left）
 *  互斥：swipeAnimating 期间忽略新切换请求，避免连点跳图 */
function swipeTo(next: number) {
  if (swipeAnimating.value) return; // 切换动画进行中，忽略本次请求
  const sign = next > currentIdx.value ? 1 : -1;
  swipeAnimating.value = true;
  leaving.value = { src: currentSrc.value, sign: -sign }; // 本图滑出方向（下一张向左）
  currentIdx.value = next; // 目标图成为当前（触发 slide :key 重建 + 滑入动画）
  enterDir.value = sign; // 新图滑入方向（下一张从右进）
  zoomScale.value = 1; // 切换后重置缩放
  panOffset.value = { x: 0, y: 0 }; // 重置平移
  // 动画时长与 $up-ease-normal（0.2s）一致；结束后清理滑出层并解除互斥
  setTimeout(() => {
    leaving.value = null;
    swipeAnimating.value = false;
  }, 200);
}

function onTouchStart(e: unknown) {
  onDragStart(e);
}
function onTouchMove(e: unknown) {
  onDragMove(e);
}
function onTouchEnd() {
  lastTouchEnd = Date.now();
  onDragEnd();
}

function onMouseDown(e: unknown) {
  if (Date.now() - lastTouchEnd < 300) return; // 忽略触屏 synthetic mouse
  onDragStart(e);
}
function onMouseMove(e: unknown) {
  onDragMove(e);
}
function onMouseUp() {
  onDragEnd();
}

function goPrev() {
  if (currentIdx.value > 0) swipeTo(currentIdx.value - 1);
}
function goNext() {
  if (currentIdx.value < props.images.length - 1) swipeTo(currentIdx.value + 1);
}

function close() {
  emit('update:modelValue', false);
}

// ESC 键关闭（复用 useEscapeClose：仅弹窗可见时生效，卸载自动移除监听）
useEscapeClose(() => visible.value, close);

function onLoad(src: string) {
  imgState[src].status = 'loaded';
}

function onError(src: string) {
  imgState[src].status = 'error';
}

/** 失败重试：状态置回 loading，attempt 递增强制 image 重建重新加载 */
function retry(src: string) {
  imgState[src].status = 'loading';
  attempt.value++;
}

/** 点击放大查看（仅未拖拽时触发；uni 原生预览，支持多图与缩放） */
function preview(current: number) {
  uni.previewImage({
    urls: props.images,
    current,
  });
}
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.pg-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: $up-space-6;
  background-color: $u-overlay;

  /* 弹窗：横向长方形（3:2），约 2160×1440rpx 基准，视口内等比缩放；模态框阴影 §3.9 $up-shadow-xl */
  &__box {
    width: min(2160rpx, 94vw, 129vh);
    aspect-ratio: 3 / 2;
    display: flex;
    flex-direction: column;
    background-color: $u-white;
    border-radius: $up-radius-lg;
    box-shadow: $up-shadow-xl;
    overflow: hidden;
  }

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: $up-space-4 $up-space-5;
    border-bottom: 1rpx solid $u-border-color;
  }

  &__title {
    flex: 1;
    min-width: 0;
    font-size: $up-font-size-h3;
    font-weight: 600;
    color: $u-main-color;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  &__close {
    flex-shrink: 0;
    margin-left: $up-space-3;
    font-size: $up-font-size-h2;
    color: $u-tips-color;
    line-height: 1;
  }

  &__empty {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  &__empty-text {
    font-size: $up-font-size-body-sm;
    color: $u-tips-color;
  }

  /* 大图展示区：flex:1 占满剩余高度，溢出隐藏（滑动/回弹动画裁剪） */
  &__stage {
    position: relative;
    flex: 1;
    min-height: 0;
    overflow: hidden;
    background-color: $u-bg-color;
  }

  &__slide {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    will-change: transform;

    /* 切换后新图滑入动画（slide :key 重建时播放一次，全宽 ±100% 推入）；
       时长/缓动与 §3.10 $up-ease-normal 一致 */
    &--enter-right {
      animation: pg-slide-in-right 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }

    &--enter-left {
      animation: pg-slide-in-left 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }

    /* 本图滑出层（切换时存在）：CSS animation 向切换方向滑出，forwards 保持终态，
       与新图滑入同帧衔接（双图同屏，无间隙）；z-index 置于新图之上 */
    &--leave {
      z-index: 2;
      pointer-events: none;
    }

    &--leave-left {
      animation: pg-slide-out-left 0.2s cubic-bezier(0.4, 0, 0.2, 1) forwards;
    }

    &--leave-right {
      animation: pg-slide-out-right 0.2s cubic-bezier(0.4, 0, 0.2, 1) forwards;
    }
  }

  /* 图片：始终挂载以触发 @load/@error；缩放 transform 作用于自身，不影响 slide 位移 */
  &__img {
    width: 100%;
    height: 100%;
    border-radius: $up-radius-sm;
    transition: transform $up-ease-normal;
  }

  /* 覆盖层：加载中 spinner 占位（ImageSkeleton），绝对定位覆盖在图片上方 */
  &__skeleton {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    width: 100%;
    height: 100%;
  }

  /* 覆盖层：加载失败占位 */
  &__error {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background-color: $u-bg-color;
    border-radius: $up-radius-sm;
  }

  &__error-text {
    font-size: $up-font-size-caption;
    color: $u-tips-color;
  }

  &__retry-text {
    margin-top: $up-space-1;
    font-size: $up-font-size-mini;
    color: $u-primary;
  }

  /* 左右切换按钮：白底圆形 + 阴影 + 主色图标（§3.3 幽灵/次按钮语言），hover/active 浅绿反馈（§3.5） */
  &__nav {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    z-index: 2;
    width: 72rpx;
    height: 72rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: $u-white;
    border-radius: $up-radius-full;
    box-shadow: $up-shadow-md;
    transition: background-color $up-ease-normal;

    &:active {
      background-color: $u-primary-light;
    }

    &--prev {
      left: $up-space-3;
    }

    &--next {
      right: $up-space-3;
    }
  }

  &__nav-text {
    font-size: $up-font-size-h1;
    color: $u-primary;
    line-height: 1;
    margin-top: -2rpx;
  }

  /* 分页角标：底部居中胶囊 */
  &__pager {
    position: absolute;
    left: 50%;
    bottom: $up-space-3;
    transform: translateX(-50%);
    z-index: 2;
    padding: 4rpx 16rpx;
    background-color: $u-overlay;
    border-radius: $up-radius-full;
  }

  &__pager-text {
    font-size: $up-font-size-mini;
    color: $u-white;
    font-weight: 500;
  }

  /* 缩放工具：图片加载完成后显示，底部右侧（缩小/放大按钮 + 百分比） */
  &__zoom {
    position: absolute;
    right: $up-space-3;
    bottom: $up-space-3;
    z-index: 2;
    display: flex;
    align-items: center;
    gap: $up-space-2;
    padding: $up-space-1 $up-space-2;
    background-color: $u-white;
    border-radius: $up-radius-full;
    box-shadow: $up-shadow-md;
  }

  &__zoom-btn {
    width: 48rpx;
    height: 48rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: $u-white;
    border-radius: $up-radius-full;
    transition: background-color $up-ease-normal;

    &:active {
      background-color: $u-primary-light;
    }
  }

  &__zoom-text {
    font-size: $up-font-size-body;
    color: $u-primary;
    font-weight: 600;
    line-height: 1;
  }

  &__zoom-scale {
    min-width: 72rpx;
    text-align: center;
    font-size: $up-font-size-mini;
    color: $u-content-color;
    font-weight: 500;
  }
}

/* 窄视口（<400px）：缩放工具与分页角标错开，避免底部拥挤/重叠（分页上移、缩放收紧贴边） */
@media (max-width: 400px) {
  .pg-modal__pager {
    bottom: $up-space-8;
  }

  .pg-modal__zoom {
    right: $up-space-2;
    padding: 2rpx $up-space-1;
  }

  .pg-modal__zoom-btn {
    width: 40rpx;
    height: 40rpx;
  }

  .pg-modal__zoom-scale {
    min-width: 56rpx;
  }
}

/* 新图滑入动画（全宽推入，与本图滑出同帧衔接） */
@keyframes pg-slide-in-right {
  from {
    transform: translateX(100%);
  }
  to {
    transform: translateX(0);
  }
}

@keyframes pg-slide-in-left {
  from {
    transform: translateX(-100%);
  }
  to {
    transform: translateX(0);
  }
}

/* 本图滑出动画（双图同屏：本图滑出 + 新图滑入同帧进行） */
@keyframes pg-slide-out-left {
  from {
    transform: translateX(0);
  }
  to {
    transform: translateX(-100%);
  }
}

@keyframes pg-slide-out-right {
  from {
    transform: translateX(0);
  }
  to {
    transform: translateX(100%);
  }
}
</style>
