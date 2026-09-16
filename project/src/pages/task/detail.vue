<template>
  <view class="page-container">
    <view class="page-header">
      <text class="page-title">任务详情</text>
    </view>

    <!-- 详情内容区（占位骨架 + 空态展示，统一视觉） -->
    <view class="section-card">
      <view class="section-title">任务信息</view>
      <LoadingSkeleton v-if="loading" :rows="3" title />
      <EmptyState
        v-else
        type="default"
        text="暂无任务详情数据"
        sub-text="请在任务中心展开任务卡片查看说明"
      />
    </view>

    <view class="section-card">
      <view class="section-title">操作指引</view>
      <view class="guide-list">
        <view class="guide-item">
          <text class="guide-item__dot">•</text>
          <text class="guide-item__text">完成勾选后任务将标记为已完成</text>
        </view>
        <view class="guide-item">
          <text class="guide-item__dot">•</text>
          <text class="guide-item__text">类目/资费查询可在「资费数据校验」页进行</text>
        </view>
      </view>
    </view>

    <!-- 底部操作区 -->
    <view class="action-bar">
      <ActionButton type="secondary" @click="goBack">
        <text>返回任务中心</text>
      </ActionButton>
    </view>

    <!-- 页脚：备案信息（工信部要求） -->
    <IcpFooter />
  </view>
</template>

<script setup lang="ts">
/**
 * 任务详情页
 * @description 单个任务详情占位展示（数据在任务中心卡片内展开）；提供加载骨架/空态统一与返回操作。
 */
import { ref, onMounted } from 'vue';
import LoadingSkeleton from '@/components/LoadingSkeleton/index.vue';
import EmptyState from '@/components/EmptyState/index.vue';
import ActionButton from '@/components/ActionButton/index.vue';
import IcpFooter from '@/components/IcpFooter/index.vue';

const loading = ref(true);

onMounted(() => {
  // 模拟加载占位后展示空态（本页为占位页，不承载真实任务数据）
  setTimeout(() => {
    loading.value = false;
  }, 400);
});

function goBack(): void {
  uni.navigateBack({
    fail: () => {
      uni.reLaunch({ url: '/pages/index/index' });
    },
  });
}
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.page-container {
  min-height: 100vh;
  background-color: $u-bg-color;
  padding: $up-space-4;
  padding-bottom: 160rpx;
}

.page-header {
  padding: $up-space-6 0 $up-space-4;
}

.page-title {
  font-size: $up-font-size-h1;
  font-weight: $up-font-weight-bold;
  color: $u-main-color;
}

.section-card {
  background-color: $u-white;
  border-radius: $up-radius-lg;
  padding: $up-space-5;
  margin-bottom: $up-space-4;
  box-shadow: $up-shadow-md;
}

.section-title {
  font-size: $up-font-size-h3;
  font-weight: $up-font-weight-bold;
  color: $u-main-color;
  margin-bottom: $up-space-4;
}

.guide-list {
  display: flex;
  flex-direction: column;
  gap: $up-space-3;
}

.guide-item {
  display: flex;
  align-items: flex-start;
  gap: $up-space-2;

  &__dot {
    color: $u-primary;
    font-weight: $up-font-weight-bold;
    line-height: 1.6;
  }

  &__text {
    font-size: $up-font-size-body-sm;
    color: $u-content-color;
    line-height: 1.6;
  }
}

.action-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: $up-space-4;
  background-color: $u-white;
  box-shadow: 0 -2rpx 8rpx rgba(0, 0, 0, 0.06);
  border-top: 1rpx solid $u-border-color;
}
</style>
