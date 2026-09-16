<template>
  <view class="stat-card" :class="'stat-card--' + color">
    <view v-if="icon" class="stat-card__icon">
      <text class="stat-card__icon-text">{{ icon }}</text>
    </view>
    <view class="stat-card__body">
      <text class="stat-card__label">{{ label }}</text>
      <view class="stat-card__value-row">
        <text class="stat-card__value">{{ value }}</text>
        <text v-if="unit" class="stat-card__unit">{{ unit }}</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
/**
 * StatCard - 指标卡
 * @description 数据看板/进度页的数值展示卡片，移动端自适应；数值使用等宽数字（tabular-nums）避免跳动。
 *
 * @example
 * <StatCard label="总体进度" value="68" unit="%" color="primary" />
 */
type StatColor = 'primary' | 'success' | 'info' | 'warning' | 'error' | 'default'

interface Props {
  /** 指标名称 */
  label: string
  /** 指标数值（string | number） */
  value: string | number
  /** 数值单位（如 % / 元 / 个） */
  unit?: string
  /** 语义色：primary=主色 / success / info / warning / error / default */
  color?: StatColor
  /** 图标（emoji 文本，可选） */
  icon?: string
}

withDefaults(defineProps<Props>(), {
  unit: '',
  color: 'primary',
  icon: '',
})
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.stat-card {
  display: flex;
  align-items: center;
  gap: $up-space-4;
  padding: $up-space-5;
  background-color: $u-white;
  border: 1rpx solid $u-border-color;
  border-radius: $up-radius-lg;
  box-shadow: $up-shadow-sm;
  transition: box-shadow $up-ease-fast, transform $up-ease-fast;

  &:active {
    transform: scale(0.98);
  }

  &__icon {
    flex-shrink: 0;
    width: 88rpx;
    height: 88rpx;
    border-radius: $up-radius-md;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: $up-font-size-h2;
  }

  &__body {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: $up-space-1;
  }

  &__label {
    font-size: $up-font-size-caption;
    color: $u-tips-color;
    line-height: 1.4;
  }

  &__value-row {
    display: flex;
    align-items: baseline;
    gap: $up-space-1;
  }

  &__value {
    font-size: $up-font-size-h1;
    font-weight: $up-font-weight-bold;
    color: $u-main-color;
    line-height: 1.2;
    /* 等宽数字：数值变化不跳动 */
    font-variant-numeric: tabular-nums;
  }

  &__unit {
    font-size: $up-font-size-caption;
    color: $u-content-color;
  }

  /* ---- 语义色（Token）---- */
  &--primary {
    .stat-card__icon { background-color: $u-primary-light; }
    .stat-card__icon-text { color: $u-primary-dark; }
    .stat-card__value { color: $u-primary-dark; }
  }

  &--success {
    .stat-card__icon { background-color: $u-success-light; }
    .stat-card__icon-text { color: $u-success-dark; }
    .stat-card__value { color: $u-success-dark; }
  }

  &--info {
    .stat-card__icon { background-color: $u-info-light; }
    .stat-card__icon-text { color: $u-info-dark; }
    .stat-card__value { color: $u-info-dark; }
  }

  &--warning {
    .stat-card__icon { background-color: $u-warning-light; }
    .stat-card__icon-text { color: $u-warning-dark; }
    .stat-card__value { color: $u-warning-dark; }
  }

  &--error {
    .stat-card__icon { background-color: $u-error-light; }
    .stat-card__icon-text { color: $u-error-dark; }
    .stat-card__value { color: $u-error-dark; }
  }

  &--default {
    .stat-card__icon { background-color: $u-bg-color; }
    .stat-card__icon-text { color: $u-content-color; }
    .stat-card__value { color: $u-main-color; }
  }
}
</style>
