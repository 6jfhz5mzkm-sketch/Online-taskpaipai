<template>
  <view class="image-skeleton" :style="style">
    <view class="image-skeleton__spinner" />
  </view>
</template>

<script setup lang="ts">
/**
 * ImageSkeleton - 图片加载占位（spinner）
 * @description 浅灰底 + 主色旋转 spinner（CSS 动画），用于 <image> 加载完成前占位；
 *              配合 image 的 @load/@error 显隐切换（见 ProductGuideModal 用法）。
 *
 * @example
 * <ImageSkeleton width="200rpx" height="200rpx" />
 */
interface Props {
  /** 占位块宽度（CSS 尺寸，默认 100%） */
  width?: string;
  /** 占位块高度（CSS 尺寸，默认 100%） */
  height?: string;
  /** 是否为圆形（如头像占位） */
  circle?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  width: '100%',
  height: '100%',
  circle: false,
});

const style = {
  width: props.width,
  height: props.height,
  borderRadius: props.circle ? '9999px' : '',
};
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

/* 占位块：浅灰底（$u-bg-color），居中显示主色旋转 spinner（0.8s 线性循环） */
.image-skeleton {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: $u-bg-color;
  border-radius: $up-radius-sm;

  &__spinner {
    width: 64rpx;
    height: 64rpx;
    border: 6rpx solid $u-border-color;
    border-top-color: $u-primary;
    border-radius: $up-radius-full;
    animation: image-skeleton-spin 0.8s linear infinite;
  }
}

@keyframes image-skeleton-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
