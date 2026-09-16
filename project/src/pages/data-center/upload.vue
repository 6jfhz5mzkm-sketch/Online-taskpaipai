<!--
  @Page data-center/upload
  @Version 1.0.0
  @Description 数据分析专区-店铺数据上传独立页：展示 T2.5 店铺数据上传 6 个任务
               （T2.5.1 星级 / T2.5.2~4 交易·流量·商品 Excel / T2.5.5 商品数量 / T2.5.6 健康分），
               展开后复用 DataForm / ExcelUpload 组件；任务定义来自 GET /api/task/stages
               （stage_id=shopdata 分组，独立记录），进度来自既有 task-progress 接口；
               按 data_center_unlocked 展示锁定态（完成阶段二「商品发布」全部任务后解锁）。
-->
<template>
  <view class="page-layout">
    <Stage2Sidebar
      :stages="store.stage2Stages"
      :progress="store.progress"
      :active-index="0"
      :user-name="userName"
      @select="goGroup"
      @go-home="goHome"
    />

    <view class="main-content">
      <!-- 页头 -->
      <view class="page-header">
        <view class="page-header__back" @tap="goBack">
          <text class="page-header__back-text">← 返回</text>
        </view>
        <view class="page-header__title-row">
          <text class="page-header__title">店铺数据上传</text>
          <Badge
            :type="store.dataCenterUnlocked ? 'success' : 'warning'"
            :text="store.dataCenterUnlocked ? '已解锁' : '未解锁'"
          />
        </view>
        <text class="page-header__desc">上传店铺经营数据，供数据看板与 AI 经营分析使用</text>
        <!-- 重新观看引导（R60：清除共用标记并重放本页引导） -->
        <!-- 重新观看引导入口（仅开发环境显示，生产隐藏） -->
        <view v-if="IS_DEV" class="up-tour-replay" @tap="replayTour">
          <text class="up-tour-replay__text">重新观看引导</text>
        </view>
      </view>

      <!-- 上传进度（解锁后展示，方案 §6 遗留项 3：默认展示 x/6） -->
      <view v-if="store.dataCenterUnlocked" class="upload-progress">
        <Progress
          :percent="progress.percent"
          :label="`已上传 ${progress.completed}/${progress.total} 项`"
        />
      </view>

      <!-- 加载中：统一骨架屏 -->
      <LoadingSkeleton v-if="store.loading && shopdataTasks.length === 0" :rows="3" title />

      <!-- 锁定态：完成阶段二商品发布全部任务后解锁 -->
      <view v-else-if="!store.dataCenterUnlocked" class="state-box">
        <view class="state-box__icon">🔒</view>
        <text class="state-box__title">数据上传未解锁</text>
        <text class="state-box__desc">完成阶段二「商品发布」全部任务后解锁店铺数据上传</text>
        <view class="state-box__btn" @tap="goStage2Listing">
          <text class="state-box__btn-text">去完成商品发布</text>
        </view>
      </view>

      <!-- 解锁态：T2.5.1~T2.5.6 六个数据上传任务（3×2 网格卡片，响应式降 2/1 列） -->
      <template v-else>
        <view class="upload-grid">
          <CardMotion
            v-for="task in sortedShopdataTasks"
            :key="task.taskId"
            class="upload-card-wrap"
          >
          <view
            class="upload-card"
            :class="{ 'upload-card--completed': task.completionStatus === 'completed' }"
          >
            <!-- 卡片头部：勾选 + 标题/文案（+ 已完成角标，绝对定位在卡片右上角、不占位）；
                 卡片不再折起：点击头部/空白处不做任何事，交互区常显 -->
            <view class="upload-card__header">
              <!-- 勾选圈：仅切换手动完成态（store.toggleTask），不触发其它行为 -->
              <view
                class="upload-card__check"
                :class="{ 'upload-card__check--done': task.completionStatus === 'completed' }"
                @tap.stop="store.toggleTask(task.taskId)"
              >
                <text v-if="task.completionStatus === 'completed'" class="upload-card__check-icon">✓</text>
              </view>
              <view class="upload-card__content">
                <text
                  class="upload-card__title"
                  :class="{ 'upload-card__title--done': task.completionStatus === 'completed' }"
                >
                  {{ task.title }}
                </text>
                <!-- 描述行：描述 + 跳转外部工具入口（#F-29）。
                     入口文案与链接全部来自后端任务数据（actionText / actionUrl），前端不硬编码；
                     任一为空则不渲染（不会出现空按钮/点击无响应）；常驻入口，与完成态无关。 -->
                <view class="upload-card__desc-row">
                  <text class="upload-card__desc">{{ getDisplayTask(task).detail }}</text>
                  <view
                    v-if="shouldShowTaskAction(task)"
                    class="upload-card__action"
                    @tap.stop="handleTaskAction(task)"
                  >
                    <text class="upload-card__action-text">{{ task.actionText }}</text>
                  </view>
                </view>
              </view>
              <!-- 已完成角标：position:absolute 贴卡片右上角（top/right 取 Token），脱离文档流——
                   不再挤占内容区宽度，因此「按钮 + 描述」在完成/未完成两态下宽度完全一致 -->
              <view v-if="task.completionStatus === 'completed'" class="upload-card__badge">
                <text class="upload-card__badge-text">✓ 已完成</text>
              </view>
            </view>

            <!-- 卡片交互区：常显（内嵌 Excel 上传 / 数据表单）；卡片已无折起，故原 @tap.stop 防误触
                 已无保护对象，一并清理（点击事件不再有上层 tap 处理） -->
            <view class="upload-card__body">
              <ExcelUpload
                v-if="getTaskInteraction(task.taskId)?.startsWith('upload:')"
                :type="getUploadType(getTaskInteraction(task.taskId))"
                @complete="store.markTaskCompleted(task.taskId)"
              />
              <DataForm
                v-else-if="getTaskInteraction(task.taskId)?.startsWith('form:')"
                :form-key="getTaskInteraction(task.taskId)"
                @complete="store.markTaskCompleted(task.taskId)"
              />
            </view>
          </view>
          </CardMotion>
        </view>
      </template>

      <!-- 页脚：备案信息（工信部要求） -->
      <IcpFooter />
    </view>

    <!-- 数据上传页新手引导（账号级标记，首次进入显示） -->
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
import { trackPageView, trackEvent, EventType } from '@/utils/track';
import { useStage2Store } from '@/store/modules/stage2';
import { getTaskInteraction } from '@/utils/stage2';
import { openExternalLink } from '@/utils/link';
import { getMerchantNickname } from '@/utils/merchant';
import { fetchTourSeen, markTourSeen, resetTourSeen } from '@/api/tour';
import type { SecondLevelTask } from '@/types/task';
import Stage2Sidebar from '@/components-local/stage2/Stage2Sidebar.vue';
import ExcelUpload from '@/components-local/stage2/ExcelUpload.vue';
import DataForm from '@/components-local/stage2/DataForm.vue';
import Badge from '@/components/Badge/index.vue';
import Progress from '@/components/Progress/index.vue';
import LoadingSkeleton from '@/components/LoadingSkeleton/index.vue';
import CardMotion from '@/components/CardMotion/index.vue';
import ProductTour, { type TourStep } from '@/components/ProductTour/index.vue';
import IcpFooter from '@/components/IcpFooter/index.vue';

