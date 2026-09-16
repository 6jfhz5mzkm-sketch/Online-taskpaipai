<!--
  @Page data-center/index
  @Version 1.0.0
  @Description 数据分析专区-数据看板：按时间维度（昨天/近7天/近30天）展示 T2.5 已上传指标
               （星级/交易/流量/商品/数量/健康分）+ AI 经营分析区块（同页一体）；
               逻辑整体搬移自原 pages/stage2/data-board.vue（旧路由保留兼容跳转）。
               数据源 GET /api/shop/summary / POST /api/shop/analysis（契约预留，
               接口未就绪时展示空态+提示）。
-->
<template>
  <view class="page-layout">
    <Stage2Sidebar
      :stages="stage2Stages"
      :progress="store.progress"
      :active-index="0"
      :user-name="userName"
      @select="goGroup"
      @go-home="goHome"
    />

    <view class="main-content">
      <view class="board-header">
        <view class="board-header__back" @tap="goBackStage2">
          <text class="board-header__back-text">← 返回开店搭建</text>
        </view>
        <view class="board-header__title-row">
          <text class="board-header__title">数据看板</text>
          <view class="board-header__ops">
            <view class="board-header__refresh" @tap="loadSummary">
              <text class="board-header__refresh-text">刷新</text>
            </view>
            <!-- 清除当前所有数据（破坏性操作：强提示确认；F2-DC） -->
            <view class="board-header__clear" @tap="openClearDataModal">
              <text class="board-header__clear-text">清除数据</text>
            </view>
          </view>
        </view>
        <text class="board-header__desc">按时间维度查看已上传的店铺经营数据</text>
        <!-- 重新观看引导（R60：清除共用标记并重放数据专区引导） -->
        <!-- 重新观看引导入口（仅开发环境显示，生产隐藏） -->
        <view v-if="IS_DEV" class="dc-tour-replay" @tap="replayTour">
          <text class="dc-tour-replay__text">重新观看引导</text>
        </view>
      </view>

      <!-- AI 经营分析（最顶部） -->
      <view class="analysis-card">
        <view class="analysis-card__header">
          <text class="analysis-card__title">AI 经营分析</text>
          <ActionButton
            type="secondary"
            size="small"
            :block="false"
            :disabled="!store.unlocked || analyzing"
            @click="runAnalysis"
          >
            {{ analyzing ? '分析中' : '生成分析' }}
          </ActionButton>
        </view>
        <text class="analysis-card__desc">基于当前时间维度已上传数据生成经营现状与改进建议</text>

        <view v-if="analysis" class="analysis-result">
          <view class="analysis-result__block">
            <text class="analysis-result__title">现状总结</text>
            <text class="analysis-result__summary">{{ analysis.summary }}</text>
          </view>
          <view class="analysis-result__block">
            <text class="analysis-result__title analysis-result__title--good">做得好</text>
            <view v-for="(item, i) in analysis.strengths" :key="'s' + i" class="analysis-result__item">
              <text class="analysis-result__mark analysis-result__mark--good">✓</text>
              <view class="analysis-result__content">
                <text class="analysis-result__text">{{ item.point }}</text>
                <text class="analysis-result__reason">{{ item.reason }}</text>
              </view>
            </view>
            <text v-if="!analysis.strengths.length" class="analysis-result__empty">暂无亮点</text>
          </view>
          <view class="analysis-result__block">
            <text class="analysis-result__title analysis-result__title--bad">待改进</text>
            <view v-for="(item, i) in analysis.weaknesses" :key="'w' + i" class="analysis-result__item">
              <text class="analysis-result__mark analysis-result__mark--bad">!</text>
              <view class="analysis-result__content">
                <text class="analysis-result__text">{{ item.point }}</text>
                <text class="analysis-result__reason">{{ item.reason }}</text>
              </view>
            </view>
            <text v-if="!analysis.weaknesses.length" class="analysis-result__empty">暂无待改进项</text>
          </view>
          <view class="analysis-result__block">
            <text class="analysis-result__title">建议（按优先级）</text>
            <view v-for="(item, i) in analysis.suggestions" :key="'a' + i" class="analysis-result__item">
              <text class="analysis-result__num">{{ i + 1 }}</text>
              <view class="analysis-result__content">
                <text class="analysis-result__text">{{ item.action }}</text>
                <text class="analysis-result__reason">{{ priorityLabel(item.priority) }}</text>
              </view>
            </view>
            <text v-if="!analysis.suggestions.length" class="analysis-result__empty">暂无建议</text>
          </view>
        </view>

        <view v-else-if="analysisError" class="analysis-result__error">
          <text class="analysis-result__error-text">{{ analysisError }}</text>
          <ActionButton type="secondary" size="small" :block="false" @click="runAnalysis">
            重试
          </ActionButton>
        </view>

        <LoadingOverlay v-if="analyzing" text="AI 分析中，请稍候..." />
      </view>

      <!-- 时间维度切换 -->
      <view class="range-tabs">
        <view
          v-for="range in rangeTabs"
          :key="range.key"
          class="range-tabs__item"
          :class="{ 'range-tabs__item--active': activeRange === range.key }"
          @tap="switchRange(range.key)"
        >
          <text class="range-tabs__text">{{ range.label }}</text>
        </view>
      </view>

      <!-- 加载中：统一骨架屏 -->
      <LoadingSkeleton v-if="loading" :rows="3" title />

      <!-- 接口未就绪 -->
      <EmptyState
        v-else-if="notReady"
        type="error"
        text="数据看板暂未就绪"
        sub-text="后端聚合接口接入后将自动展示已上传数据，请稍后再试"
        action-text="重试"
        @action="loadSummary"
      />

      <!-- 无数据 -->
      <EmptyState
        v-else-if="hasNoData"
        text="暂无可展示数据"
        sub-text="完成 T2.5 店铺数据上传后刷新查看"
        action-text="刷新"
        @action="loadSummary"
      />

      <!-- 指标卡片（在下） -->

      <template v-else>
        <CardMotion v-for="type in summaryTypes" :key="type.key">
        <view class="metric-card">
          <view class="metric-card__header">
            <text class="metric-card__title">{{ type.title }}</text>
            <Badge type="info" :text="type.desc" plain />
          </view>
          <view v-if="getTypeData(type.key)" class="metric-card__body">
            <text v-if="getMeta(type.key, 'data_date')" class="metric-card__date">
              数据日期：{{ getMeta(type.key, 'data_date') }}
            </text>
            <view
              v-for="[key, value] in getRows(type.key)"
              :key="key"
              class="metric-card__row"
            >
              <text class="metric-card__label">{{ getLabel(key) }}</text>
              <text class="metric-card__value">{{ formatValue(key, value) }}</text>
            </view>
          </view>
          <view v-else class="metric-card__empty">
            <text class="metric-card__empty-text">暂无数据</text>
          </view>
        </view>
        </CardMotion>
      </template>

      <!-- 页脚：备案信息（工信部要求） -->
      <IcpFooter />
    </view>

    <!-- 清除当前所有数据 · 强提示弹窗（危险操作：不可恢复文案 + 红色确认，F2-DC） -->
    <view v-if="showClearDataModal" class="dc-clear-mask" @tap="closeClearDataModal">
      <view class="dc-clear-box" @tap.stop>
        <view class="dc-clear-box__header">
          <text class="dc-clear-box__title">清除当前所有数据</text>
          <text class="dc-clear-box__close" @tap="closeClearDataModal">×</text>
        </view>
        <view class="dc-clear-box__body">
          <view class="dc-clear-box__badge">⚠ 危险操作</view>
          <text class="dc-clear-box__text">
            将永久删除当前商家所有已上传的店铺数据（星级 / 交易 / 流量 / 商品 / 商品数量 / 健康分），且不可恢复。请确认继续？
          </text>
          <view class="dc-clear-box__actions">
            <view class="dc-clear-box__btn dc-clear-box__btn--secondary" @tap="closeClearDataModal">
              <text class="dc-clear-box__btn-text">取消</text>
            </view>
            <view
              class="dc-clear-box__btn dc-clear-box__btn--danger"
              :class="{ 'dc-clear-box__btn--disabled': clearingData }"
              @tap="confirmClearData"
            >
              <text class="dc-clear-box__btn-text">{{ clearingData ? '清除中…' : '确认清除' }}</text>
            </view>
          </view>
        </view>
      </view>
    </view>

    <!-- 数据专区新手引导（账号级标记，首次进入显示） -->
    <ProductTour
      v-model="tourActive"
      :steps="TOUR_STEPS"
      @complete="onTourComplete"
      @skip="onTourComplete"
    />
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { trackPageView } from '@/utils/track';
import { getMerchantNickname } from '@/utils/merchant';
import { useStage2Store } from '@/store/modules/stage2';
import {
  SHOP_SUMMARY_TIME_RANGES,
  SHOP_SUMMARY_TYPES,
  SHOP_METRIC_LABELS,
} from '@/constants/stage2';
import { fetchShopSummary, fetchShopAnalysis, clearShopData } from '@/api/stage2';
import { fetchTourSeen, markTourSeen, resetTourSeen } from '@/api/tour';
import type { ShopSummaryData, ShopSummaryTimeRange, ShopAnalysisData } from '@/api/stage2';
import Stage2Sidebar from '@/components-local/stage2/Stage2Sidebar.vue';
import LoadingOverlay from '@/components-local/stage2/LoadingOverlay.vue';
import Badge from '@/components/Badge/index.vue';
import EmptyState from '@/components/EmptyState/index.vue';
import LoadingSkeleton from '@/components/LoadingSkeleton/index.vue';
import CardMotion from '@/components/CardMotion/index.vue';
import ActionButton from '@/components/ActionButton/index.vue';
import ProductTour, { type TourStep } from '@/components/ProductTour/index.vue';
import IcpFooter from '@/components/IcpFooter/index.vue';

