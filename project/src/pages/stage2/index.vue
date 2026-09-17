<!--
  @Page stage2/index
  @Version 1.2.0
  @Description 阶段二（开店搭建）主页：左侧导航 + 右侧内容，与阶段一布局一致；
               T2.1-T2.4 共 27 个任务按后端返回顺序展示（T2.5 店铺数据上传已剥离至数据分析专区）；
               交互组件（商标搜索/Excel 上传/表单）绑定在任务卡展开区内；
               T2.1.4 提供企微二维码按钮+弹窗；侧边栏高亮随页面滚动联动；
               顶部数据看板入口跳转数据分析专区看板页（pages/data-center/index）。
-->
<template>
  <view class="page-layout">
    <Stage2Sidebar
      :stages="stage2Stages"
      :progress="store.progress"
      :active-index="activeIndex"
      :user-name="userName"
      :auto-prompt-category="autoPromptCategory"
      :category-unsaved="categoryUnsaved"
      @select="scrollToStage"
      @go-home="goHome"
      @category-closed="handleCategoryDialogClosed"
      @category-saved="handleCategorySaved"
    />

    <view class="main-content">
      <!-- 加载中：统一骨架屏 -->
      <LoadingSkeleton v-if="store.loading && stage2Stages.length === 0" :rows="3" title />

      <!-- 未解锁 -->
      <view v-else-if="!store.unlocked" class="state-box">
        <view class="state-box__icon">2</view>
        <text class="state-box__title">阶段二未解锁</text>
        <text class="state-box__desc">{{ unlockHint || '完成阶段一全部任务后开启开店搭建' }}</text>
        <view class="state-box__btn" @tap="goHome">
          <text class="state-box__btn-text">返回任务中心</text>
        </view>
      </view>

      <!-- 已解锁：5 个一级任务分组 -->
      <template v-else>
        <!-- 重新观看引导（轻量入口，R60 补充：清除已看标记并强制重放 Tour） -->
        <!-- 重新观看引导入口（仅开发环境显示，生产隐藏） -->
        <view v-if="IS_DEV" class="tour-replay" @tap="replayTour">
          <text class="tour-replay__text">重新观看引导</text>
        </view>

        <!-- 数据看板入口（指向数据分析专区看板页；旧路由 pages/stage2/data-board 保留兼容跳转） -->
        <CardMotion>
          <view class="board-entry" @tap="goBoard">
            <view class="board-entry__info">
              <text class="board-entry__title">数据看板</text>
              <text class="board-entry__desc">按时间维度查看已上传的店铺经营数据与 AI 经营分析</text>
            </view>
            <view class="board-entry__btn">
              <text class="board-entry__btn-text">进入</text>
            </view>
          </view>
        </CardMotion>

        <view
          v-for="(stage, sIdx) in stage2Stages"
          :key="stage.stageId"
          :id="'flt-' + stage.stageId"
          class="stage-section"
        >
          <StageHeader
            :stage-num="sIdx + 1"
            :title="stage.title"
            :button-text="getGroupButtonText(stage)"
            :completed="isGroupCompleted(stage)"
            @complete="handleCompleteGroup(stage)"
          />

          <view v-for="flt in stage.firstLevelTasks" :key="flt.taskId" class="first-level-task-group">
            <TaskCard
              v-for="(task, tIdx) in flt.secondLevelTasks"
              :key="task.taskId"
              :task="getDisplayTask(task)"
              :tick-delay="tIdx * 40"
              :show-detail="
                hasTaskActionType(task, 'trademark_lookup') || hasTaskActionType(task, 'title_optimize')
              "
              @toggle="handleTaskToggle(task)"
              @action="handleTaskAction"
            >
              <!-- 右侧附加操作：商品发布（T2.2）「查看图片示例」常显按钮 + T2.3.2「AI 优化主图」按钮 -->
              <template #right-extra>
                <view
                  v-if="hasGuideImages(task.taskId)"
                  class="guide-entry"
                  @tap.stop="openGuide(task)"
                >
                  <text class="guide-entry__text">查看图片示例</text>
                </view>
                <view
                  v-if="hasTaskActionType(task, 'image_optimize')"
                  class="guide-entry guide-entry--ai"
                  @tap.stop="openImageOptimize"
                >
                  <text class="guide-entry__text">AI 优化主图</text>
                </view>
              </template>
              <!-- 详情区扩展：任务展开即见搜索/上传/填写/催审入口 -->
              <template #detail-extra>
                <!-- @tap.stop 防止操作交互区时误触卡片展开/收起 -->
                <view @tap.stop>
                <!-- 行为分发（#FE-29）：唯一依据 = 后端 actionType（缺失/未知按 none），不再按 taskId 判断 -->
                <!-- title_optimize：AI 商品标题优化（accordion 面板） -->
                <TitleOptimizePanel v-if="hasTaskActionType(task, 'title_optimize')" />
                <TrademarkSearch
                  v-if="hasTaskActionType(task, 'trademark_lookup')"
                  @complete="store.markTaskCompleted(task.taskId)"
                />
                <view v-else-if="hasTaskActionType(task, 'advisor_entry')" class="advisor-entry">
                  <text class="advisor-entry__subtitle">联系拍拍商家顾问催审</text>
                  <text class="advisor-entry__desc">审核周期较长时可添加拍拍商家顾问企微催审，获取一对一开店指导。</text>
                </view>
                <ExcelUpload
                  v-else-if="hasTaskActionType(task, 'data_upload') && resolveDataUploadType(task)"
                  :type="resolveDataUploadType(task)"
                  @complete="store.markTaskCompleted(task.taskId)"
                />
                <DataForm
                  v-else-if="hasTaskActionType(task, 'data_form') && resolveDataFormKey(task)"
                  :form-key="resolveDataFormKey(task)"
                  @complete="store.markTaskCompleted(task.taskId)"
                />
                </view>
              </template>
            </TaskCard>
          </view>
        </view>
      </template>

      <!-- 页脚：备案信息（工信部要求） -->
      <IcpFooter />
    </view>

    <!-- 商家顾问企微二维码弹窗（参考阶段一 T1.3.8） -->
    <view v-if="showQRModal" class="modal-mask" @tap="showQRModal = false">
      <view class="modal-box modal-box--large" @tap.stop>
        <view class="modal-header">
          <text class="modal-title">添加商家顾问</text>
          <text class="modal-close" @tap="showQRModal = false">×</text>
        </view>
        <view class="modal-body">
          <view class="qr-code-area">
            <image :src="qrCodeUrl" mode="aspectFit" class="qr-code-image" />
          </view>
          <view class="modal-text">添加话术：您好，我是XX店铺负责人，商家ID：XXXXXXXX，现在提交了品牌申请，辛苦审核</view>
          <view class="modal-hint">添加商家顾问可获得一对一开店指导</view>
        </view>
      </view>
    </view>

    <!-- 一级任务组「全部取消」二次确认弹窗（自定义弹窗，符合设计规范：遮罩/圆角/阴影/按钮全 Token） -->
    <view v-if="showGroupCancelModal" class="modal-mask" @tap="closeGroupCancelModal">
      <view class="modal-box group-cancel-modal" @tap.stop>
        <view class="modal-header">
          <text class="modal-title">取消完成</text>
          <text class="modal-close" @tap="closeGroupCancelModal">×</text>
        </view>
        <view class="modal-body">
          <text class="group-cancel-modal__text">
            确定取消「{{ pendingCancelStage?.title || '' }}」全部任务的完成状态吗？取消后需重新完成该组任务。
          </text>
          <!-- 组级取消告知（F2-GROUPCANCEL / F2-CANCELTEXT；B11 修正文案使其与实现一致）：商品发布组 + 数据专区已解锁 → 告知「取消只标记未完成、不删除已上传的店铺数据」。
               实现见 confirmCancelGroup → store.completeStage，全程不调用 clearShopData（数据删除仅由数据看板「清除数据」显式触发） -->
          <text
            v-if="pendingCancelStage?.stageId === 'listing' && store.dataCenterUnlocked"
            class="group-cancel-modal__notice"
          >
            取消只会把任务标记为未完成，不会删除已上传的店铺数据。
          </text>
          <view class="group-cancel-modal__actions">
            <view class="group-cancel-modal__btn group-cancel-modal__btn--secondary" @tap="closeGroupCancelModal">
              <text class="group-cancel-modal__btn-text">再想想</text>
            </view>
            <view class="group-cancel-modal__btn group-cancel-modal__btn--danger" @tap="confirmCancelGroup">
              <text class="group-cancel-modal__btn-text">确认取消</text>
            </view>
          </view>
        </view>
      </view>
    </view>

    <!-- 取消商品发布（listing）任务告知弹窗（F2-CANCELTEXT；B11 修正文案使其与实现一致）：数据专区已解锁时告知「取消只标记未完成、不删除已上传的店铺数据」
         （confirmListingCancel → store.toggleTask，不调用 clearShopData） -->
    <view v-if="showListingCancelTip" class="modal-mask" @tap="closeListingCancelTip">
      <view class="modal-box group-cancel-modal" @tap.stop>
        <view class="modal-header">
          <text class="modal-title">提示</text>
          <text class="modal-close" @tap="closeListingCancelTip">×</text>
        </view>
        <view class="modal-body">
          <text class="group-cancel-modal__text">
            取消「{{ pendingListingCancelTask?.title || '商品发布' }}」只会把任务标记为未完成，不会删除已上传的店铺数据。确认继续取消吗？
          </text>
          <view class="group-cancel-modal__actions">
            <view class="group-cancel-modal__btn group-cancel-modal__btn--secondary" @tap="closeListingCancelTip">
              <text class="group-cancel-modal__btn-text">暂不取消</text>
            </view>
            <view class="group-cancel-modal__btn group-cancel-modal__btn--primary" @tap="confirmListingCancel">
              <text class="group-cancel-modal__btn-text">继续取消</text>
            </view>
          </view>
        </view>
      </view>
    </view>

    <!-- 商品发布任务图片示例弹窗（skeleton/shimmer 加载态 + 缩略图平铺 + 点击放大） -->
    <ProductGuideModal
      v-model="guideModalVisible"
      :images="guideImages"
      :title="guideTitle"
    />

    <!-- T2.3.2 商品主图 AI 优化弹窗（左上传图片 / 右 AI 建议 / 可复制） -->
    <ImageOptimizeModal v-model="imageOptimizeVisible" />

    <!-- 阶段二新商家引导 Tour（首次进入显示，spotlight + tooltip） -->
    <ProductTour
      v-model="tourActive"
      :steps="TOUR_STEPS"
      @complete="onTourComplete"
      @skip="onTourComplete"
    />
  </view>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue';