const store = useStage2Store();
const userName = ref('');

/* ---------- 数据上传页新手引导（账号级：GET/POST /api/tour/seen） ---------- */
const tourActive = ref(false);
/** 开发环境标识：生产（build）不渲染「重新观看引导」入口（vite import.meta.env.DEV） */
const IS_DEV = import.meta.env.DEV;

/** 数据上传页引导步骤（合并「填写表单 + Excel 上传」为一步，归属本页） */
const TOUR_STEPS: TourStep[] = [
  {
    title: '填写并上传店铺数据',
    text: '手动填写星级/商品数量/健康分，或上传交易/流量/商品 Excel，提交即完成任务（每行 3 张卡片对应一个数据项）。',
    target: '.upload-card',
    placement: 'bottom',
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

/** shopdata 全部二级任务（T2.5.1~T2.5.6，按后端返回顺序平铺） */
const shopdataTasks = computed<SecondLevelTask[]>(() =>
  (store.dataCenterStages[0]?.firstLevelTasks || []).flatMap((flt) => flt.secondLevelTasks || []),
);

/** 按交互类型分行排序：手动输入（form:）组在前、Excel 上传（upload:）组在后，
 *  3 个手动 + 3 个上传 = 每行 3 张共 2 行（3×2 网格），同行类型一致 */
const sortedShopdataTasks = computed<SecondLevelTask[]>(() => {
  const tasks = shopdataTasks.value;
  const formTasks = tasks.filter((t) => getTaskInteraction(t.taskId)?.startsWith('form:'));
  const uploadTasks = tasks.filter((t) => getTaskInteraction(t.taskId)?.startsWith('upload:'));
  return [...formTasks, ...uploadTasks];
});

/** 数据上传进度（x/6） */
const progress = computed(() => store.dataCenterProgress);

/** 展示用任务副本：detail 为空时回退到 description（后端暂未写 detail） */
function getDisplayTask(task: SecondLevelTask): SecondLevelTask {
  const display = { ...task };
  if (!display.detail) {
    display.detail = display.description;
  }
  return display;
}

/** 是否渲染卡片跳转入口（纯数据驱动，6 张数据上传卡片统一）：
 *  后端下发 actionText 与 actionUrl **双非空**即渲染（缺任一不渲染，避免空按钮/点击无响应）；
 *  与任务完成态无关——它是「去京东各工具页」的常驻入口。
 *  演进：#F-29 建立（仅健康分卡片，用交互键白名单限定）→ #F-30 去掉白名单，改为纯数据驱动。 */
function shouldShowTaskAction(task: SecondLevelTask): boolean {
  return Boolean(task.actionText && task.actionUrl);
}

/** 点击跳转入口：新窗口打开后端下发的 actionUrl
 *  （埋点与既有 TaskCard 操作按钮一致；window.open 必须在 tap 同步调用栈内完成，故不加 await） */
function handleTaskAction(task: SecondLevelTask): void {
  trackEvent(EventType.ACTION_CLICK, {
    taskKey: task.taskId,
    meta: { action_text: task.actionText || '', action_url: task.actionUrl || '' },
  });
  openExternalLink(task.actionUrl);
}

/** 解析上传类型（upload:trade -> trade） */
function getUploadType(interaction: string | undefined): 'trade' | 'traffic' | 'product' {
  const type = interaction?.replace('upload:', '');
  return type === 'trade' || type === 'traffic' || type === 'product' ? type : 'trade';
}

/** 侧边栏点击分组：回阶段二主页并定位到对应分组 */
function goGroup(idx: number) {
  uni.navigateTo({ url: `/pages/stage2/index?group=${idx}` });
}

/** 返回任务中心 */
function goHome() {
  uni.reLaunch({ url: '/pages/index/index' });
}

/** 去阶段二「商品发布」（T2.2，listing）分组 */
function goStage2Listing() {
  const idx = store.stage2Stages.findIndex((s) => s.stageId === 'listing');
  uni.navigateTo({ url: `/pages/stage2/index?group=${Math.max(0, idx)}` });
}

/** 返回上一页（来源页：阶段二主页 / 数据看板 / 任务中心） */
function goBack() {
  const pages = getCurrentPages();
  if (pages.length > 1) {
    uni.navigateBack();
  } else {
    uni.reLaunch({ url: '/pages/stage2/index' });
  }
}

onMounted(async () => {
  trackPageView('data-center-upload');
  // 用户名：唯一读取入口 @/utils/merchant（未登录返回空串 → 侧栏/顶栏用户区不渲染）
  userName.value = getMerchantNickname();
  if (store.stages.length === 0) {
    await store.fetchStages();
  }
  store.restoreProgress();
  // 首次进入且共用引导未看过 → 延迟启动 Tour（等 DOM 就绪）
  setTimeout(() => maybeStartTour(), 500);
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

.page-header {
  margin-bottom: $up-space-6;

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

  &__tag {
    padding: $up-space-1 $up-space-4;
    border-radius: $up-radius-full;
    background-color: $u-primary-light;

    &--locked {
      background-color: $u-warning-light;
    }
  }

  &__tag-text {
    font-size: $up-font-size-caption;
    color: $u-primary-dark;
    font-weight: 500;

    .page-header__tag--locked & {
      color: $u-warning-dark;
    }
  }

  &__desc {
    display: block;
    margin-top: $up-space-2;
    font-size: $up-font-size-body-sm;
    color: $u-tips-color;
  }
}

/* 重新观看引导入口（轻量：caption 主色文字，右对齐） */
.up-tour-replay {
  display: flex;
  justify-content: flex-end;
  margin-top: $up-space-2;

  &__text {
    font-size: $up-font-size-caption;
    color: $u-primary;
    font-weight: 500;
  }
}

/* 上传进度 */
.upload-progress {
  margin-bottom: $up-space-6;
  padding: $up-space-4 $up-space-5;
  background-color: $u-white;
  border: 1rpx solid $u-border-color;
  border-radius: $up-radius-md;

  &__text {
    display: block;
    font-size: $up-font-size-body-sm;
    color: $u-content-color;
    margin-bottom: $up-space-2;
  }

  &__bar {
    height: 8rpx;
    background-color: $u-border-color;
    border-radius: 4rpx;
    overflow: hidden;
  }

  &__fill {
    height: 100%;
    background-color: $u-primary;
    border-radius: 4rpx;
    transition: width 0.3s ease;
  }
}

/* 解锁态任务区：3 列网格卡片（flex wrap，每行 3 张、共 2 行；响应式降 2/1 列） */
.upload-grid {
  display: flex;
  flex-wrap: wrap;
  gap: $up-space-3;
}

/* CardMotion 外层承担 3 列 flex item 角色：calc 精确扣除 2 个 gap；box-sizing 防超限换行；
   min-width:0 允许收缩到计算列宽（防内容撑破列宽） */
.upload-card-wrap {
  width: calc((100% - #{$up-space-3} * 2) / 3);
  min-width: 0;
  box-sizing: border-box;
}

.upload-card {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%; /* 同行卡片高度统一：填满 CardMotion（flex stretch 等高） */
  background-color: $u-white;
  /* 定位上下文：已完成角标绝对定位到卡片右上角（不占位） */
  position: relative;
  border: 1rpx solid $u-border-color;
  border-radius: $up-radius-lg;
  transition: background-color $up-ease-normal, border-color $up-ease-normal;

  /* 完成态：浅绿底 + 绿边（参考既有 TaskCard 视觉语言） */
  &--completed {
    background-color: $u-success-light;
    border-color: $u-success-dark;
  }

  &__header {
    display: flex;
    align-items: flex-start;
    padding: $up-space-4;
  }

  /* 勾选圈：未完成空心边框，完成态主色实心 + 白色对勾（§3.2 主色/§3.3） */
  &__check {
    flex-shrink: 0;
    width: 36rpx;
    height: 36rpx;
    margin-top: 2rpx;
    margin-right: $up-space-2;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 2rpx solid $u-border-color;
    border-radius: $up-radius-full;

    &--done {
      background-color: $u-primary;
      border-color: $u-primary;
    }
  }

  &__check-icon {
    color: $u-white;
    font-size: $up-font-size-mini;
    font-weight: 600;
  }

  &__content {
    flex: 1;
    min-width: 0;
  }

  &__title {
    display: block;
    font-size: $up-font-size-body-sm;
    font-weight: 600;
    color: $u-main-color;
    line-height: 1.5;
    margin-bottom: $up-space-1;

    /* 完成态：置灰 + 划线；并仅在标题上做右侧避让，防长标题首行尾巴被角标压住。
       避让宽度 = 角标实测宽（57px）+ 与内容的间距（8px）≈ 65px，取 Token 组合 68px
       （48 + 20）留余量——只影响标题换行盒，不影响按钮/描述宽度 */
    &--done {
      color: $u-tips-color;
      text-decoration: line-through;
      padding-right: calc(#{$up-space-12} + #{$up-space-5});
    }
  }

  /* 描述行：描述（可收缩，2 行截断）+ 跳转入口（不收缩）；同一行、间距取 Token */
  &__desc-row {
    display: flex;
    align-items: center;
    gap: $up-space-2;
  }

  /* 任务文案：最多 2 行截断，窄卡片不撑破；作为 flex 子项显式 min-width:0 允许收缩（§5.5） */
  &__desc {
    flex: 1;
    min-width: 0;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    overflow: hidden;
    font-size: $up-font-size-caption;
    color: $u-tips-color;
    line-height: 1.6;
  }

  /* 跳转外部工具入口（#F-29）：观感与阶段二任务卡操作按钮同款（主色实心 + 白字 + $up-radius-sm），
     尺寸按本页卡片层级降档——字号取 caption，内边距取 $up-space-1 / $up-space-3（4px / 12px），
     不照抄 TaskCard 的 10rpx / 24rpx（那是阶段二任务卡栅格）；按钮不收缩、文案不换行 */
  &__action {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: $up-space-1 $up-space-3;
    background-color: $u-primary;
    border-radius: $up-radius-sm;
    transition: background-color $up-ease-fast;

    &:hover {
      background-color: $u-primary-dark;
    }

    &:active {
      background-color: $u-primary-dark;
    }
  }

  &__action-text {
    font-size: $up-font-size-caption;
    line-height: $up-line-height-normal;
    color: $u-white;
    white-space: nowrap;
  }

  /* 已完成角标：绝对定位贴卡片右上角（Token 间距），脱离文档流——
     完成态与未完成态的「按钮 + 描述」宽度因此完全一致（#F-31 用户诉求） */
  &__badge {
    position: absolute;
    top: $up-space-2;
    right: $up-space-2;
    padding: 2rpx 12rpx;
    border-radius: $up-radius-full;
    background-color: $u-white;
  }

  &__badge-text {
    font-size: $up-font-size-mini;
    color: $u-success;
    font-weight: 500;
  }

  /* 交互区：常显（内嵌 ExcelUpload / DataForm，组件自带容器与间距）；
     flex:1 使交互区铺满卡片剩余高度，同行卡片视觉对齐 */
  &__body {
    flex: 1;
    padding: 0 $up-space-4 $up-space-4;
  }
}

/* 响应式降列：桌面（≥900px）稳定 3 列 × 2 行；中等视口（<900px）降 2 列、手机（<600px）降 1 列 */
@media (max-width: 900px) {
  .upload-card-wrap {
    width: calc((100% - #{$up-space-3}) / 2);
  }

  /* 断点决策（#F-29 实测 → #F-30 用户确认，2026-09-15）：≥900px 三列时按钮与描述**同行**
     （贴合「描述旁边」）；**≤900px 起换行到描述下方**——依据是本档位卡片内容宽不足以同时容纳
     「2 行截断描述 + 按钮」，实测 768px 时描述仅剩 ~43px、375px 时 ~87px（等于把描述压成每行 3~7 字）。
     用户已明确接受该换行策略，后续若要改回同行须先确认。 */
  .upload-card__desc-row {
    flex-wrap: wrap;
  }

  .upload-card__desc {
    flex: 1 1 100%;
  }
}

@media (max-width: 600px) {
  .upload-card-wrap {
    width: 100%;
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
    font-size: $up-font-size-h3;
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
</style>
