<!--
  @Component ProgressBar
  @Version 1.0.0
  @Description 进度条组件，支持百分比填充与可选标签显示。
  @Props percent - 进度百分比 (0-100) | label - 可选标签文本
-->
<template>
  <view class="progress-bar">
    <!-- 标签区域 -->
    <view v-if="label || percent !== undefined" class="progress-bar__label">
      <text class="progress-bar__label-text">{{ label || `${percent}%` }}</text>
    </view>

    <!-- 进度条轨道 -->
    <view class="progress-bar__track">
      <view ref="fillRef" class="progress-bar__fill" />
    </view>
  </view>
</template>

<script setup lang="ts">
/**
 * ProgressBar 组件
 * @description 细长进度条，填充色随 percent 变化并带有平滑过渡动画。
 */
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { getGsap } from '@/utils/gsap'
const gsap = getGsap()

interface Props {
  /** 进度百分比，取值 0 ~ 100 */
  percent: number
  /** 显示在进度条上方的标签文本 */
  label?: string
}

const props = withDefaults(defineProps<Props>(), {
  label: '',
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

/** 进度推进：只动 transform（scaleX），约 0.6s，缓动接近原 cubic-bezier 观感 */
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

.progress-bar {
  width: 100%;

  &__label {
    margin-bottom: $up-space-2;
  }

  &__label-text {
    font-size: 24rpx;
    color: $u-main-color;
    font-weight: 500;
  }

  &__track {
    width: 100%;
    height: 6rpx;
    background-color: $u-border-color;
    border-radius: 3rpx;
    overflow: hidden;
  }

  &__fill {
    width: 100%;
    height: 100%;
    background-color: $u-primary;
    border-radius: 3rpx;
    transform-origin: left;
  }
}
</style>

