<template>
  <view class="empty-state">
    <view class="empty-state__icon">
      <text class="empty-state__icon-text">{{ iconText }}</text>
    </view>
    <text class="empty-state__text">{{ text }}</text>
    <text v-if="subText" class="empty-state__sub">{{ subText }}</text>
    <view v-if="actionText" class="empty-state__action" @tap="handleAction">
      <text class="empty-state__action-text">{{ actionText }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
/**
 * EmptyState - 空态组件
 * @description 统一各页空数据/无搜索结果展示：图标 + 主文案 + 可选说明 + 可选操作按钮。
 *
 * @example
 * <EmptyState text="暂无进度数据" sub-text="完成任务后此处将展示进度" />
 * <EmptyState type="search" text="未找到匹配的类目" action-text="清除筛选" @action="keyword = ''" />
 */
import { computed } from 'vue'

type EmptyType = 'default' | 'search' | 'error'

interface Props {
  /** 空态类型：default=数据为空 / search=无搜索结果 / error=加载失败 */
  type?: EmptyType
  /** 主文案 */
  text: string
  /** 辅助说明（可选） */
  subText?: string
  /** 操作按钮文字（可选，提供后展示按钮并触发 action） */
  actionText?: string
}

const props = withDefaults(defineProps<Props>(), {
  type: 'default',
  subText: '',
  actionText: '',
})

const emit = defineEmits<{
  /** 点击操作按钮时触发 */
  action: []
}>()

/** 按类型映射图标（emoji，纯展示不引入图标库） */
const iconText = computed(() => {
  switch (props.type) {
    case 'search': return '🔍'
    case 'error': return '⚠️'
    default: return '📭'
  }
})

function handleAction(): void {
  emit('action')
}
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: $up-space-8 $up-space-5;
  text-align: center;

  &__icon {
    width: 120rpx;
    height: 120rpx;
    border-radius: $up-radius-full;
    background-color: $u-bg-color;
    border: 1rpx solid $u-border-color;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: $up-space-4;
  }

  &__icon-text {
    font-size: 56rpx;
    line-height: 1;
  }

  &__text {
    font-size: $up-font-size-body;
    color: $u-content-color;
    font-weight: $up-font-weight-medium;
    line-height: 1.5;
  }

  &__sub {
    margin-top: $up-space-2;
    font-size: $up-font-size-caption;
    color: $u-tips-color;
    line-height: 1.5;
  }

  &__action {
    margin-top: $up-space-5;
    padding: $up-space-2 $up-space-6;
    border: 1rpx solid $u-primary;
    border-radius: $up-radius-full;
    background-color: $u-white;
    transition: all $up-ease-fast;

    &:active {
      background-color: $u-primary-light;
      transform: scale(0.97);
    }
  }

  &__action-text {
    font-size: $up-font-size-body-sm;
    color: $u-primary;
    font-weight: $up-font-weight-medium;
  }
}
</style>