import { onLoad, onPageScroll } from '@dcloudio/uni-app';
import { trackPageView, trackEvent, EventType } from '@/utils/track';
import { fetchMerchantCategories } from '@/api/category';
import { useStage2Store } from '@/store/modules/stage2';
import {
  hasTaskActionType,
  isTaskEnabled,
  isTaskCompleted,
  resolveDataFormKey,
  resolveDataUploadType,
} from '@/utils/stage2';
import { getMerchantNickname } from '@/utils/merchant';
import { getAdvisorQrCodeUrl } from '@/api/stage2';
import { PRODUCT_GUIDE_IMAGES } from '@/constants/productGuide';
import type { StageInfo, SecondLevelTask } from '@/types/task';
import Stage2Sidebar from '@/components-local/stage2/Stage2Sidebar.vue';
import TrademarkSearch from '@/components-local/stage2/TrademarkSearch.vue';
import ExcelUpload from '@/components-local/stage2/ExcelUpload.vue';
import DataForm from '@/components-local/stage2/DataForm.vue';
import TaskCard from '@/components/TaskCard/index.vue';
import StageHeader from '@/components/StageHeader/index.vue';
import ProductGuideModal from '@/components-local/stage2/ProductGuideModal.vue';
import ImageOptimizeModal from '@/components-local/stage2/ImageOptimizeModal.vue';
import TitleOptimizePanel from '@/components-local/stage2/TitleOptimizePanel.vue';
import { useEscapeClose } from '@/composables/useEscapeClose';
import { fetchTourSeen, markTourSeen, resetTourSeen } from '@/api/tour';
import LoadingSkeleton from '@/components/LoadingSkeleton/index.vue';
import CardMotion from '@/components/CardMotion/index.vue';
import ProductTour, { type TourStep } from '@/components/ProductTour/index.vue';
import IcpFooter from '@/components/IcpFooter/index.vue';

