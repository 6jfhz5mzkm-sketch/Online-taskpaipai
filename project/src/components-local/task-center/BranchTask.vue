<!--
  @Component BranchTask
  @Version 1.0.0
  @Description 支线任务卡片组件，包含标题栏、任务列表与示例区域。
  @Props title - 任务标题 | tasks - 任务项数组
  @Events toggle-check - 勾选状态变更时触发，携带 taskId
-->
<template>
  <view class="branch-task">
    <!-- 标题栏 -->
    <view class="branch-task__header">
      <text class="branch-task__title">{{ title }}</text>
    </view>

    <!-- 任务列表 -->
    <view class="branch-task__list">
      <view
        v-for="(item, index) in tasks"
        :key="item.id"
        :class="[
          'branch-task__item',
          { 'branch-task__item--bordered': index > 0 },
        ]"
      >
        <view class="branch-task__checkbox">
          <Checkbox
            :model-value="item.checked"
            @update:model-value="handleToggle(item.id)"
          />
        </view>
        <view class="branch-task__text">
          <text class="branch-task__item-name">{{ item.name }}</text>
          <text v-if="item.hint" class="branch-task__item-hint">{{ item.hint }}</text>
        </view>
      </view>
    </view>

    <!-- 示例区域 -->
    <view class="branch-task__examples">
      <view class="branch-task__example-row">
        <text class="branch-task__icon-success">✅</text>
        <text class="branch-task__example-text">营业执照放置在店铺显眼位置，内容清晰可辨</text>
      </view>
      <view class="branch-task__example-row">
        <text class="branch-task__icon-error">❌</text>
        <text class="branch-task__example-text">营业执照缺失、遮挡或内容模糊无法辨识</text>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
/**
 * BranchTask 组件（支线任务）
 * @description 支线任务卡片，展示标题、可勾选任务列表与正确/错误示例。
 * @see Checkbox
 */
import Checkbox from '@/components/Checkbox/index.vue'

interface BranchTaskItem {
  /** 任务唯一标识 */
  id: string
  /** 任务名称 */
  name: string
  /** 任务提示文字 */
  hint: string
  /** 是否已勾选 */
  checked: boolean
}

interface Props {
  /** 卡片标题，如 "支线任务：店铺名称合规检查" */
  title: string
  /** 任务项列表 */
  tasks: BranchTaskItem[]
}

defineProps<Props>()

const emit = defineEmits<{
  /** 勾选状态切换，返回任务 ID */
  'toggle-check': [taskId: string]
}>()

/** 触发勾选切换事件 */
function handleToggle(taskId: string): void {
  emit('toggle-check', taskId)
}
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.branch-task {
  border: 1px solid $u-border-color;
  border-radius: $up-radius-lg;
  overflow: hidden;
  background-color: #ffffff;

  &__header {
    background-color: $u-bg-color;
    padding: $up-space-3 $up-space-5;
  }

  &__title {
    font-size: 28rpx;
    font-weight: 600;
    color: $u-main-color;
    line-height: 1.5;
  }

  &__list {
    padding: 0 $up-space-5;
  }

  &__item {
    display: flex;
    align-items: flex-start;
    padding: $up-space-4 0;
    gap: $up-space-3;

    &--bordered {
      border-top: 1px solid $u-border-color;
    }
  }

  &__checkbox {
    flex-shrink: 0;
    padding-top: 2rpx;
  }

  &__text {
    flex: 1;
    min-width: 0;
  }

  &__item-name {
    font-size: 28rpx;
    color: $u-main-color;
    line-height: 1.5;
  }

  &__item-hint {
    display: block;
    margin-top: $up-space-1;
    font-size: 24rpx;
    color: $u-tips-color;
    line-height: 1.6;
  }

  /* 示例区域 */
  &__examples {
    padding: $up-space-4 $up-space-5;
    border-top: 1px solid $u-border-color;
    background-color: $u-bg-color;
  }

  &__example-row {
    display: flex;
    align-items: flex-start;
    gap: $up-space-2;
    margin-bottom: $up-space-2;

    &:last-child {
      margin-bottom: 0;
    }
  }

  &__icon-success,
  &__icon-error {
    font-size: 28rpx;
    line-height: 1.6;
    flex-shrink: 0;
  }

  &__example-text {
    font-size: 24rpx;
    color: $u-tips-color;
    line-height: 1.6;
    flex: 1;
  }
}
</style>