const store = useStage2Store();
const userName = ref('');

/* ---------- 数据专区新手引导（账号级：GET/POST /api/tour/seen） ---------- */
const tourActive = ref(false);
/** 开发环境标识：生产（build）不渲染「重新观看引导」入口（vite import.meta.env.DEV） */
const IS_DEV = import.meta.env.DEV;

/** 数据专区引导步骤（拆分两块，顺序与页面布局一致：AI 经营分析在上、数据看板在下；
 *  上传步骤归属店铺数据上传页，此处不重复） */
const TOUR_STEPS: TourStep[] = [
  {
    title: 'AI 经营分析',
    text: '按时间维度（昨天/近7天/近30天）点击「生成分析」，可获得经营现状、亮点/待改进与改进建议。',
    target: '.analysis-card',
    placement: 'left',
  },
  {
    title: '数据看板',
    text: '查看已上传的星级/交易/流量/商品等指标数据；数据可在店铺数据上传页填写/上传。',
    target: '.metric-card',
    placement: 'left',
  },
];

/** 首次进入且账号级引导未看过（GET /api/tour/seen）→ 启动 Tour */
async function maybeStartTour() {
  try {
    const data = await fetchTourSeen();
    if (data?.seen === false) {
      tourActive.value = true;
    }
  } catch {
    /* 接口异常不阻塞页面 */
  }
}