const store = useStage2Store();
const activeIndex = ref(0);
const userName = ref('');
const showQRModal = ref(false);
const qrCodeUrl = getAdvisorQrCodeUrl();

// 企微二维码弹窗支持 ESC 键关闭（仅弹窗可见时生效）
useEscapeClose(() => showQRModal.value, () => { showQRModal.value = false; });

/** 一级任务组「全部取消」二次确认弹窗状态（复用阶段一逻辑，防误触取消整组） */
const showGroupCancelModal = ref(false);
const pendingCancelStage = ref<StageInfo | null>(null);
useEscapeClose(() => showGroupCancelModal.value, () => { showGroupCancelModal.value = false; });

/** 取消商品发布（listing）任务告知弹窗：数据专区已解锁时先行告知（F2-DC） */
const showListingCancelTip = ref(false);
const pendingListingCancelTask = ref<SecondLevelTask | null>(null);
useEscapeClose(() => showListingCancelTip.value, () => { closeListingCancelTip(); });

/** 商品发布图片示例弹窗状态 */
const guideModalVisible = ref(false);
const guideImages = ref<string[]>([]);
const guideTitle = ref('');

/** T2.3.2 商品主图 AI 优化弹窗状态 */
const imageOptimizeVisible = ref(false);

/** 打开 AI 优化主图弹窗 */
function openImageOptimize() {
  imageOptimizeVisible.value = true;
}


