<template>
  <view class="title-panel">
    <!-- accordion 头：AI 商品标题优化（展开/收起） -->
    <view class="title-panel__header" @tap="expanded = !expanded">
      <text class="title-panel__title">AI 商品标题优化</text>
      <text class="title-panel__arrow">{{ expanded ? "▾" : "▸" }}</text>
    </view>

    <!-- 展开内容 -->
    <view v-show="expanded" class="title-panel__body">
      <!-- 模式切换：标题生成 / 标题优化 -->
      <view class="title-panel__modes">
        <view
          class="title-panel__mode"
          :class="{ 'title-panel__mode--active': mode === 'generate' }"
          @tap="mode = 'generate'"
        >
          <text class="title-panel__mode-text">标题生成</text>
        </view>
        <view
          class="title-panel__mode"
          :class="{ 'title-panel__mode--active': mode === 'optimize' }"
          @tap="mode = 'optimize'"
        >
          <text class="title-panel__mode-text">标题优化</text>
        </view>
      </view>

      <!-- 类目选择（下拉） -->
      <view class="title-panel__field">
        <text class="title-panel__label">类目<text class="title-panel__required"> *</text></text>
        <picker :range="categories" @change="onCategoryChange">
          <view class="title-panel__picker">
            <text class="title-panel__picker-text" :class="{ 'title-panel__picker-text--placeholder': !category }">{{ category || '请选择类目' }}</text>
            <text class="title-panel__picker-arrow">▾</text>
          </view>
        </picker>
      </view>

      <!-- 标题生成表单 -->
      <template v-if="mode === 'generate'">
        <view v-for="f in generateFields" :key="f.key" class="title-panel__field">
          <text class="title-panel__label">{{ f.label }}</text>
          <input v-model="form[f.key]" class="title-panel__input" :placeholder="f.placeholder" />
        </view>
        <text class="title-panel__hint">{{ categoryHint }}</text>
      </template>

      <!-- 标题优化表单 -->
      <template v-else>
        <view class="title-panel__field">
          <text class="title-panel__label">现有标题<text class="title-panel__required"> *</text></text>
          <input v-model="form.currentTitle" class="title-panel__input" placeholder="请输入当前商品标题" />
        </view>
      </template>

      <!-- 提交 -->
      <view class="title-panel__submit">
        <ActionButton type="primary" size="small" :loading="submitting" @click="submit">
          {{ submitting ? 'AI 生成中…' : (mode === 'generate' ? '生成标题' : '优化标题') }}
        </ActionButton>
      </view>

      <!-- 结果展示（SPU + 可选 SKU + notes，可复制） -->
      <view v-if="result" class="title-panel__result">
        <view class="title-panel__result-head">
          <text class="title-panel__result-title">AI 生成结果</text>
          <ActionButton type="ghost" size="small" :block="false" @click="copyResult">复制</ActionButton>
        </view>
        <view class="title-panel__result-item">
          <text class="title-panel__result-label">SPU 标题</text>
          <text class="title-panel__result-text">{{ result.spuTitle }}</text>
        </view>
        <view v-if="result.skuTitle" class="title-panel__result-item">
          <text class="title-panel__result-label">SKU 标题</text>
          <text class="title-panel__result-text">{{ result.skuTitle }}</text>
        </view>
        <view v-if="result.notes" class="title-panel__result-item">
          <text class="title-panel__result-label">说明</text>
          <text class="title-panel__result-text">{{ result.notes }}</text>
        </view>
      </view>

      <!-- 失败：可读错误 + 点击重试 -->
      <view v-if="error" class="title-panel__error" @tap="submit">
        <text class="title-panel__error-text">{{ error }}</text>
        <text class="title-panel__retry-text">点击重试</text>
      </view>

      <!-- 生成中：LoadingOverlay -->
      <LoadingOverlay v-if="submitting" text="AI 生成中…" />
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue';
import { optimizeTitle, type TitleOptimizeData } from '@/api/stage2';
import ActionButton from '@/components/ActionButton/index.vue';
import LoadingOverlay from '@/components-local/stage2/LoadingOverlay.vue';

/**
 * TitleOptimizePanel - 商品标题 AI 优化面板（T2.3.1 展开区 accordion）
 * @description 手风琴展开/收起；模式切换（标题生成/标题优化）；生成模式按类目动态提示字段
 *              （品牌/型号/特点/成色/关键属性/销售属性），优化模式输入现有标题；
 *              提交 POST /api/shop/title-optimize → 展示 SPU/SKU 标题 + notes，可复制；
 *              LoadingOverlay「AI 生成中…」，失败可读错误可重试。
 */

