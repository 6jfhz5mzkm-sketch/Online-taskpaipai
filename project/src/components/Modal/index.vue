<!--
  @Component Modal
  @Version 1.1.0
  @Description 通用模态弹窗组件，支持 v-model 控制显示。
-->
<template>
  <view v-if="visible" class="modal-overlay" @tap="handleOverlayTap">
    <view class="modal-card" :style="{ width }" @tap.stop>
      <view class="modal-card__header">
        <text class="modal-card__title">{{ title }}</text>
        <view class="modal-card__close" @tap="handleClose">
          <text class="modal-card__close-icon">×</text>
        </view>
      </view>
      <view class="modal-card__body">
        <slot />
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { useEscapeClose } from '@/composables/useEscapeClose';

interface Props {
  visible: boolean
  title: string
  width?: string
}

const props = withDefaults(defineProps<Props>(), {
  width: '520rpx',
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

function handleClose(): void {
  emit('update:visible', false)
}

// 通用 Modal 支持 ESC 键关闭（仅可见时生效；卸载时 composable 自动移除监听）
useEscapeClose(() => props.visible, handleClose)

function handleOverlayTap(): void {
  handleClose()
}
</script>

<style lang="scss" scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.modal-card {
  background-color: #ffffff;
  border-radius: 16rpx;
  overflow: hidden;
  max-width: 90vw;

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16rpx 20rpx;
    border-bottom: 1px solid #E2E8F0;
  }

  &__title {
    font-size: 32rpx;
    font-weight: 600;
    color: #1F2937;
  }

  &__close {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 48rpx;
    height: 48rpx;
    border-radius: 50%;
  }

  &__close:active {
    background-color: #F8FAFC;
  }

  &__close-icon {
    font-size: 36rpx;
    color: #9CA3AF;
    line-height: 1;
  }

  &__body {
    padding: 20rpx;
    min-height: 120rpx;
  }
}
</style>
