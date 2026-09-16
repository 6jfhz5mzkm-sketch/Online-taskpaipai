<template>
  <view class="page-container">
    <!-- 标签切换 -->
    <view class="tabs">
      <view
        v-for="tab in tabList"
        :key="tab.key"
        class="tab-item"
        :class="{ 'tab-item--active': activeTab === tab.key }"
        @tap="activeTab = tab.key"
      >
        <text class="tab-item__text">{{ tab.label }}</text>
        <text class="tab-item__count">{{ tab.count }}</text>
      </view>
    </view>

    <!-- 搜索框 -->
    <view class="search-bar">
      <view class="search-box">
        <text class="search-box__icon">🔍</text>
        <input
          class="search-box__input"
          v-model="keyword"
          placeholder="搜索类目或品牌..."
          placeholder-class="search-box__placeholder"
        />
        <text v-if="keyword" class="search-box__clear" @tap="keyword = ''">×</text>
      </view>
    </view>

    <!-- 统计信息 -->
    <view class="stats">
      <text class="stats-text">共 {{ filteredData.length }} 条</text>
      <text v-if="keyword" class="stats-text stats-text--keyword">关键词：{{ keyword }}</text>
    </view>

    <!-- 数据表格 -->
    <DataTable :columns="columns" :data="filteredData" :empty-text="'未找到匹配的「' + keyword + '」'" />
    <view v-if="filteredData.length === 0 && !keyword" class="empty-wrap">
      <EmptyState text="暂无资费数据" sub-text="请稍后刷新重试" />
    </view>
  </view>
</template>

<script setup lang="ts">
/**
 * 类目/资费查询与数据校验页
 * @description 基础/特殊资费表格展示：Tab 切换 + 关键词搜索 + DataTable 数据表格（数值等宽）。
 */
import { ref, computed } from 'vue';
import feeBasic from '@/static/data/fee_basic.json';
import feeSpecial from '@/static/data/fee_special.json';
import DataTable from '@/components/DataTable/index.vue';
import EmptyState from '@/components/EmptyState/index.vue';

type TabKey = 'basic' | 'special';

interface TabItem {
  key: TabKey
  label: string
  count: number
}

const activeTab = ref<TabKey>('basic');
const keyword = ref('');

const basicData = feeBasic as Record<string, string>[];
const specialData = feeSpecial as Record<string, string>[];

const tabList = computed<TabItem[]>(() => [
  { key: 'basic', label: '基础资费', count: basicData.length },
  { key: 'special', label: '特殊资费', count: specialData.length },
]);

/** 当前数据源 */
const sourceData = computed(() => (activeTab.value === 'basic' ? basicData : specialData));

/** 过滤后的数据 */
const filteredData = computed(() => {
  const list = sourceData.value;
  if (!keyword.value) return list;
  const kw = keyword.value.toLowerCase();
  return list.filter((item) =>
    Object.values(item).some(
      (v) => typeof v === 'string' && v.toLowerCase().includes(kw)
    )
  );
});

/** 基础资费列配置 */
const basicColumns = computed(() => [
  { key: '二级类目', title: '二级类目', width: '15%' },
  { key: '三级类目', title: '三级类目', width: '15%' },
  { key: '运营支持服务费率', title: '运营费率', width: '12%' },
  { key: '交易服务费率', title: '交易费率', width: '12%' },
  { key: '保证金 GMV＜5万', title: '<5万', width: '14%' },
  { key: '保证金 5-10万', title: '5-10万', width: '14%' },
  { key: '保证金 10-30万', title: '10-30万', width: '14%' },
  { key: '保证金 ≥30万', title: '≥30万', width: '14%' },
]);

/** 特殊资费列配置 */
const specialColumns = computed(() => [
  { key: '二级类目', title: '二级类目', width: '20%' },
  { key: '三级类目', title: '三级类目', width: '20%' },
  { key: '品牌名称', title: '品牌', width: '20%' },
  { key: '运营支持服务费率（拍拍二手）', title: '运营费率', width: '20%' },
  { key: '交易服务费率（拍拍二手）', title: '交易费率', width: '20%' },
]);

const columns = computed(() => (activeTab.value === 'basic' ? basicColumns.value : specialColumns.value));
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.page-container {
  min-height: 100vh;
  background-color: $u-bg-color;
  padding: $up-space-4;
  padding-bottom: $up-space-8;
}

/* 标签切换（胶囊 Tab，Token 化） */
.tabs {
  display: flex;
  gap: $up-space-3;
  margin-bottom: $up-space-4;
}

.tab-item {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: $up-space-2;
  padding: $up-space-3 0;
  background-color: $u-white;
  border: 1rpx solid $u-border-color;
  border-radius: $up-radius-full;
  transition: all $up-ease-normal;

  &:active {
    transform: scale(0.97);
  }

  &--active {
    background-color: $u-primary;
    border-color: $u-primary;
    box-shadow: $up-shadow-btn;

    .tab-item__text {
      color: $u-white;
      font-weight: $up-font-weight-medium;
    }

    .tab-item__count {
      color: $u-white;
    }
  }

  &__text {
    font-size: $up-font-size-body-sm;
    color: $u-content-color;
  }

  &__count {
    font-size: $up-font-size-mini;
    color: $u-tips-color;
    font-variant-numeric: tabular-nums;
  }
}

/* 搜索框 */
.search-bar {
  margin-bottom: $up-space-4;
}

.search-box {
  display: flex;
  align-items: center;
  gap: $up-space-2;
  height: 76rpx;
  background-color: $u-white;
  border: 1rpx solid $u-border-color;
  border-radius: $up-radius-full;
  padding: 0 $up-space-4;
  box-sizing: border-box;
  transition: border-color $up-ease-fast, box-shadow $up-ease-fast;

  &:focus-within {
    border-color: $u-primary;
    box-shadow: $up-shadow-sm;
  }

  &__icon {
    font-size: $up-font-size-body;
    flex-shrink: 0;
  }

  &__input {
    flex: 1;
    min-width: 0;
    font-size: $up-font-size-body-sm;
    color: $u-main-color;
  }

  &__placeholder {
    color: $u-tips-color;
  }

  &__clear {
    font-size: $up-font-size-h2;
    color: $u-tips-color;
    padding: $up-space-1 $up-space-2;
    flex-shrink: 0;
  }
}

/* 统计信息 */
.stats {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: $up-space-3;
  padding: 0 $up-space-2;
}

.stats-text {
  font-size: $up-font-size-caption;
  color: $u-tips-color;
  font-variant-numeric: tabular-nums;

  &--keyword {
    color: $u-primary-dark;
  }
}

.empty-wrap {
  background-color: $u-white;
  border: 1rpx solid $u-border-color;
  border-radius: $up-radius-md;
  margin-top: $up-space-3;
}
</style>