/** 类目列表（与后端约定一致） */
const categories = [
  '二手手机',
  '二手电脑整机',
  '二手奢侈品',
  '二手智能设备',
  '二手办公设备',
  '二手骑行运动',
  '二手家电',
  '其他',
];

/** 各类目标题规则提示（R59 第二节，精简提示语） */
const CATEGORY_HINTS: Record<string, string> = {
  '二手手机': '成色词：准新/官翻/99新/95新/9新/8新/7新（苹果可加资源机）；禁止刷机越狱、非国行、XR改',
  '二手电脑整机': '建议含机器年份、型号、CPU、GPU、内存、显卡；T-3 可标注 99 新、T-7 可标注 95 新',
  '二手奢侈品': '腕表/包袋：品牌中文+英文+系列+型号+功能+性别',
  '二手智能设备': '成色词可选：99新 / 95新 / 9成新 / 8成新',
  '二手办公设备': '成色词可选：99新 / 95新 / 9成新 / 8成新',
  '二手骑行运动': '成色词可选：99新 / 95新 / 9成新 / 8成新',
  '二手家电': 'SPU 首位加「二手」+成色（尾货机/样品机等）+匹数/能效等级；禁止官翻机、准新机',
  '其他': '通用格式：二手 + 品牌 + 型号 + 产品特点',
};

/** 生成模式表单字段（placeholder 按类目成色/规则动态变化） */
const generateFields = computed(() => [
  { key: 'brand', label: '品牌', placeholder: '如 苹果' },
  { key: 'model', label: '型号', placeholder: '如 iPhone 15 Pro Max' },
  { key: 'features', label: '产品特点', placeholder: '如 全网通5G、大容量电池' },
  { key: 'condition', label: '成色', placeholder: conditionPlaceholder.value },
  { key: 'keyAttrs', label: '关键属性', placeholder: '如 256G、深空黑' },
  { key: 'saleAttrs', label: '销售属性', placeholder: '如 官方标配、单机' },
]);

/** 成色输入占位（按类目） */
const conditionPlaceholder = computed(() => {
  if (category.value === '二手手机') return '如 95新 / 准新 / 官翻';
  if (category.value === '二手家电') return '如 尾货机 / 样品机（限85新及以上）';
  return '如 99新 / 95新';
});

/** 当前类目规则提示 */
const categoryHint = computed(() => CATEGORY_HINTS[category.value] || CATEGORY_HINTS['其他']);

const expanded = ref(false); // 任务卡展开、表单区默认收起（F2-T231B），用户可手动展开
const mode = ref<'generate' | 'optimize'>('generate');
const category = ref('');
const form = reactive<Record<string, string>>({
  brand: '',
  model: '',
  features: '',
  condition: '',
  keyAttrs: '',
  saleAttrs: '',
  currentTitle: '',
});
const submitting = ref(false);
const result = ref<TitleOptimizeData | null>(null);
const error = ref('');

function onCategoryChange(e: { detail?: { value?: number } }) {
  const idx = e?.detail?.value ?? 0;
  category.value = categories[idx] || '';
  error.value = '';
  result.value = null;
}

/** 提交生成/优化 */
async function submit() {
  if (submitting.value) return;
  if (!category.value) { error.value = '请选择类目'; return; }
  if (mode.value === 'generate') {
    if (!form.brand && !form.model) { error.value = '请至少填写品牌或型号'; return; }
  } else if (!form.currentTitle.trim()) {
    error.value = '请输入现有标题';
    return;
  }
  submitting.value = true;
  error.value = '';
  result.value = null;
  try {
    const payload = {
      mode: mode.value,
      category: category.value,
      brand: form.brand,
      model: form.model,
      features: form.features,
      condition: form.condition,
      keyAttrs: form.keyAttrs,
      saleAttrs: form.saleAttrs,
      currentTitle: form.currentTitle,
    };
    result.value = await optimizeTitle(payload);
  } catch (e) {
    error.value = (e as { message?: string })?.message || 'AI 生成失败，请重试';
  } finally {
    submitting.value = false;
  }
}

