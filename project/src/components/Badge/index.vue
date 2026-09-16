<template>
  <view class="badge" :class="['badge--' + type, { 'badge--plain': plain }]">
    <text class="badge__text">{{ text }}</text>
  </view>
</template>

<script setup lang="ts">
/**
 * Badge - 状态徽章
 * @description 胶囊形状态徽章（完成/待办/进行中/已解锁等），配色取自设计规范 §3.4 Tag 语义 Token。
 *
 * @example
 * <Badge type="success" text="已完成" />
 * <Badge type="info" text="进行中" plain />
 */
type BadgeType = 'success' | 'primary' | 'info' | 'warning' | 'error' | 'default'

interface Props {
  /** 徽章语义类型：success=完成 / primary=品牌·已解锁 / info=进行中 / warning=待办 / error=错误 / default=默认 */
  type?: BadgeType
  /** 徽章文字 */
  text: string
  /** 是否简洁模式（无背景色，仅文字 + 边框） */
  plain?: boolean
}

withDefaults(defineProps<Props>(), {
  type: 'default',
  plain: false,
})
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.badge {
  display: inline-flex;
  align-items: center;
  padding: 2rpx $up-space-4;
  border-radius: $up-radius-full;
  border-width: 1rpx;
  border-style: solid;
  font-size: $up-font-size-caption;
  line-height: 1.6;
  white-space: nowrap;

  &__text {
    font-weight: $up-font-weight-medium;
  }

  /* ---- 语义配色（Token）---- */
  &--success {
    background-color: $u-tag-success-bg;
    border-color: $u-tag-success-border;

    .badge__text { color: $u-tag-success-text; }
  }

  &--primary {
    background-color: $u-tag-primary-bg;
    border-color: $u-tag-primary-border;

    .badge__text { color: $u-tag-primary-text; }
  }

  &--info {
    background-color: $u-tag-info-bg;
    border-color: $u-tag-info-border;

    .badge__text { color: $u-tag-info-text; }
  }

  &--warning {
    background-color: $u-tag-warning-bg;
    border-color: $u-tag-warning-border;

    .badge__text { color: $u-tag-warning-text; }
  }

  &--error {
    background-color: $u-tag-error-bg;
    border-color: $u-tag-error-border;

    .badge__text { color: $u-tag-error-text; }
  }

  &--default {
    background-color: $u-tag-default-bg;
    border-color: $u-tag-default-border;

    .badge__text { color: $u-tag-default-text; }
  }

  /* ---- 简洁模式：仅文字 + 边框 ---- */
  &--plain {
    background-color: transparent;
  }
}
</style>
