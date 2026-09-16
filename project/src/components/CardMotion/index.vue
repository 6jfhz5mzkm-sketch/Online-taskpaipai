<template>
  <view
    class="card-motion"
    :class="{
      'card-motion--pressable': !disabled,
      'card-motion--hoverable': hoverable && !disabled,
    }"
  >
    <slot />
  </view>
</template>

<script setup lang="ts">
/**
 * CardMotion - 卡片 hover/按压微动效封装
 * @description 包裹任意卡片内容，统一微动效：H5 hover 轻上浮 + 阴影增强（150-300ms 过渡），
 *              按压 scale 微缩；可整体禁用（disabled 传透场景）。不改变内容布局与功能。
 *
 * @example
 * <CardMotion><TaskCard ... /></CardMotion>
 * <CardMotion :disabled="true"><view>静态内容</view></CardMotion>
 */
interface Props {
  /** 是否禁用动效（默认 false） */
  disabled?: boolean
  /** 是否启用 H5 hover 上浮阴影（移动端无 hover，仅按压生效；默认 true） */
  hoverable?: boolean
}

withDefaults(defineProps<Props>(), {
  disabled: false,
  hoverable: true,
})
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.card-motion {
  border-radius: $up-radius-lg;
  transition: transform $up-ease-normal, box-shadow $up-ease-normal;

  /* 按压微动效：150-300ms，点击反馈 */
  &--pressable:active {
    transform: scale(0.98);
  }

  /* H5 hover：轻上浮 + 柔和阴影增强（大而柔，主色低透明度） */
  &--hoverable {
    &:hover {
      transform: translateY(-2rpx);
      box-shadow: $up-shadow-md;
    }
  }
}
</style>