/** 复制结果全文（SPU + SKU + notes） */
function copyResult() {
  if (!result.value) return;
  const lines: string[] = ['SPU 标题：' + result.value.spuTitle];
  if (result.value.skuTitle) lines.push('SKU 标题：' + result.value.skuTitle);
  if (result.value.notes) lines.push('说明：' + result.value.notes);
  uni.setClipboardData({
    data: lines.join('\n'),
    success: () => uni.showToast({ title: '已复制到剪贴板', icon: 'none' }),
    fail: () => uni.showToast({ title: '复制失败，请重试', icon: 'none' }),
  });
}
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.title-panel {
  margin-top: $up-space-3;
  background-color: $u-white;
  border: 1rpx solid $u-border-color;
  border-radius: $up-radius-md;
  overflow: hidden;

  /* accordion 头 */
  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: $up-space-3 $up-space-4;
    transition: background-color $up-ease-normal;

    &:active {
      background-color: $u-primary-light;
    }
  }

  &__title {
    font-size: $up-font-size-body-sm;
    font-weight: 600;
    color: $u-primary;
  }

  &__arrow {
    font-size: $up-font-size-caption;
    color: $u-tips-color;
  }

  &__body {
    position: relative;
    padding: $up-space-4;
    border-top: 1rpx solid $u-border-color;
  }

  /* 模式分段 */
  &__modes {
    display: flex;
    gap: $up-space-2;
    margin-bottom: $up-space-4;
  }

  &__mode {
    flex: 1;
    padding: $up-space-2 0;
    text-align: center;
    border: 1rpx solid $u-border-color;
    border-radius: $up-radius-sm;
    transition: background-color $up-ease-normal, border-color $up-ease-normal;

    &--active {
      background-color: $u-primary-light;
      border-color: $u-primary;

      .title-panel__mode-text {
        color: $u-primary;
        font-weight: 600;
      }
    }
  }

  &__mode-text {
    font-size: $up-font-size-body-sm;
    color: $u-content-color;
  }

  /* 表单字段 */
  &__field {
    margin-bottom: $up-space-3;
  }

  &__label {
    display: block;
    font-size: $up-font-size-body-sm;
    color: $u-content-color;
    margin-bottom: $up-space-1;
  }

  &__required {
    color: $u-error;
  }

  &__picker {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 72rpx;
    padding: $up-space-2 $up-space-3;
    background-color: $u-bg-color;
    border: 1rpx solid $u-border-color;
    border-radius: $up-radius-sm;
  }

  &__picker-text {
    font-size: $up-font-size-body-sm;
    color: $u-main-color;

    &--placeholder {
      color: $u-tips-color;
    }
  }

  &__picker-arrow {
    font-size: $up-font-size-caption;
    color: $u-tips-color;
  }

  &__input {
    min-height: 72rpx;
    padding: $up-space-2 $up-space-3;
    background-color: $u-bg-color;
    border: 1rpx solid $u-border-color;
    border-radius: $up-radius-sm;
    font-size: $up-font-size-body-sm;
    color: $u-main-color;
  }

  /* 类目规则提示 */
  &__hint {
    display: block;
    margin-bottom: $up-space-3;
    font-size: $up-font-size-caption;
    color: $u-tips-color;
    line-height: 1.6;
  }

  &__submit {
    margin-top: $up-space-4;
  }

  /* 结果展示 */
  &__result {
    margin-top: $up-space-4;
    padding: $up-space-4;
    background-color: $u-bg-color;
    border: 1rpx solid $u-border-color;
    border-radius: $up-radius-md;
  }

  &__result-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: $up-space-3;
  }

  &__result-title {
    font-size: $up-font-size-body;
    font-weight: 600;
    color: $u-main-color;
  }

  &__result-item {
    margin-bottom: $up-space-3;

    &:last-child {
      margin-bottom: 0;
    }
  }

  &__result-label {
    display: block;
    font-size: $up-font-size-caption;
    color: $u-tips-color;
    margin-bottom: $up-space-1;
  }

  &__result-text {
    display: block;
    font-size: $up-font-size-body-sm;
    color: $u-main-color;
    line-height: 1.7;
  }

  /* 失败重试 */
  &__error {
    margin-top: $up-space-3;
    padding: $up-space-3;
    text-align: center;
    background-color: $u-error-light;
    border: 1rpx solid $u-tag-error-border;
    border-radius: $up-radius-sm;
  }

  &__error-text {
    display: block;
    font-size: $up-font-size-caption;
    color: $u-error;
    line-height: 1.6;
  }

  &__retry-text {
    display: block;
    margin-top: $up-space-1;
    font-size: $up-font-size-mini;
    color: $u-error;
    font-weight: 500;
  }
}
</style>