/* ---------- 阶段二 Product Tour（新商家首次进入引导，R60） ---------- */
const tourActive = ref(false);
/** 开发环境标识：生产（build）不渲染「重新观看引导」入口（vite import.meta.env.DEV） */
const IS_DEV = import.meta.env.DEV;

/** 阶段二 Tour 步骤（8 步：欢迎/搜索商标/数据看板/查看图例/展开/表单/AI主图/上传数据） */
const TOUR_STEPS: TourStep[] = [
  {
    title: '欢迎来到阶段二 · 开店搭建',
    text: '这里是开店搭建任务中心：完成品牌申请、商品发布、商品优化等任务，逐步完成店铺搭建。',
    focus: false,
  },
  {
    title: '搜索商标注册号',
    text: '在「查询商标注册号」任务中输入品牌名称即可查询。示例：输入「小米」，将返回小米的申请/注册号（如 10674581 / 10979463）。',
    target: '.trademark-search',
  },
  {
    title: '查看图片示例',
    text: '商品发布任务右侧的「查看图片示例」按钮，可查看各任务的图文操作指引（页面已自动滚动到该区域）。',
    target: '.guide-entry',
    placement: 'left',
  },
  {
    title: '点击任务卡展开',
    text: '点击任务卡可展开详情区，查看任务引导与操作入口。',
    target: '.task-card',
    placement: 'left',
  },
  {
    title: 'AI 优化主图',
    text: '商品优化任务提供「AI 优化主图」：上传主图即可获得合规核查与优化建议。',
    target: '.guide-entry--ai',
    placement: 'left',
  },
];

/* ---------- 经营类目首入引导（未保存才弹；跳过仅本次驻留生效，不写库、不落持久标记） ---------- */

/** 未保存经营类目 → 置 true 通知侧栏弹窗（本次驻留只置一次） */
const autoPromptCategory = ref(false);
/** 经营类目是否尚未保存（与 autoPromptCategory 同源：同一次查询侧结果得出，供侧栏入口小红点显隐） */
const categoryUnsaved = ref(false);
/** 本次驻留是否已判定过经营类目（避免重复查询/重复弹窗） */
let categoryPromptChecked = false;
/** 本次驻留的经营类目弹窗是否由本页自动打开（用于把 Tour 排在其后，避免弹层叠加） */
let categoryDialogAutoOpened = false;

/**
 * 首次进入引导链：经营类目（未保存则自动弹窗） → Tour。
 * 经营类目弹窗由侧栏实例承载，本页只负责判定与排序（弹窗关闭后由 handleCategoryDialogClosed 续跑 Tour）。
 */
function continueFirstEntryGuidance(): void {
  void maybePromptCategory();
}

