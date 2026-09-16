<!--
  @Component LoadingOverlay
  @Version 1.0.0
  @Description 通用加载遮罩（转圈 + 文案），绝对定位于父容器内；
               用于 Excel 上传与 AI 经营分析等耗时操作（与上传动画一致）。
-->
<template>
  <view class="loading-overlay">
    <view class="loading-overlay__spinner" />
    <text class="loading-overlay__text">{{ text }}</text>
  </view>
</template>

<script setup lang="ts">
interface Props {
  /** 加载提示文案 */
  text?: string;
}

withDefaults(defineProps<Props>(), {
  text: '加载中...',
});
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 10;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: $up-space-3;
  background-color: $u-overlay;
  border-radius: $up-radius-md;

  &__spinner {
    width: 48rpx;
    height: 48rpx;
    border: 4rpx solid $u-primary-light;
    border-top-color: $u-primary;
    border-radius: $up-radius-full;
    animation: loading-overlay-spin 0.8s linear infinite;
  }

  &__text {
    font-size: $up-font-size-body-sm;
    color: $u-white;
    font-weight: 500;
  }
}

@keyframes loading-overlay-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
