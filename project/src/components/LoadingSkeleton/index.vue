<template>
  <view class="skeleton">
    <view v-if="avatar" class="skeleton__avatar" :class="{ 'skeleton__item--animated': animated }" />
    <view class="skeleton__body">
      <view v-if="title" class="skeleton__title" :class="{ 'skeleton__item--animated': animated }" />
      <view
        v-for="i in rows"
        :key="i"
        class="skeleton__row"
        :class="{ 'skeleton__item--animated': animated }"
      />
    </view>
  </view>
</template>

<script setup lang="ts">
/**
 * LoadingSkeleton - 通用加载骨架
 * @description 页面/卡片加载中的骨架占位（推广 ImageSkeleton 思路为通用骨架屏）：
 *              浅色底块 + 呼吸闪烁动效，支持头像/标题/多行结构。
 *
 * @example
 * <LoadingSkeleton :rows="3" title />
 * <LoadingSkeleton :rows="2" avatar />
 */
interface Props {
  /** 正文骨架行数（默认 3） */
  rows?: number
  /** 是否显示标题骨架块 */
  title?: boolean
  /** 是否显示左侧头像圆形骨架块 */
  avatar?: boolean
  /** 是否启用闪烁动效（默认开启） */
  animated?: boolean
}

withDefaults(defineProps<Props>(), {
  rows: 3,
  title: false,
  avatar: false,
  animated: true,
})
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.skeleton {
  display: flex;
  gap: $up-space-4;
  padding: $up-space-5;
  background-color: $u-white;
  border: 1rpx solid $u-border-color;
  border-radius: $up-radius-lg;

  &__avatar {
    flex-shrink: 0;
    width: 88rpx;
    height: 88rpx;
    border-radius: $up-radius-full;
    background-color: $u-bg-color;
  }

  &__body {
    flex: 1;
    min-width: 0;
  }

  &__title {
    width: 40%;
    height: 28rpx;
    border-radius: $up-radius-xs;
    background-color: $u-bg-color;
    margin-bottom: $up-space-3;
  }

  &__row {
    width: 100%;
    height: 24rpx;
    border-radius: $up-radius-xs;
    background-color: $u-bg-color;
    margin-bottom: $up-space-3;

    &:last-child {
      width: 70%;
      margin-bottom: 0;
    }
  }

  /* 呼吸闪烁动效（主色低透明度高亮，克制不刺眼） */
  &__item--animated {
    animation: skeleton-blink 1.4s ease-in-out infinite;
  }
}

@keyframes skeleton-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}
</style>