/** 引导完成/跳过：标记账号级已看（POST /api/tour/seen） */
async function onTourComplete() {
  try {
    await markTourSeen();
  } catch {
    /* ignore */
  }
}

/** 重新观看引导（开发入口）：重置账号级已看并强制重放 */
async function replayTour() {
  try {
    await resetTourSeen();
  } catch {
    /* ignore */
  }
  tourActive.value = true;
}
const activeRange = ref<ShopSummaryTimeRange>('7d');
const loading = ref(false);
const notReady = ref(false);
const summary = ref<ShopSummaryData | null>(null);
const analyzing = ref(false);
const analysis = ref<ShopAnalysisData | null>(null);
const analysisError = ref('');

const rangeTabs = SHOP_SUMMARY_TIME_RANGES;
const summaryTypes = SHOP_SUMMARY_TYPES;

const stage2Stages = computed(() => store.stage2Stages);

const hasNoData = computed(() => {
  if (!summary.value) return true;
  return summaryTypes.every((type) => !getTypeData(type.key));
});

/** 按类型取汇总数据（兼容契约预留的 snake_case key） */
function getTypeData(key: string): Record<string, number | string> | null | undefined {
  if (!summary.value) return undefined;
  return (summary.value as unknown as Record<string, Record<string, number | string> | null | undefined>)[key];
}

/** 取类型的元信息字段（如 data_date） */
function getMeta(key: string, metaKey: string): string {
  const data = getTypeData(key);
  if (!data) return '';
  const value = data[metaKey];
  return value === undefined || value === null ? '' : String(value);
}

