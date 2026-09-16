<!--
  @Component TrademarkSearch
  @Version 1.0.0
  @Description 商标注册号模糊搜索（T2.1.2）：输入品牌名关键词实时联想，
               查询成功并展示结果即完成任务（emit complete）。
-->
<template>
  <view class="trademark-search">
    <text class="trademark-search__hint">输入品牌名称关键词，支持模糊搜索</text>
    <view class="trademark-search__row">
      <input
        v-model="keyword"
        class="trademark-search__input"
        placeholder="如：小米"
        confirm-type="search"
        @input="handleInput"
        @confirm="handleSearch"
      />
      <view class="trademark-search__btn" @tap="handleSearch">
        <text class="trademark-search__btn-text">查询</text>
      </view>
    </view>

    <view v-if="loading" class="trademark-search__status">
      <text class="trademark-search__status-text">查询中...</text>
    </view>
    <view v-else-if="results.length > 0" class="trademark-search__results">
      <view v-for="(item, idx) in results" :key="idx" class="trademark-search__result">
        <text class="trademark-search__brand">{{ item.brand_name }}</text>
        <view class="trademark-search__result-right">
          <text class="trademark-search__number">{{ item.registration_number }}</text>
          <view class="trademark-search__copy" @tap.stop="copyNumber(item.registration_number)">
            <text class="trademark-search__copy-text">复制</text>
          </view>
        </view>
      </view>
      <text class="trademark-search__tip">查询成功，可复制注册号前往京麦填写</text>
    </view>
    <view v-else-if="searched" class="trademark-search__status">
      <text class="trademark-search__status-text">未查询到匹配结果，请换个关键词</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { searchTrademark } from '@/api/stage2';
import type { TrademarkResult } from '@/api/stage2';

const emit = defineEmits<{ complete: [] }>();

const keyword = ref('');
const results = ref<TrademarkResult[]>([]);
const loading = ref(false);
const searched = ref(false);
let timer: ReturnType<typeof setTimeout> | null = null;

/** 复制注册号（仅复制该项 registration_number；H5/小程序均走系统剪贴板） */
function copyNumber(registrationNumber: string) {
  uni.setClipboardData({
    data: registrationNumber,
    success: () => {
      uni.showToast({ title: '已复制注册号', icon: 'none' });
    },
    fail: () => {
      uni.showToast({ title: '复制失败，请重试', icon: 'none' });
    },
  });
}

function handleInput() {
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => handleSearch(), 300);
}

async function handleSearch() {
  const kw = keyword.value.trim();
  if (!kw || loading.value) return;
  loading.value = true;
  try {
    const res = await searchTrademark(kw);
    results.value = res.data || [];
    searched.value = true;
    if (results.value.length > 0) {
      emit('complete');
    }
  } catch (e) {
    results.value = [];
    searched.value = true;
    uni.showToast({ title: '查询失败，请稍后重试', icon: 'none' });
  } finally {
    loading.value = false;
  }
}
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.trademark-search {
  margin-top: $up-space-3;
  padding: $up-space-4;
  background-color: $u-white;
  border: 1rpx solid $u-border-color;
  border-radius: $up-radius-md;

  &__hint {
    display: block;
    font-size: $up-font-size-caption;
    color: $u-tips-color;
    margin-bottom: $up-space-3;
  }

  &__row {
    display: flex;
    gap: $up-space-3;
  }

  &__input {
    flex: 1;
    min-height: 72rpx;
    padding: $up-space-2 $up-space-3;
    background-color: $u-bg-color;
    border: 1rpx solid $u-border-color;
    border-radius: $up-radius-sm;
    font-size: $up-font-size-body-sm;
    color: $u-main-color;
  }

  &__btn {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 128rpx;
    background-color: $u-primary;
    border-radius: $up-radius-sm;
  }

  &__btn-text {
    font-size: $up-font-size-body-sm;
    color: $u-white;
    font-weight: 500;
  }

  &__results {
    margin-top: $up-space-3;
  }

  &__result {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: $up-space-3;
    padding: $up-space-2 $up-space-3;
    background-color: $u-bg-color;
    border-radius: $up-radius-sm;
    margin-bottom: $up-space-2;
  }

  &__brand {
    flex: 1;
    min-width: 0;
    font-size: $up-font-size-body-sm;
    color: $u-main-color;
    font-weight: 500;
  }

  &__result-right {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: $up-space-2;
  }

  &__number {
    font-size: $up-font-size-body-sm;
    color: $u-primary-dark;
    font-weight: 600;
  }

  &__copy {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 4rpx $up-space-3;
    background-color: $u-primary-light;
    border: 1rpx solid $u-tag-primary-border;
    border-radius: $up-radius-full;
    cursor: pointer;
    transition: background-color $up-ease-fast, opacity $up-ease-fast;

    &:active {
      background-color: $u-primary;
    }
  }

  &__copy-text {
    font-size: $up-font-size-mini;
    font-weight: 500;
    color: $u-primary-dark;

    .trademark-search__copy:active & {
      color: $u-white;
    }
  }

  &__tip {
    display: block;
    margin-top: $up-space-2;
    font-size: $up-font-size-caption;
    color: $u-success;
  }

  &__status {
    margin-top: $up-space-3;
  }

  &__status-text {
    font-size: $up-font-size-caption;
    color: $u-tips-color;
  }
}
</style>
