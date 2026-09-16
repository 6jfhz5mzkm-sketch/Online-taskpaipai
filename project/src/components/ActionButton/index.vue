<template>
  <view
    class="action-button"
    :class="[
      'action-button--' + type,
      {
        'action-button--block': block,
        'action-button--disabled': disabled,
        'action-button--small': size === 'small',
      },
    ]"
    :hover-class="hoverClass"
    @tap="handleClick"
  >
    <view v-if="loading" class="action-button__spinner" />
    <slot />
  </view>
</template>

<script setup lang="ts">
/**
 * ActionButton - 主/次按钮封装
 * @description 统一按钮样式（主/次/幽灵/危险），配色按《设计规范》§3.3 按钮 Token；
 *              内置按压微动效（150-300ms 过渡），支持 loading / disabled / block / small。
 *
 * @example
 * <ActionButton type="primary" @click="submit">完成任务</ActionButton>
 * <ActionButton type="secondary" size="small">查看详情</ActionButton>
 */
type ButtonType = 'primary' | 'secondary' | 'ghost' | 'danger' | 'danger-secondary'

interface Props {
  /** 按钮类型：primary=主按钮 / secondary=次按钮 / ghost=幽灵 / danger=危险主 / danger-secondary=危险次 */
  type?: ButtonType
  /** 是否禁用 */
  disabled?: boolean
  /** 是否加载中（显示 spinner） */
  loading?: boolean
  /** 是否占满整行（默认 true） */
  block?: boolean
  /** 尺寸：normal（默认）/ small */
  size?: 'normal' | 'small'
}

const props = withDefaults(defineProps<Props>(), {
  type: 'primary',
  disabled: false,
  loading: false,
  block: true,
  size: 'normal',
})

const emit = defineEmits<{
  /** 点击按钮时触发（disabled/loading 时不触发） */
  click: []
}>()

/** H5 hover 类名（仅非禁用时生效） */
const hoverClass = props.disabled ? '' : 'action-button--hover'

function handleClick(): void {
  if (props.disabled || props.loading) return
  emit('click')
}
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.action-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: $up-space-2;
  padding: $up-space-3 $up-space-6;
  border-radius: $up-radius-md;
  font-size: $up-font-size-body;
  font-weight: $up-font-weight-medium;
  border-width: 1rpx;
  border-style: solid;
  box-sizing: border-box;
  cursor: pointer;
  user-select: none;
  transition: all $up-ease-normal;

  /* 按压微动效：150-300ms 过渡，点击/取消等交互场景 */
  &:active {
    transform: scale(0.97);
  }

  &--block {
    width: 100%;
  }

  &--small {
    padding: $up-space-2 $up-space-4;
    font-size: $up-font-size-body-sm;
    border-radius: $up-radius-sm;
  }

  &__spinner {
    width: 28rpx;
    height: 28rpx;
    border: 3rpx solid rgba(255, 255, 255, 0.35);
    border-top-color: $u-white;
    border-radius: $up-radius-full;
    animation: action-button-spin 0.8s linear infinite;
  }

  /* ---- 类型配色（Token，对应设计规范 §3.3）---- */
  &--primary {
    background-color: $u-primary;
    border-color: $u-primary;
    color: $u-white;
    box-shadow: $up-shadow-btn;

    &.action-button--hover, &:active {
      background-color: $u-primary-dark;
      border-color: $u-primary-dark;
    }
  }

  &--secondary {
    background-color: $u-white;
    border-color: $u-primary;
    color: $u-primary;

    &.action-button--hover, &:active {
      background-color: $u-primary-light;
    }
  }

  &--ghost {
    background-color: transparent;
    border-color: transparent;
    color: $u-primary;

    &.action-button--hover, &:active {
      background-color: $u-primary-light;
    }
  }

  &--danger {
    background-color: $u-error;
    border-color: $u-error;
    color: $u-white;

    &.action-button--hover, &:active {
      background-color: $u-error-dark;
      border-color: $u-error-dark;
    }
  }

  &--danger-secondary {
    background-color: $u-white;
    border-color: $u-error;
    color: $u-error;

    &.action-button--hover, &:active {
      background-color: $u-error-light;
    }
  }

  /* ---- 禁用态 ---- */
  &--disabled {
    background-color: $u-disabled-color;
    border-color: $u-disabled-color;
    color: $u-light-color;
    box-shadow: none;
    cursor: not-allowed;

    &:active {
      transform: none;
    }
  }
}

@keyframes action-button-spin {
  to { transform: rotate(360deg); }
}
</style>