/** 指标行（剔除元信息字段） */
function getRows(key: string): Array<[string, number | string | null | undefined]> {
  const data = getTypeData(key);
  if (!data) return [];
  return Object.entries(data).filter(
    ([k]) => k !== 'data_date' && k !== 'time_range' && k !== 'merchant_id',
  );
}

/** 指标标签（未收录字段回退原始 key） */
function getLabel(key: string): string {
  return SHOP_METRIC_LABELS[key] || key;
}

/** 数值格式化：率类字段追加 % */
function formatValue(key: string, value: number | string | null | undefined): string {
  // 未填写指标：显示「—」，避免字面 null（与 getMeta 空值口径一致）
  if (value === null || value === undefined || value === '') return '—';
  const raw = typeof value === 'number' ? value : Number(value);
  if (!Number.isNaN(raw) && (key.includes('rate') || key === 'spu_active_rate')) {
    return `${raw}%`;
  }
  return String(value);
}

/** 建议优先级中文标签 */
function priorityLabel(priority: string): string {
  const map: Record<string, string> = {
    high: '高优先级',
    medium: '中优先级',
    low: '低优先级',
  };
  return map[priority] || '建议';
}

async function loadSummary() {
  loading.value = true;
  notReady.value = false;
  try {
    const res = await fetchShopSummary(activeRange.value);
    summary.value = res.data || null;
  } catch (e) {
    // 接口未就绪（后端聚合单未完成）：空态 + 提示
    notReady.value = true;
    summary.value = null;
  } finally {
    loading.value = false;
  }
}

/** 触发 AI 经营分析（当前时间维度） */
async function runAnalysis() {
  if (analyzing.value) return;
  if (!store.unlocked) {
    uni.showToast({ title: '阶段二未解锁，无法生成分析', icon: 'none' });
    return;
  }
  analyzing.value = true;
  analysis.value = null;
  analysisError.value = '';
  try {
    const res = await fetchShopAnalysis(activeRange.value);
    const data = res.data;
    if (
      !data ||
      (!data.summary && !data.strengths?.length && !data.weaknesses?.length && !data.suggestions?.length)
    ) {
      analysisError.value = '暂无足够数据生成分析，请先完成 T2.5 店铺数据上传';
      return;
    }
    analysis.value = data;
  } catch (e) {
    analysisError.value = '分析服务暂不可用，请稍后重试';
  } finally {
    analyzing.value = false;
  }
}

function switchRange(key: ShopSummaryTimeRange) {
  if (activeRange.value === key) return;
  activeRange.value = key;
  loadSummary();
}

/* ---------- 清除当前所有数据（F2-DC：破坏性操作强提示；POST /api/shop/clear-data 待后端就绪联调） ---------- */
/** 强提示弹窗可见 */
const showClearDataModal = ref(false);
/** 清除中状态（防重复提交） */
const clearingData = ref(false);

/** 打开强提示弹窗 */
function openClearDataModal() {
  showClearDataModal.value = true;
}

/** 关闭强提示弹窗（遮罩/×/「取消」） */
function closeClearDataModal() {
  if (clearingData.value) return;
  showClearDataModal.value = false;
}

/** 确认清除：POST /api/shop/clear-data → 成功 toast + 刷新看板与数据专区任务状态；失败由 request 封装提示原因 */
async function confirmClearData() {
  if (clearingData.value) return;
  clearingData.value = true;
  try {
    await clearShopData();
    uni.showToast({ title: '已清除', icon: 'none' });
    showClearDataModal.value = false;
    analysis.value = null;
    analysisError.value = '';
    await loadSummary();
    // 同步后端重置后的 T2.5 完成态（店铺数据上传页进度/任务状态下次进入即最新）
    // B8：两处刷新必须 await —— restoreProgress 按 stages 校正完成态，未 await 时会读到刷新前的
    //      旧 stages 导致校正失效；且二者内部不抛错（失败时清空 stages / 置 progressRestoreFailed），
    //      .catch(() => {}) 是死代码且会静默吞错，故改为按 store 状态显式暴露失败。
    await store.fetchStages();
    await store.restoreProgress();
    if (store.stages.length === 0 || store.progressRestoreFailed) {
      uni.showToast({ title: '任务状态刷新失败，请重进页面重试', icon: 'none', duration: 2500 });
    }
  } catch (err) {
    // request 封装已 toast 后端原因（如 403 未解锁/接口未就绪）
    console.warn('清除店铺数据失败:', err);
  } finally {
    clearingData.value = false;
  }
}