/** 查询已保存经营类目（API-07 查询侧）：未保存 → 通知侧栏自动弹窗；已保存/查询失败 → 直接走 Tour */
async function maybePromptCategory(): Promise<void> {
  if (categoryPromptChecked) {
    maybeStartTour();
    return;
  }
  categoryPromptChecked = true;
  try {
    const saved = await fetchMerchantCategories();
    // 单一真源：同一次查询结果同时决定「是否自动弹窗」与「入口小红点」，两处不可能不一致
    categoryUnsaved.value = !(saved && saved.length > 0);
    if (!categoryUnsaved.value) {
      maybeStartTour();
      return;
    }
  } catch (err) {
    // 查询失败不打扰用户（request 封装已按失败原因提示），也不阻塞 Tour；此时不臆断「未保存」，红点保持隐藏
    console.warn('[经营类目] 已保存类目查询失败，跳过自动弹窗', err);
    maybeStartTour();
    return;
  }
  // 未保存：自动弹经营类目弹窗（可跳过）；Tour 等弹窗关闭后再走，避免两层引导叠加
  categoryDialogAutoOpened = true;
  autoPromptCategory.value = true;
  trackEvent(EventType.ACTION_CLICK, { element: 'category', meta: { action: 'auto_open' } });
}

/** 保存成功：立即把「未保存」翻转为已保存（侧栏小红点即时消失，不等重新进页面） */
function handleCategorySaved(): void {
  categoryUnsaved.value = false;
}

/** 经营类目弹窗关闭（跳过/保存/×/遮罩/ESC 任一）：若是本页自动打开的，续跑 Tour */
function handleCategoryDialogClosed(): void {
  if (!categoryDialogAutoOpened) return;
  categoryDialogAutoOpened = false;
  maybeStartTour();
}

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

/** 任务是否有图片示例（无映射或空数组 → 不显示按钮，如 T2.2.9/T2.2.13） */
function hasGuideImages(taskId: string): boolean {
  return (PRODUCT_GUIDE_IMAGES[taskId]?.length || 0) > 0;
}

/** 打开图片示例弹窗 */
function openGuide(task: SecondLevelTask) {
  const images = PRODUCT_GUIDE_IMAGES[task.taskId] || [];
  if (images.length === 0) return;
  guideImages.value = images;
  guideTitle.value = task.title;
  guideModalVisible.value = true;
}

/** 分组在页面内的绝对偏移（rect.top + 测量时 scrollTop），滚动联动用 */
const groupOffsets = ref<number[]>([]);
const scrollTopRef = ref(0);
const SCROLL_OFFSET = 120;
/** 数据看板导航携带的目标分组索引 */
const initialGroup = ref(-1);

const stage2Stages = computed<StageInfo[]>(() => store.stage2Stages);

const unlockHint = computed(() => stage2Stages.value.find((s) => s.locked)?.unlockHint || '');

/**
 * 展示用任务副本：detail 为空时回退到 description（后端暂未写 detail），
 * T2.1.4 增加「查看二维码」操作按钮（参考阶段一 T1.3.8）。
 */
function getDisplayTask(task: SecondLevelTask): SecondLevelTask {
  const display = { ...task };
  if (!display.detail) {
    display.detail = display.description;
  }
  // advisor_entry（原 T2.1.4）：按钮文案「查看二维码」（#FE-29：按 actionType 判断，不再看 taskId）
  if (hasTaskActionType(display, 'advisor_entry')) {
    display.actionText = '查看二维码';
  }
  return display;
}

/** 分组按钮文案：一级任务 buttonText（后端返回） */
function getGroupButtonText(stage: StageInfo): string {
  return stage.firstLevelTasks?.[0]?.buttonText || '完成本组';
}

/** 一级任务组是否已全部完成（驱动 StageHeader 完成态单勾 + 绿色） */
function isGroupCompleted(stage: StageInfo): boolean {
  const tasks = (stage.firstLevelTasks?.[0]?.secondLevelTasks || []).filter(isTaskEnabled);
  return tasks.length > 0 && tasks.every(isTaskCompleted);
}

