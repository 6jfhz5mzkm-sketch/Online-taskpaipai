<template>
  <view class="page-container">
    <view class="page-header">
      <text class="page-title">进度概览</text>
      <text class="page-subtitle">入驻准备阶段任务完成情况</text>
    </view>

    <!-- 加载态 -->
    <template v-if="loading">
      <view class="section-card">
        <LoadingSkeleton :rows="2" title />
      </view>
      <view class="section-card">
        <LoadingSkeleton :rows="3" />
      </view>
    </template>

    <!-- 空态：无任务数据 -->
    <view v-else-if="stageList.length === 0" class="section-card">
      <EmptyState text="暂无进度数据" sub-text="完成任务后此处将展示阶段进度" />
    </view>

    <!-- 数据态 -->
    <template v-else>
      <!-- 总体进度 -->
      <view class="overview-grid">
        <StatCard label="任务总数" :value="overall.total" icon="📋" color="info" />
        <StatCard label="已完成" :value="overall.completed" icon="✅" color="success" />
        <StatCard label="完成率" :value="overall.percent" unit="%" icon="📈" color="primary" />
      </view>

      <view class="section-card">
        <view class="section-card__header">
          <text class="section-title">总体进度</text>
          <Badge
            :type="overall.percent === 100 ? 'success' : 'info'"
            :text="overall.percent === 100 ? '已完成' : '进行中'"
          />
        </view>
        <Progress :percent="overall.percent" :label="'总体进度 ' + overall.percent + '%'" height="thick" />
      </view>

      <!-- 各阶段进度 -->
      <view
        v-for="stage in stageList"
        :key="stage.stageId"
        class="section-card"
      >
        <view class="section-card__header">
          <text class="section-title">{{ stage.title }}</text>
          <text class="section-card__stage-num">第 {{ stage.stageNum }} 步</text>
        </view>
        <Progress
          :percent="stageProgress(stage).percent"
          :label="stageProgress(stage).completed + ' / ' + stageProgress(stage).total"
          :color="stageProgress(stage).percent === 100 ? 'success' : 'primary'"
        />
      </view>
    </template>

    <!-- 页脚：备案信息（工信部要求） -->
    <IcpFooter />
  </view>
</template>

<script setup lang="ts">
/**
 * 进度概览页
 * @description 展示阶段一（入驻准备）总体与各阶段任务进度：指标卡 + 阶段进度条 + 空态/加载态统一。
 */
import { ref, computed, onMounted } from 'vue';
import { useTaskStore } from '@/store/modules/task';
import type { StageInfo } from '@/types/task';
import { computeStageProgress } from '@/utils/stage2';
import StatCard from '@/components/StatCard/index.vue';
import Progress from '@/components/Progress/index.vue';
import Badge from '@/components/Badge/index.vue';
import EmptyState from '@/components/EmptyState/index.vue';
import LoadingSkeleton from '@/components/LoadingSkeleton/index.vue';
import IcpFooter from '@/components/IcpFooter/index.vue';

const taskStore = useTaskStore();
const loading = ref(false);

/** 阶段一 stage 列表 */
const stageList = computed<StageInfo[]>(() => taskStore.stage1Stages as StageInfo[]);

/** 总体进度（含阶段一全部启用任务） */
const overall = computed(() => taskStore.progress);

/** 单阶段进度（仅统计该 stage 内启用任务） */
function stageProgress(stage: StageInfo): { total: number; completed: number; percent: number } {
  return computeStageProgress([stage]);
}

onMounted(async () => {
  loading.value = true;
  try {
    if (taskStore.stages.length === 0) {
      await taskStore.fetchStages();
      await taskStore.restoreProgress();
    }
  } finally {
    loading.value = false;
  }
});
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.page-container {
  min-height: 100vh;
  background-color: $u-bg-color;
  padding: $up-space-4;
  padding-bottom: $up-space-8;
}

.page-header {
  padding: $up-space-6 0 $up-space-4;
}

.page-title {
  font-size: $up-font-size-h1;
  font-weight: $up-font-weight-bold;
  color: $u-main-color;
}

.page-subtitle {
  display: block;
  margin-top: $up-space-1;
  font-size: $up-font-size-caption;
  color: $u-tips-color;
}

/* 总体指标卡栅格：移动端自适应（每行最多 3 个，窄屏自动换行） */
.overview-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: $up-space-3;
  margin-bottom: $up-space-4;

  @media (max-width: 360px) {
    grid-template-columns: 1fr;
  }
}

.section-card {
  background-color: $u-white;
  border-radius: $up-radius-lg;
  padding: $up-space-5;
  margin-bottom: $up-space-4;
  box-shadow: $up-shadow-md;

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: $up-space-4;
  }

  &__stage-num {
    font-size: $up-font-size-caption;
    font-weight: $up-font-weight-medium;
    color: $u-tips-color;
    font-variant-numeric: tabular-nums;
  }
}

.section-title {
  font-size: $up-font-size-h3;
  font-weight: $up-font-weight-bold;
  color: $u-main-color;
}
</style>