/** 侧边栏点击分组：回阶段二主页并定位到对应分组 */
function goGroup(idx: number) {
  uni.navigateTo({ url: `/pages/stage2/index?group=${idx}` });
}

/** 返回任务中心 */
function goHome() {
  uni.reLaunch({ url: '/pages/index/index' });
}

/** 返回开店搭建主页 */
function goBackStage2() {
  const pages = getCurrentPages();
  if (pages.length > 1) {
    uni.navigateBack();
  } else {
    uni.reLaunch({ url: '/pages/stage2/index' });
  }
}

onMounted(async () => {
  trackPageView('data-center-board');
  // 首次进入且共用引导未看过 → 延迟启动 Tour
  setTimeout(() => maybeStartTour(), 500);
  // 用户名：唯一读取入口 @/utils/merchant（未登录返回空串 → 侧栏/顶栏用户区不渲染）
  userName.value = getMerchantNickname();
  if (store.stages.length === 0) {
    await store.fetchStages();
  }
  loadSummary();
});
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';
@import '@/components-local/stage2/_layout.scss';

.page-layout {
  display: flex;
  min-height: 100vh;
  background-color: $u-bg-color;
}

.main-content {
  flex: 1;
  /* 窄视口：允许收缩到可用宽度（flex 项默认 min-width:auto 会被内容 min-content 撑破视口，D1） */
  min-width: 0;
  margin-left: 20%;
  padding: $up-space-6;
}

/* 移动端（≤600px，T-3）：侧栏转抽屉 + 固定顶栏；主内容不再为 20% 侧栏让位，
   顶部让出固定顶栏高度，并保留既有内容上边距（$up-space-6），避免首行贴住顶栏底边 */
@media (max-width: 600px) {
  .main-content {
    margin-left: 0;
    padding-top: calc(#{$stage2-topbar-height} + #{$up-space-6});
  }
}

.board-header {
  margin-bottom: $up-space-6;

  /* 重新观看引导入口（轻量：caption 主色文字，右对齐） */
  &__desc {
    display: block;
    margin-top: $up-space-2;
  }

  &__back {
    margin-bottom: $up-space-4;
  }

  &__back-text {
    font-size: $up-font-size-caption;
    color: $u-primary;
  }

  &__title-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  &__title {
    font-size: $up-font-size-h1;
    font-weight: 600;
    color: $u-main-color;
  }

  &__refresh {
    padding: $up-space-2 $up-space-5;
    background-color: $u-white;
    border: 1rpx solid $u-border-color;
    border-radius: $up-radius-sm;
  }

  /* 重新观看引导入口（轻量：caption 主色文字，右对齐） */
  &__replay {
    display: flex;
    justify-content: flex-end;
    margin-top: $up-space-2;
  }

  &__replay-text {
    font-size: $up-font-size-caption;
    color: $u-primary;
    font-weight: 500;
  }

  &__refresh-text {
    font-size: $up-font-size-caption;
    color: $u-primary;
  }

  &__desc {
    display: block;
    margin-top: $up-space-2;
    font-size: $up-font-size-body-sm;
    color: $u-tips-color;
  }
}

/* 重新观看引导入口（轻量：caption 主色文字，右对齐） */
.dc-tour-replay {
  display: flex;
  justify-content: flex-end;
  margin-top: $up-space-2;

  &__text {
    font-size: $up-font-size-caption;
    color: $u-primary;
    font-weight: 500;
  }
}

.range-tabs {
  display: flex;
  gap: $up-space-3;
  margin-bottom: $up-space-6;

  &__item {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: $up-space-3 0;
    background-color: $u-white;
    border: 1rpx solid $u-border-color;
    border-radius: $up-radius-sm;

    &--active {
      background-color: $u-primary;
      border-color: $u-primary;
    }
  }

  &__text {
    font-size: $up-font-size-body-sm;
    color: $u-content-color;

    .range-tabs__item--active & {
      color: $u-white;
      font-weight: 500;
    }
  }
}

.metric-card {
  background-color: $u-white;
  border: 1rpx solid $u-border-color;
  border-radius: $up-radius-lg;
  padding: $up-space-5;
  margin-bottom: $up-space-5;

  &__header {
    display: flex;
    align-items: center;
    gap: $up-space-2;
    margin-bottom: $up-space-4;
  }

  &__title {
    font-size: $up-font-size-h3;
    font-weight: 600;
    color: $u-main-color;
  }

  &__tag {
    font-size: $up-font-size-mini;
    padding: 2rpx 16rpx;
    border-radius: $up-radius-full;
    background-color: $u-primary-light;
    color: $u-primary-dark;
    font-weight: 500;
  }

  &__date {
    display: block;
    font-size: $up-font-size-caption;
    color: $u-tips-color;
    margin-bottom: $up-space-3;
  }

  &__row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: $up-space-2 0;
    border-bottom: 1rpx solid $u-border-color;

    &:last-child {
      border-bottom: none;
    }
  }

  &__label {
    font-size: $up-font-size-body-sm;
    color: $u-content-color;
  }

  &__value {
    font-size: $up-font-size-body-sm;
    font-weight: 600;
    color: $u-main-color;
    /* 数值等宽（tabular-nums）：指标数字对齐不跳动（R50 通用提升） */
    font-variant-numeric: tabular-nums;
  }

  &__empty {
    padding: $up-space-4 0;
    text-align: center;
  }

  &__empty-text {
    font-size: $up-font-size-body-sm;
    color: $u-tips-color;
  }
}