/** 「完成本组」toggle：未完成点击 → 完成本组；已完成点击（「全部取消」语义）→ 弹二次确认防误触（阶段一一致） */
function handleCompleteGroup(stage: StageInfo) {
  const wasComplete = isGroupCompleted(stage);
  if (wasComplete) {
    openGroupCancelModal(stage);
    return;
  }
  store.completeStage(stage.stageId);
  uni.showToast({ title: '已全部完成', icon: 'none', duration: 1500 });
}

/** 打开「取消全部完成」确认弹窗 */
function openGroupCancelModal(stage: StageInfo) {
  pendingCancelStage.value = stage;
  showGroupCancelModal.value = true;
}

/** 关闭确认弹窗（遮罩/关闭按钮/ESC/「再想想」），并清空待确认组 */
function closeGroupCancelModal() {
  showGroupCancelModal.value = false;
  pendingCancelStage.value = null;
}

/** 确认取消：执行 completeStage 并提示 */
function confirmCancelGroup() {
  const stage = pendingCancelStage.value;
  closeGroupCancelModal();
  if (stage) {
    store.completeStage(stage.stageId);
    uni.showToast({ title: '已取消完成', icon: 'none', duration: 1500 });
  }
}

/**
 * 任务卡勾选切换入口（F2-DC）：
 * 取消已完成任务且属商品发布（listing）组、数据专区已解锁 → 先弹确认（F2-CANCELTEXT；B11 文案如实
 * 描述实现：只把任务标记为未完成、不删除已上传的店铺数据；数据删除仅由数据看板「清除数据」显式调用
 * clearShopData 触发），确认后再执行取消。
 */
function handleTaskToggle(task: SecondLevelTask) {
  const isCancel = task.completionStatus === 'completed';
  if (isCancel && task.stageId === 'listing' && store.dataCenterUnlocked) {
    pendingListingCancelTask.value = task;
    showListingCancelTip.value = true;
    return;
  }
  store.toggleTask(task.taskId);
}

/** 关闭告知弹窗（遮罩/×/ESC/「暂不取消」）并清空待取消任务 */
function closeListingCancelTip() {
  showListingCancelTip.value = false;
  pendingListingCancelTask.value = null;
}

/** 确认继续取消：执行原 toggle（任务回到未完成，数据与解锁不受影响） */
function confirmListingCancel() {
  const task = pendingListingCancelTask.value;
  closeListingCancelTip();
  if (task) {
    store.toggleTask(task.taskId);
  }
}

/** 滚动到指定一级任务分组 */
function scrollToStage(idx: number) {
  activeIndex.value = idx;
  const stage = stage2Stages.value[idx];
  if (stage) {
    uni.pageScrollTo({
      selector: '#flt-' + stage.stageId,
      duration: 300,
    });
  }
}

/** 进入数据看板（数据分析专区看板页） */
function goBoard() {
  uni.navigateTo({ url: '/pages/data-center/index' });
}

/**
 * 任务操作按钮分发（#FE-29；入参为整个 task，与 TaskCard 新 emit 契约一致）
 * @description 唯一依据 = 后端 actionType（缺失/空/未知一律按 none，见 resolveTaskActionType）：
 *              advisor_entry → 企微二维码弹窗；其余（含 none 且无 actionUrl）保持原有兜底提示。
 *              模板上的 title_optimize / trademark_lookup / image_optimize / data_form / data_upload 由
 *              hasTaskActionType 直接表达，不经此处。
 */
function handleTaskAction(task: SecondLevelTask) {
  if (hasTaskActionType(task, 'advisor_entry')) {
    showQRModal.value = true;
    return;
  }
  uni.showToast({ title: '请按照引导完成任务', icon: 'none', duration: 2000 });
}

/** 测量各分组在视口内的位置（数据加载完成后执行） */
function measureGroups() {
  if (stage2Stages.value.length === 0) return;
  uni
    .createSelectorQuery()
    .selectAll('.stage-section')
    .boundingClientRect((rects) => {
      const list = Array.isArray(rects) ? rects : [rects];
      groupOffsets.value = list.map((r) =>
        r ? ((r as { top?: number }).top || 0) + scrollTopRef.value : 0,
      );
    })
    .exec();
}

