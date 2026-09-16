<!--
  @Component Checkbox
  @Version 1.2.0
  @Description 可复用复选框组件，完全自定义样式。
-->
<template>
  <view class="checkbox-wrap" @tap.stop="handleTap">
    <view
      ref="boxRef"
      class="checkbox-box"
      :class="{ 'is-checked': modelValue, 'is-disabled': disabled }"
    >
      <view v-if="modelValue" class="checkbox-tick">✓</view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { getGsap } from '@/utils/gsap'
const gsap = getGsap()

interface Props {
  modelValue: boolean
  disabled?: boolean
  /** 勾选/取消动画延迟（毫秒），用于整组完成时轻微 stagger */
  tickDelay?: number
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false,
  tickDelay: 0,
})

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const boxRef = ref<HTMLElement | null>(null)
let boxEl: HTMLElement | null = null

onMounted(() => {
  boxEl = (boxRef.value as any)?.$el ?? (boxRef.value as HTMLElement | null)
})

onBeforeUnmount(() => {
  if (boxEl) gsap.killTweensOf(boxEl)
})

/** 勾选/取消弹跳：gsap.fromTo + back.out，tickDelay 用时间线 delay（无 :key 重挂、无 setTimeout）；弹跳提速 1.7x：0.3s / 1.7 ≈ 0.18s */
function animateTick(checked: boolean) {
  if (!boxEl) return
  gsap.timeline({ delay: props.tickDelay / 1000 })
    .fromTo(
      boxEl,
      { scale: checked ? 0.8 : 1.08 },
      { scale: 1, duration: 0.18, ease: 'back.out(1.7)', overwrite: 'auto' },
    )
}

watch(() => props.modelValue, (val) => {
  animateTick(val)
})

function handleTap(): void {
  if (props.disabled) return
  emit('update:modelValue', !props.modelValue)
}
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.checkbox-wrap {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  box-sizing: content-box;
  width: 40rpx;
  height: 40rpx;
  /* 扩大勾选点击区域：padding 覆盖视觉范围，负 margin 抵消布局偏移 */
  padding: $up-space-3;
  margin: calc(#{$up-space-3} * -1);
  position: relative;
  z-index: 1;
  flex-shrink: 0;
}

.checkbox-box {
  width: 40rpx;
  height: 40rpx;
  border-radius: 50%;
  border: 2rpx solid #D1D5DB;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s ease, border-color 0.2s ease;
  box-sizing: border-box;
  
  &.is-checked {
    background-color: #22C55E;
    border-color: #22C55E;
  }
  
  &.is-disabled {
    opacity: 0.4;
  }
}

.checkbox-tick {
  color: #FFFFFF;
  font-size: 20rpx;
  font-weight: 600;
  line-height: 1;
}
</style>