.state-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 40vh;
  padding: $up-space-10;
  text-align: center;

  &__icon {
    width: 96rpx;
    height: 96rpx;
    border-radius: $up-radius-full;
    background-color: $u-primary-light;
    color: $u-primary;
    font-size: $up-font-size-caption;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: $up-space-5;
  }

  &__title {
    font-size: $up-font-size-h3;
    color: $u-main-color;
    font-weight: 600;
    margin-bottom: $up-space-3;
  }

  &__desc {
    font-size: $up-font-size-body-sm;
    color: $u-tips-color;
    line-height: 1.6;
    margin-bottom: $up-space-6;
  }

  &__btn {
    padding: $up-space-3 $up-space-8;
    background-color: $u-primary;
    border-radius: $up-radius-md;
  }

  &__btn-text {
    font-size: $up-font-size-body-sm;
    color: $u-white;
    font-weight: 500;
  }
}

/* AI 经营分析 */
.analysis-card {
  position: relative;
  background-color: $u-white;
  border: 1rpx solid $u-border-color;
  border-radius: $up-radius-lg;
  padding: $up-space-5;
  margin-top: $up-space-6;
  /* 与下方时间维度切换拉开间距（Token） */
  margin-bottom: $up-space-6;

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  &__title {
    font-size: $up-font-size-h3;
    font-weight: 600;
    color: $u-main-color;
  }

  &__btn {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 160rpx;
    padding: $up-space-2 $up-space-5;
    background-color: $u-primary;
    border-radius: $up-radius-sm;

    &--disabled {
      background-color: $u-light-color;
    }

    &--retry {
      margin-top: $up-space-4;
    }
  }

  &__btn-text {
    font-size: $up-font-size-body-sm;
    color: $u-white;
    font-weight: 500;
  }

  &__desc {
    display: block;
    margin-top: $up-space-2;
    font-size: $up-font-size-caption;
    color: $u-tips-color;
  }
}

