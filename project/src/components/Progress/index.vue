<template>
  <view class="progress">
    <!-- 标签区域 -->
    <view v-if="showLabel && (label || percent !== undefined)" class="progress__label">
      <text class="progress__label-text">{{ label || percent + '%' }}</text>
    </view>

    <!-- 进度条轨道 -->
    <view class="progress__track" :class="'progress__track--' + height">
      <view ref="fillRef" class="progress__fill" :class="'progress__fill--' + color" />
    </view>
  </view>
</template>

<script setup lang="ts">
/**
 * Progress - 阶段进度条封装
 * @description 统一进度条：支持百分比/标签/语义色/高度档位，进度推进使用 GSAP scaleX 平滑动画；
 *              百分比数字为等宽数字。兼容既有 ProgressBar 的用法（percent + label）。
 *
 * @example
 * <Progress :percent="68" label="阶段进度 68%" />
 * <Progress :percent="100" color="success" height="thick" />
 */
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { getGsap } from '@/utils/gsap'
const gsap = getGsap()

type ProgressColor = 'primary' | 'success' | 'info' | 'warning' | 'error'
type ProgressHeight = 'thin' | 'normal' | 'thick'

interface Props {
  /** 进度百分比，取值 0 ~ 100 */
  percent: number
  /** 显示在进度条上方的标签文本（缺省显示 percent + '%'） */
  label?: string
  /** 是否显示标签行 */
  showLabel?: boolean
  /** 语义色：primary=主色（默认）/ success / info / warning / error */
  color?: ProgressColor
  /** 高度档位：thin=6rpx / normal=10rpx / thick=16rpx */
  height?: ProgressHeight
}

const props = withDefaults(defineProps<Props>(), {
  label: '',
  showLabel: true,
  color: 'primary',
  height: 'normal',
})

/** 将 percent 限制在 0 ~ 100 范围内 */
const clampedPercent = computed(() => {
  return Math.min(100, Math.max(0, props.percent))
})

const fillRef = ref<HTMLElement | null>(null)
let fillEl: HTMLElement | null = null

onMounted(() => {
  fillEl = (fillRef.value as any)?.$el ?? (fillRef.value as HTMLElement | null)
  if (fillEl) {
    gsap.set(fillEl, { scaleX: clampedPercent.value / 100, transformOrigin: 'left' })
  }
})

onBeforeUnmount(() => {
  if (fillEl) gsap.killTweensOf(fillEl)
})

/** 进度推进：只动 transform（scaleX），约 0.6s 平滑过渡 */
watch(clampedPercent, (val) => {
  if (!fillEl) return
  gsap.to(fillEl, {
    scaleX: val / 100,
    duration: 0.6,
    ease: 'power2.inOut',
    overwrite: 'auto',
  })
})
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.progress {
  width: 100%;

  &__label {
    margin-bottom: $up-space-2;
  }

  &__label-text {
    font-size: $up-font-size-caption;
    color: $u-main-color;
    font-weight: $up-font-weight-medium;
    font-variant-numeric: tabular-nums;
  }

  &__track {
    width: 100%;
    background-color: $u-border-color;
    border-radius: $up-radius-full;
    overflow: hidden;

    &--thin { height: 6rpx; }
    &--normal { height: 10rpx; }
    &--thick { height: 16rpx; }
  }

  &__fill {
    width: 100%;
    height: 100%;
    background-color: $u-primary;
    border-radius: $up-radius-full;
    transform-origin: left;

    /* ---- 语义色（Token）---- */
    &--success { background-color: $u-success; }
    &--info { background-color: $u-info; }
    &--warning { background-color: $u-warning; }
    &--error { background-color: $u-error; }
  }
}
</style>