/** 根据滚动位置联动左侧导航高亮（绝对偏移与 scrollTop+120 比较，参照阶段一实现） */
function updateActiveByScroll(scrollTop: number) {
  if (groupOffsets.value.length !== stage2Stages.value.length) {
    // 数据/布局尚未就绪时先补测，下一滚动事件再联动
    measureGroups();
    return;
  }
  let next = 0;
  groupOffsets.value.forEach((top, i) => {
    if (top <= scrollTop + SCROLL_OFFSET) next = i;
  });
  if (next !== activeIndex.value) {
    activeIndex.value = next;
  }
}

onPageScroll((e) => {
  scrollTopRef.value = e.scrollTop;
  updateActiveByScroll(e.scrollTop);
});

/** 返回任务中心 */
function goHome() {
  uni.reLaunch({ url: '/pages/index/index' });
}

onLoad((options) => {
  const group = Number((options as Record<string, string> | undefined)?.group);
  if (Number.isInteger(group) && group >= 0) {
    initialGroup.value = group;
  }
});

onMounted(async () => {
  trackPageView('stage2-center');
  // 用户名：唯一读取入口 @/utils/merchant（未登录返回空串 → 侧栏/顶栏用户区不渲染）
  userName.value = getMerchantNickname();
  await store.fetchStages();
  store.restoreProgress();
  nextTick(() => {
    setTimeout(() => {
      measureGroups();
      if (initialGroup.value >= 0) {
        scrollToStage(initialGroup.value);
      }
    }, 50);
    // 首次进入阶段二 → 引导链：经营类目（未保存则弹窗）→ 账号级 Tour（延迟等任务卡 DOM 就绪）
    setTimeout(() => {
      continueFirstEntryGuidance();
    }, 600);
  });
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

.stage-section {
  margin-bottom: $up-space-12;
}

.first-level-task-group {
  margin-top: $up-space-4;
}

/* 重新观看引导入口（轻量：caption 主色文字，hover/active 浅绿反馈） */
.tour-replay {
  display: flex;
  justify-content: flex-end;
  padding: $up-space-1 0 $up-space-3;
  transition: opacity $up-ease-fast;

  &:active {
    opacity: 0.7;
  }

  &__text {
    font-size: $up-font-size-caption;
    color: $u-primary;
    font-weight: 500;
  }
}

/* 数据看板入口 */
.board-entry {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $up-space-5;
  margin-bottom: $up-space-6;
  background-color: $u-white;
  border: 1rpx solid $u-border-color;
  border-radius: $up-radius-lg;

  &__info {
    flex: 1;
    min-width: 0;
  }

  &__title {
    display: block;
    font-size: $up-font-size-h3;
    font-weight: 600;
    color: $u-main-color;
    margin-bottom: $up-space-2;
  }

  &__desc {
    display: block;
    font-size: $up-font-size-caption;
    color: $u-tips-color;
    line-height: 1.5;
  }

  &__btn {
    flex-shrink: 0;
    margin-left: $up-space-4;
    padding: $up-space-2 $up-space-5;
    background-color: $u-primary;
    border-radius: $up-radius-sm;
  }

  &__btn-text {
    font-size: $up-font-size-body-sm;
    color: $u-white;
    font-weight: 500;
  }
}

.state-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  padding: $up-space-10;
  text-align: center;

  &__icon {
    width: 96rpx;
    height: 96rpx;
    border-radius: $up-radius-full;
    background-color: $u-primary-light;
    color: $u-primary;
    font-size: $up-font-size-h2;
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

/* 商品发布任务「查看图片示例」按钮：右侧常显，主色描边弱化按钮（§3.3 次按钮语言） */
.guide-entry {
  flex-shrink: 0;
  margin-left: $up-space-2;
  padding: $up-space-1 $up-space-3;
  background-color: $u-white;
  border: 1rpx solid $u-primary;
  border-radius: $up-radius-sm;
  transition: background-color $up-ease-normal, border-color $up-ease-normal;

  &:active {
    background-color: $u-primary-light;
  }

  &__text {
    font-size: $up-font-size-caption;
    color: $u-primary;
    font-weight: 500;
    white-space: nowrap;
  }
}

/* 窄视口（<600px）：入口文案允许换行 —— 「查看图片示例 / AI 优化主图」nowrap 单行宽 +
   任务卡右侧状态列会把任务卡行撑出视口（D1） */
@media (max-width: 600px) {
  .guide-entry__text {
    white-space: normal;
  }
}

/* T2.1.4 催审副标题 */
.advisor-entry {
  margin-top: $up-space-3;

  &__subtitle {
    display: block;
    font-size: $up-font-size-body-sm;
    font-weight: 600;
    color: $u-main-color;
    margin-bottom: $up-space-2;
  }

  &__desc {
    display: block;
    font-size: $up-font-size-caption;
    color: $u-content-color;
    line-height: 1.6;
  }
}

/* 企微二维码弹窗（参考阶段一 T1.3.8） */
.modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: $u-overlay;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.modal-box {
  background-color: $u-white;
  border-radius: $up-radius-lg;
  width: 90%;
  max-width: 600rpx;
  max-height: 80vh;
  overflow: hidden;

  &--large {
    max-width: 700rpx;
  }
}

.modal-header {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: $up-space-4 $up-space-5;
  border-bottom: 1rpx solid $u-border-color;
}

.modal-title {
  font-size: $up-font-size-h3;
  font-weight: 600;
  color: $u-main-color;
}

.modal-close {
  position: absolute;
  right: $up-space-4;
  top: 50%;
  transform: translateY(-50%);
  font-size: $up-font-size-h2;
  color: $u-tips-color;
  padding: $up-space-2;
}

.modal-body {
  padding: $up-space-5;
}

/* 一级任务组「取消全部完成」确认弹窗（复用阶段一实现；危险主按钮 §3.3 #EF4444） */
.group-cancel-modal {
  &__text {
    display: block;
    font-size: $up-font-size-body;
    color: $u-content-color;
    line-height: 1.6;
  }

  /* 组级取消告知条（F2-GROUPCANCEL：告知性，非警告；主色浅底） */
  &__notice {
    display: block;
    margin-top: $up-space-3;
    padding: $up-space-2 $up-space-3;
    background-color: $u-primary-light;
    border: 1rpx solid $u-tag-primary-border;
    border-radius: $up-radius-sm;
    font-size: $up-font-size-caption;
    color: $u-primary-dark;
    line-height: 1.5;
  }

  &__actions {
    display: flex;
    gap: $up-space-3;
    margin-top: $up-space-6;
  }

  &__btn {
    flex: 1;
    padding: $up-space-3 0;
    border-radius: $up-radius-sm;
    text-align: center;
    transition: transform $up-ease-fast, background-color $up-ease-fast;

    &:active {
      transform: scale(0.97);
    }

    /* 次按钮：白底描边（§3.3 次按钮风格） */
    &--secondary {
      background-color: $u-white;
      border: 1rpx solid $u-border-color;

      &:active {
        background-color: $u-bg-color;
      }
    }

    /* 危险主按钮：红色底白字（§3.3 危险主按钮 #EF4444 / #FFF / hover #DC2626） */
    &--danger {
      background-color: $u-error;
      border: 1rpx solid $u-error;

      &:active {
        background-color: $u-error-dark;
      }
    }

    /* 主色主按钮（F2-DC 取消告知「继续取消」用）：绿色底白字（§3.3 主按钮） */
    &--primary {
      background-color: $u-primary;
      border: 1rpx solid $u-primary;

      &:active {
        background-color: $u-primary-dark;
      }
    }
  }

  &__btn-text {
    font-size: $up-font-size-body-sm;
    font-weight: $up-font-weight-medium;

    .group-cancel-modal__btn--secondary & {
      color: $u-content-color;
    }

    .group-cancel-modal__btn--danger & {
      color: $u-white;
    }

    .group-cancel-modal__btn--primary & {
      color: $u-white;
    }
  }
}

.qr-code-area {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: $up-space-8 0;
}

.qr-code-image {
  width: 400rpx;
  height: 400rpx;
  border-radius: $up-radius-md;
}

.modal-text {
  font-size: $up-font-size-body-sm;
  color: $u-content-color;
  text-align: center;
}

.modal-hint {
  margin-top: $up-space-3;
  font-size: $up-font-size-caption;
  color: $u-tips-color;
  text-align: center;
}

</style>