.analysis-result {
  margin-top: $up-space-5;

  &__block {
    margin-bottom: $up-space-5;
  }

  &__title {
    display: block;
    font-size: $up-font-size-body-sm;
    font-weight: 600;
    color: $u-main-color;
    margin-bottom: $up-space-3;

    &--good {
      color: $u-success-dark;
    }

    &--bad {
      color: $u-warning-dark;
    }
  }

  &__summary {
    display: block;
    font-size: $up-font-size-body-sm;
    color: $u-content-color;
    line-height: 1.7;
    padding: $up-space-3;
    background-color: $u-bg-color;
    border-radius: $up-radius-sm;
  }

  &__item {
    display: flex;
    align-items: flex-start;
    gap: $up-space-2;
    padding: $up-space-2 0;
  }

  &__content {
    flex: 1;
    min-width: 0;
  }

  &__mark {
    flex-shrink: 0;
    width: 32rpx;
    height: 32rpx;
    border-radius: $up-radius-full;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: $up-font-size-mini;
    font-weight: 700;

    &--good {
      background-color: $u-success-light;
      color: $u-success-dark;
    }

    &--bad {
      background-color: $u-warning-light;
      color: $u-warning-dark;
    }
  }

  &__num {
    flex-shrink: 0;
    width: 32rpx;
    height: 32rpx;
    border-radius: $up-radius-full;
    background-color: $u-primary-light;
    color: $u-primary-dark;
    font-size: $up-font-size-mini;
    font-weight: 600;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  &__text {
    display: block;
    font-size: $up-font-size-body-sm;
    color: $u-content-color;
    line-height: 1.6;
  }

  &__reason {
    display: block;
    margin-top: $up-space-1;
    font-size: $up-font-size-caption;
    color: $u-tips-color;
    line-height: 1.5;
  }

  &__empty {
    font-size: $up-font-size-body-sm;
    color: $u-tips-color;
  }

  &__error {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: $up-space-6 0 $up-space-4;
  }

  &__error-text {
    font-size: $up-font-size-body-sm;
    color: $u-content-color;
    line-height: 1.6;
    text-align: center;
  }
}

/* 看板页头部操作区（F2-DC：刷新 + 清除数据并排） */
.board-header__ops {
  display: flex;
  align-items: center;
  gap: $up-space-2;
}

/* 清除数据按钮：危险弱化（红字白底红描边，§3.3 危险次按钮风格，不抢主操作） */
.board-header__clear {
  padding: $up-space-2 $up-space-4;
  background-color: $u-white;
  border: 1rpx solid $u-error;
  border-radius: $up-radius-sm;
  cursor: pointer;
  transition: background-color $up-ease-fast, color $up-ease-fast;

  &:active {
    background-color: $u-error;
  }
}

.board-header__clear-text {
  font-size: $up-font-size-caption;
  color: $u-error;

  .board-header__clear:active & {
    color: $u-white;
  }
}

/* ---------- 清除数据强提示弹窗（危险操作：遮罩/圆角/阴影/按钮全 Token，F2-DC） ---------- */
.dc-clear-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: $u-overlay;
}

.dc-clear-box {
  width: 92%;
  max-width: 560rpx;
  background-color: $u-white;
  border-radius: $up-radius-md;
  box-shadow: $up-shadow-xl;
  overflow: hidden;

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: $up-space-3 $up-space-5;
    border-bottom: 1rpx solid $u-border-color;
  }

  &__title {
    font-size: $up-font-size-h3;
    font-weight: 600;
    color: $u-error;
  }

  &__close {
    font-size: $up-font-size-h2;
    color: $u-tips-color;
    padding: $up-space-2;
  }

  &__body {
    padding: $up-space-5;
  }

  /* 危险徽标：错误浅底 + 红字（§3.4 错误 Tag 语义 Token） */
  &__badge {
    display: inline-block;
    padding: $up-space-1 $up-space-3;
    background-color: $u-error-light;
    border: 1rpx solid $u-tag-error-border;
    border-radius: $up-radius-full;
    font-size: $up-font-size-caption;
    font-weight: 500;
    color: $u-error-dark;
    margin-bottom: $up-space-3;
  }

  &__text {
    display: block;
    font-size: $up-font-size-body-sm;
    color: $u-content-color;
    line-height: 1.8;
  }

  &__actions {
    display: flex;
    gap: $up-space-3;
    margin-top: $up-space-6;
  }

  &__btn {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    height: 80rpx;
    border-radius: $up-radius-sm;
    cursor: pointer;
    transition: background-color $up-ease-fast, opacity $up-ease-fast;

    &--secondary {
      background-color: $u-white;
      border: 1rpx solid $u-border-color;

      &:active {
        background-color: $u-bg-color;
      }
    }

    /* 危险主按钮：红底白字（§3.3 危险主按钮） */
    &--danger {
      background-color: $u-error;
      border: 1rpx solid $u-error;

      &:active {
        background-color: $u-error-dark;
      }
    }

    &--disabled {
      opacity: 0.6;
    }
  }

  &__btn-text {
    font-size: $up-font-size-body;
    font-weight: $up-font-weight-medium;

    .dc-clear-box__btn--secondary & {
      color: $u-content-color;
    }

    .dc-clear-box__btn--danger & {
      color: $u-white;
    }
  }
}
</style>