<template>
  <view class="page-layout">
    <!-- 移动端顶栏（≤600px 显示；PC 为 display:none，不参与布局与渲染）：
         左侧汉堡开合抽屉 + 中间当前阶段与进度摘要 + 右侧用户头像 -->
    <view class="sidebar__topbar">
      <view class="sidebar__topbar-toggle" @tap="toggleDrawer">
        <view class="sidebar__topbar-bar" />
        <view class="sidebar__topbar-bar" />
        <view class="sidebar__topbar-bar" />
      </view>
      <view class="sidebar__topbar-info">
        <text class="sidebar__topbar-title">入驻准备</text>
        <text class="sidebar__topbar-progress">阶段进度 {{ taskStore.progress.completed }}/{{ taskStore.progress.total }}</text>
      </view>
      <view v-if="userName" class="sidebar__topbar-avatar">{{ userName.charAt(0) }}</view>
    </view>

    <!-- 抽屉遮罩（≤600px 且抽屉展开时渲染；点击收起，PC 不渲染） -->
    <view v-if="drawerOpen" class="sidebar__mask" @tap="closeDrawer" />

    <!-- 左侧导航栏（>600px 为常驻侧栏；≤600px 转为抽屉，DOM 完全复用） -->
    <view class="sidebar" :class="{ 'sidebar--open': drawerOpen }">
      <!-- Logo -->
      <view class="sidebar__logo">
        <view class="sidebar__icon">P</view>
        <text class="sidebar__brand">商家任务中心</text>
      </view>

      <!-- 阶段标识 -->
      <view class="sidebar__stage">
        <view class="sidebar__stage-num">1</view>
        <text class="sidebar__stage-title">入驻准备</text>
      </view>

      <!-- 阶段进度 -->
      <view class="sidebar__progress">
        <view class="sidebar__progress-row">
          <text class="sidebar__progress-label">阶段进度</text>
          <text class="sidebar__progress-value">{{ taskStore.progress.completed }}/{{ taskStore.progress.total }}</text>
        </view>
        <view
          ref="sidebarProgressBarRef"
          class="sidebar__progress-bar"
          :class="{ 'sidebar__progress-bar--pulse': progressPulse }"
        >
          <view ref="sidebarFillRef" class="sidebar__progress-fill" />
        </view>
        <view
          class="sidebar__switch"
          :class="{ 'sidebar__switch--active': taskStore.stage2Unlocked }"
          @tap="handleStage2Entry"
        >
          <text class="sidebar__switch-text">{{ taskStore.stage2Unlocked ? '切换阶段 →' : '切换阶段' }}</text>
        </view>
      </view>

      <!-- 一级任务导航 -->
      <view class="sidebar__nav">
        <view
          v-for="(group, idx) in taskGroups"
          :key="group.taskId"
          class="sidebar__nav-item"
          :class="{ active: activeTab === idx }"
          @tap="scrollToTask(idx)"
        >
          <view class="sidebar__nav-num" :class="{ active: activeTab === idx }">{{ idx + 1 }}</view>
          <view class="sidebar__nav-info">
            <text class="sidebar__nav-title">{{ group.title }}</text>
            <text
              :ref="(el) => setNavCountEl(el, idx)"
              class="sidebar__nav-count"
              :class="{ 'sidebar__nav-count--pulse': pulseGroupIdx === idx }"
            >{{ groupCompleted(group) }}/{{ groupTotal(group) }}</text>
          </view>
        </view>
      </view>

      <!-- 用户信息 + 退出登录（同一行：登录态在左、退出登录右对齐；退出入口按本地登录态显隐，不依赖 nickname） -->
      <view class="sidebar__user" v-if="userName || isLoggedIn">
        <view class="sidebar__user-main">
          <view v-if="userName" class="sidebar__avatar">{{ userName.charAt(0) }}</view>
          <text v-if="userName" class="sidebar__username" :title="userName">{{ userName }}</text>
        </view>
        <text
          v-if="isLoggedIn"
          class="sidebar__logout"
          @tap="openLogoutModal"
        >{{ LOGOUT_ENTRY_TEXT }}</text>
      </view>

      <!-- 重新观看引导（仅开发环境显示：v-if="IS_DEV"，生产 build 不渲染该调试入口） -->
      <view v-if="IS_DEV" class="sidebar__tour-entry" @tap="restartTour">
        <text class="sidebar__tour-entry-text">重新观看引导</text>
      </view>
    </view>

    <!-- 右侧内容区 -->
    <view class="main-content">
      <!-- 进度提示横幅（恢复失败 / 完成进度未落库未同步时显示，可点击重试） -->
      <view v-if="progressBannerText" class="restore-fail-banner" @tap="retryRestoreProgress">
        <text class="restore-fail-banner__text">{{ progressBannerText }}</text>
        <text class="restore-fail-banner__refresh">↻ 点击重试</text>
      </view>
      <view
        v-for="(group, idx) in taskGroups"
        :key="group.taskId"
        :ref="(el) => collectGroupEl(el, group.taskId)"
        :id="'flt-' + group.taskId"
        class="stage-section first-level-task-group"
      >
        <StageHeader
          :stage-num="idx + 1"
          :title="group.title"
          :button-text="group.buttonText || '开始'"
          :completed="isGroupCompleted(group)"
          @complete="handleGroupComplete(group)"
        />

        <template v-for="(task, tIdx) in group.secondLevelTasks" :key="task.taskId">
          <TaskCard
            :ref="(el) => collectTaskCardEl(el, task.taskId)"
            :task="task"
            :show-category-selector="task.taskId === 'T1.1.2'"
            :show-fee-selector="task.taskId === 'T1.1.3'"
            :tick-delay="tIdx * 40"
            :anchor="task.taskId === 'T1.1.3' ? 'fee' : ''"
            @toggle="taskStore.toggleTask(task.taskId)"
            @action="handleTaskAction"
          />
        </template>

        <!-- 支线任务（CardMotion 统一 hover/按压微动效） -->
        <CardMotion v-for="branch in group.branches" :key="branch.id">
          <BranchTask
            :title="branch.title"
            :tasks="branch.tasks"
            @toggle-check="taskStore.toggleBranchTask"
          />
        </CardMotion>
      </view>

      <!-- 页脚：备案信息（工信部要求） -->
      <IcpFooter />
    </view>

    <!-- 保证金标准弹窗 -->
    <view v-if="showFeeModal" class="modal-mask" @tap="showFeeModal = false">
      <view class="modal-box" @tap.stop>
        <view class="modal-header">
          <text class="modal-title">保证金标准</text>
          <text class="modal-close" @tap="showFeeModal = false">×</text>
        </view>
        <view class="modal-body">
          <view class="modal-table">
            <view class="modal-table-row modal-table-header">
              <text class="modal-table-cell">GMV档位</text>
              <text class="modal-table-cell">说明</text>
            </view>
            <view class="modal-table-row">
              <text class="modal-table-cell">GMV ＜ 5万</text>
              <text class="modal-table-cell">入驻初期适用</text>
            </view>
            <view class="modal-table-row">
              <text class="modal-table-cell">5万 ≤ GMV ＜ 10万</text>
              <text class="modal-table-cell">第二阶梯</text>
            </view>
            <view class="modal-table-row">
              <text class="modal-table-cell">10万 ≤ GMV ＜ 30万</text>
              <text class="modal-table-cell">第三阶梯</text>
            </view>
            <view class="modal-table-row">
              <text class="modal-table-cell">GMV ≥ 30万</text>
              <text class="modal-table-cell">头部商家最高档</text>
            </view>
          </view>
          <view class="modal-note">保证金按档位就高不就低，GMV下降时不立即降档，平台有权要求补缴。</view>
        </view>
      </view>
    </view>

    <!-- 商家顾问二维码弹窗 -->
    <view v-if="showQRModal" class="modal-mask" @tap="showQRModal = false">
      <view class="modal-box modal-box--large" @tap.stop>
        <view class="modal-header">
          <text class="modal-title">添加商家顾问</text>
          <text class="modal-close" @tap="showQRModal = false">×</text>
        </view>
        <view class="modal-body" style="text-align: center;">
          <!-- 二维码区域 -->
          <view class="qr-code-area">
            <image 
              :src="qrCodeUrl"
              mode="aspectFit" 
              class="qr-code-image"
            />
          </view>
          <view class="modal-text">添加话术：您好，我是XX店铺负责人</view>
          <view class="modal-hint">添加商家顾问可获得一对一入驻指导</view>
        </view>
      </view>
    </view>

    <!-- 驳回原因弹窗 -->
    <view v-if="showRejectModal" class="modal-mask" @tap="showRejectModal = false">
      <view class="modal-box" @tap.stop>
        <view class="modal-header">
          <text class="modal-title">常见驳回原因</text>
          <text class="modal-close" @tap="showRejectModal = false">×</text>
        </view>
        <view class="modal-body">
          <view class="modal-table">
            <view class="modal-table-row modal-table-header">
              <text class="modal-table-cell">驳回原因</text>
              <text class="modal-table-cell">处理方式</text>
            </view>
            <view class="modal-table-row">
              <text class="modal-table-cell">联系人信息无效</text>
              <text class="modal-table-cell">重新填写有效联系方式</text>
            </view>
            <view class="modal-table-row">
              <text class="modal-table-cell">营业执照不清晰</text>
              <text class="modal-table-cell">重新上传高清原件照片</text>
            </view>
            <view class="modal-table-row">
              <text class="modal-table-cell">资质不全</text>
              <text class="modal-table-cell">补充缺失资质材料</text>
            </view>
            <view class="modal-table-row">
              <text class="modal-table-cell">信息不一致</text>
              <text class="modal-table-cell">确保所有材料信息一致</text>
            </view>
            <view class="modal-table-row">
              <text class="modal-table-cell">店铺名称违规</text>
              <text class="modal-table-cell">修改店铺名称后重新提交</text>
            </view>
          </view>
        </view>
      </view>
    </view>

    <!-- 阶段一完成弹窗 -->
    <view v-if="showStage2Modal" class="modal-mask" @tap="showStage2Modal = false">
      <view ref="stage2ModalBoxRef" class="modal-box stage2-done-modal" @tap.stop>
        <view class="stage2-done-modal__icon">✓</view>
        <view class="stage2-done-modal__title">恭喜完成入驻</view>
        <view class="stage2-done-modal__desc">请进入开店搭建任务，引导完成开店冷启动</view>
        <view class="stage2-done-modal__actions">
          <view class="stage2-done-modal__btn stage2-done-modal__btn--secondary" @tap="showStage2Modal = false">
            <text class="stage2-done-modal__btn-text">稍后再说</text>
          </view>
          <view class="stage2-done-modal__btn stage2-done-modal__btn--primary" @tap="goStage2FromModal">
            <text class="stage2-done-modal__btn-text">进入阶段二</text>
          </view>
        </view>
      </view>
    </view>
    <!-- 取消全部完成确认弹窗（自定义弹窗，符合设计规范：遮罩/圆角/阴影/按钮全 Token） -->
    <view v-if="showGroupCancelModal" class="modal-mask" @tap="closeGroupCancelModal">
      <view class="modal-box group-cancel-modal" @tap.stop>
        <view class="modal-header">
          <text class="modal-title">取消完成</text>
          <text class="modal-close" @tap="closeGroupCancelModal">×</text>
        </view>
        <view class="modal-body">
          <text class="group-cancel-modal__text">
            确定取消「{{ pendingCancelGroup?.title || '' }}」全部任务的完成状态吗？取消后需重新完成该组任务。
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

    <!-- 退出登录二次确认（复用共享 Modal 组件；确认后清登录态并回登录页） -->
    <Modal
      :visible="showLogoutModal"
      :title="LOGOUT_CONFIRM_TITLE"
      @update:visible="onLogoutModalVisible"
    >
      <view class="logout-modal">
        <text class="logout-modal__text">{{ LOGOUT_CONFIRM_MESSAGE }}</text>
        <view class="logout-modal__actions">
          <view class="logout-modal__btn logout-modal__btn--secondary" @tap="closeLogoutModal">
            <text class="logout-modal__btn-text">{{ LOGOUT_CONFIRM_CANCEL_TEXT }}</text>
          </view>
          <view class="logout-modal__btn logout-modal__btn--primary" @tap="confirmLogout">
            <text class="logout-modal__btn-text">{{ LOGOUT_CONFIRM_OK_TEXT }}</text>
          </view>
        </view>
      </view>
    </Modal>

    <!-- 阶段一完成升华汇聚动画层 -->
    <CompletionCelebration ref="burstRef" />

    <!-- 阶段一新商家引导 Tour（R60：spotlight 高亮 + tooltip，首次进入显示，可跳过） -->
    <ProductTour
  v-model="tourActive"
  :steps="TOUR_STEPS"
  @complete="handleTourComplete"
  @skip="handleTourComplete"
/>

    <!-- 右下角反馈浮窗（fixed；点击打开意见反馈弹窗） -->
    <view
      class="feedback-fab"
      hover-class="feedback-fab--hover"
      @tap="openFeedback"
    >
      <text class="feedback-fab__icon">✉︎</text>
      <text class="feedback-fab__text">意见反馈</text>
    </view>

    <!-- 意见反馈弹窗（复用 Modal 组件；提交调 POST /api/feedback） -->
    <Modal
      :visible="showFeedbackModal"
      title="意见反馈"
      @update:visible="onFeedbackModalVisible"
    >
      <view class="feedback-form">
        <!-- 反馈内容（必填） -->
        <view class="feedback-form__field">
          <text class="feedback-form__label">反馈内容 *</text>
          <textarea
            v-model="feedbackContent"
            class="feedback-form__textarea"
            placeholder="请描述您遇到的问题或建议…"
            placeholder-class="feedback-form__placeholder"
            :maxlength="500"
          />
          <text class="feedback-form__count">{{ feedbackContent.length }}/500</text>
        </view>

        <!-- 分类（可选） -->
        <view class="feedback-form__field">
          <text class="feedback-form__label">反馈分类（可选）</text>
          <view class="feedback-form__cats">
            <view
              v-for="cat in FEEDBACK_CATEGORIES"
              :key="cat"
              class="feedback-form__cat"
              :class="{ 'feedback-form__cat--active': feedbackCategory === cat }"
              @tap="feedbackCategory = feedbackCategory === cat ? '' : cat"
            >
              <text class="feedback-form__cat-text">{{ cat }}</text>
            </view>
          </view>
        </view>

        <!-- 客服入口（占位：M5 智能客服接入中） -->
        <view class="feedback-form__service" @tap="openSupport">
          <text class="feedback-form__service-icon">☎︎</text>
          <view class="feedback-form__service-info">
            <text class="feedback-form__service-title">在线客服</text>
            <text class="feedback-form__service-desc">AI 智能客服接入中，敬请期待</text>
          </view>
          <text class="feedback-form__service-arrow">›</text>
        </view>

        <!-- 提交 -->
        <view class="feedback-form__submit">
          <view
            class="feedback-form__btn feedback-form__btn--primary"
            :class="{ 'feedback-form__btn--disabled': submitting }"
            @tap="handleSubmitFeedback"
          >
            <text class="feedback-form__btn-text">{{ submitting ? '提交中…' : '提交反馈' }}</text>
          </view>
        </view>
      </view>
    </Modal>
  </view>
</template>

<script setup lang="ts">
import { trackPageView, trackEvent, EventType } from '@/utils/track';
import Modal from '@/components/Modal/index.vue';
import { submitFeedback } from '@/api/feedback';
/**
 * 任务中心首页
 * @description 左侧导航 + 右侧内容的布局，展示入驻准备阶段的5个一级任务列表
 */
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue';
import { onPageScroll } from '@dcloudio/uni-app';
import { getGsap } from '@/utils/gsap';
const gsap = getGsap();
import { useTaskStore } from '@/store/modules/task';
import type { FirstLevelTask } from '@/types/task';
import { isTaskEnabled, isTaskCompleted } from '@/utils/stage2';
import { getMerchantNickname } from '@/utils/merchant';
import { logout } from '@/utils/auth';
import {
  LOGOUT_ENTRY_TEXT,
  LOGOUT_CONFIRM_TITLE,
  LOGOUT_CONFIRM_MESSAGE,
  LOGOUT_CONFIRM_CANCEL_TEXT,
  LOGOUT_CONFIRM_OK_TEXT,
} from '@/constants/auth';
import { getAdvisorQrCodeUrl } from '@/api/stage2';
import TaskCard from '@/components/TaskCard/index.vue';
import StageHeader from '@/components/StageHeader/index.vue';
import BranchTask from '@/components-local/task-center/BranchTask.vue';
import IcpFooter from '@/components/IcpFooter/index.vue';
import CardMotion from '@/components/CardMotion/index.vue';
import CompletionCelebration from '@/components-local/task-center/CompletionCelebration.vue';
import { useEscapeClose } from '@/composables/useEscapeClose';
import ProductTour, { type TourStep } from '@/components/ProductTour/index.vue';
import request from '@/api/request';


/** 开发环境标识（vite 注入）：仅开发环境显示「重新观看引导」调试入口，生产不渲染 */
const IS_DEV = import.meta.env.DEV;

const taskStore = useTaskStore();
const activeTab = ref(0);
const userName = ref('');

/* ---------- 移动端壳层（≤600px，T-3 方案）：侧栏转抽屉 + 固定顶栏 ---------- */
/** 移动端主断点：与 #F-5/T-1 已确立的 600px 主断点一致（抽屉/顶栏仅在 ≤600px 生效） */
const MOBILE_BREAKPOINT = 600;
/** 移动端抽屉展开状态（≤600px 才有顶栏/遮罩可操作；PC 恒为 false） */
const drawerOpen = ref(false);

/** 当前视口是否为移动端（跨端取 uni 系统信息，不依赖 window） */
function isMobileViewport(): boolean {
  return uni.getSystemInfoSync().windowWidth <= MOBILE_BREAKPOINT;
}

/** 汉堡按钮开合抽屉 */
function toggleDrawer(): void {
  drawerOpen.value = !drawerOpen.value;
}

/** 收起抽屉（遮罩点击 / 选中导航项 / 视口跨回 PC 宽度） */
function closeDrawer(): void {
  drawerOpen.value = false;
}

/** 抽屉展开时禁止背景滚动：沿用项目既有做法（document.body.style.overflow，仅 H5 存在 body） */
function setBodyScrollLock(locked: boolean): void {
  if (typeof document === 'undefined' || !document.body) return;
  document.body.style.overflow = locked ? 'hidden' : '';
}

watch(drawerOpen, (open) => setBodyScrollLock(open));

/** 视口跨回 PC 宽度时强制收起抽屉并解除滚动锁（保证 PC 零残留） */
function handleWindowResize(): void {
  if (!isMobileViewport()) closeDrawer();
}

/** 侧栏进度填充/轨道与一级任务数字元素（GSAP 目标） */
const sidebarFillRef = ref<HTMLElement | null>(null);
const sidebarProgressBarRef = ref<HTMLElement | null>(null);
let sidebarFillEl: HTMLElement | null = null;
let sidebarProgressBarEl: HTMLElement | null = null;
const navCountEls: Array<HTMLElement | null> = [];

function resolveEl(refValue: any): HTMLElement | null {
  return refValue?.$el ?? (refValue as HTMLElement | null);
}

function setNavCountEl(el: any, idx: number) {
  navCountEls[idx] = resolveEl(el);
}

/** 任务卡根元素收集（升华汇聚动画目标，按 taskId 映射避免重复） */
const taskCardElMap = new Map<string, HTMLElement>();
function collectTaskCardEl(el: any, taskId: string) {
  const resolved = resolveEl(el);
  if (resolved) {
    taskCardElMap.set(taskId, resolved);
  } else {
    taskCardElMap.delete(taskId);
  }
}

/** 一级任务组容器收集（升华汇聚时整组内容——标题/支线——统一隐藏与恢复） */
const taskGroupElMap = new Map<string, HTMLElement>();
function collectGroupEl(el: any, taskId: string) {
  const resolved = resolveEl(el);
  if (resolved) {
    taskGroupElMap.set(taskId, resolved);
  } else {
    taskGroupElMap.delete(taskId);
  }
}

interface BurstInstance {
  /** 组件内为 async：resolve 表示时间线已建立（动画确实开始），reject 表示启动失败 */
  play(
    cards: Array<HTMLElement | null>,
    groups: Array<{ el: HTMLElement | null; cardCount: number }>,
    onDone: () => void,
  ): Promise<void>
  stop(): void
}

/** 升华汇聚动画组件实例 */
const burstRef = ref<BurstInstance | null>(null);
/** 完成弹窗 modal-box（入场动画目标） */
const stage2ModalBoxRef = ref<HTMLElement | null>(null);
// 弹窗状态
const showFeeModal = ref(false)
const showQRModal = ref(false)
const showRejectModal = ref(false)
const showStage2Modal = ref(false)
/** 取消全部完成确认弹窗状态与待确认组 */
const showGroupCancelModal = ref(false)
const pendingCancelGroup = ref<FirstLevelTask | null>(null)
/** 是否已登录（本地有 token）：控制「退出登录」入口显隐，不依赖 nickname */
const isLoggedIn = ref(false)

/** 退出登录二次确认弹窗 */
const showLogoutModal = ref(false)

/** 商家顾问企微二维码地址：由 api 封装按构建期 BASE_URL 生成，禁止硬编码 host（真源 §8.1 同类规则） */
const qrCodeUrl = ref(getAdvisorQrCodeUrl())

/* ---------- 意见反馈浮窗（右下角，POST /api/feedback + 客服占位入口） ---------- */
/** 反馈弹窗可见 */
const showFeedbackModal = ref(false);
/** 反馈内容（必填） */
const feedbackContent = ref('');
/** 反馈分类（可选，单选可再点取消） */
const feedbackCategory = ref('');
/** 提交中状态（防重复提交） */
const submitting = ref(false);
/** 反馈分类候选项 */
const FEEDBACK_CATEGORIES = ['功能建议', '问题反馈', '其他'] as const;

// 所有可关闭弹窗支持 ESC 键关闭（仅弹窗可见时生效）
useEscapeClose(() => showFeeModal.value, () => { showFeeModal.value = false; });
useEscapeClose(() => showQRModal.value, () => { showQRModal.value = false; });
useEscapeClose(() => showRejectModal.value, () => { showRejectModal.value = false; });
useEscapeClose(() => showStage2Modal.value, () => { showStage2Modal.value = false; });
useEscapeClose(() => showGroupCancelModal.value, () => { showGroupCancelModal.value = false; });

/** 完成庆祝「已展示」标记 key（跨进入持久化：首次展示后刷新/再次登录不再打扰；修复 #F-ANIM1 恢复窗口拦截导致的丢失） */
const CELEBRATION_SEEN_KEY = 'stage1_completion_celebrated';
/** 本次会话是否已弹过完成引导（解锁持久化后再次登录不重复弹） */
let stage2ModalShown = false;
/** 页面加载/恢复进度期间为 true，此阶段不弹完成引导 */
let restoring = true;

/**
 * 进度提示横幅文案（空串不渲染）
 * @description 优先「进度恢复失败」；其次按方向如实提示未落库项：
 *              完成方向（本地已完成、后端未确认）与取消方向（本地已取消、后端仍为完成态）分别计数。
 */
const progressBannerText = computed(() => {
  if (taskStore.progressRestoreFailed) return '进度加载失败，请刷新重试';
  const completedCount = taskStore.unsyncedCompletedTaskIds.length;
  const pendingCount = taskStore.unsyncedPendingTaskIds.length;
  if (completedCount > 0 && pendingCount > 0) {
    return `完成 ${completedCount} 项、取消 ${pendingCount} 项未同步，点击重试`;
  }
  if (completedCount > 0) return `${completedCount} 项完成进度未同步，点击重试`;
  if (pendingCount > 0) return `${pendingCount} 项取消操作未同步，点击重试`;
  return '';
});

/** 一级任务分组（按后端顺序展平） */
const taskGroups = computed<FirstLevelTask[]>(() => {
  const groups: FirstLevelTask[] = [];
  for (const stage of taskStore.stage1Stages) {
    groups.push(...(stage.firstLevelTasks || []));
  }
  return groups;
});

/** 一级任务启用任务总数 */
function groupTotal(group: FirstLevelTask): number {
  return (group.secondLevelTasks || []).filter(isTaskEnabled).length;
}

/** 一级任务已完成数 */
function groupCompleted(group: FirstLevelTask): number {
  return (group.secondLevelTasks || []).filter((t) => isTaskEnabled(t) && isTaskCompleted(t)).length;
}

/** 一级任务组是否已全部完成（驱动按钮完成态对勾） */
function isGroupCompleted(group: FirstLevelTask): boolean {
  return groupTotal(group) > 0 && groupCompleted(group) === groupTotal(group);
}

/**
 * 完成按钮点击：未完成→整组置为完成；已完成→弹自定义确认弹窗后才取消
 * @description completeGroup 为 toggle 语义，完成态按钮再次点击会直接取消整组，
 *              误触会导致 stage1Complete 回退并同步回滚后端解锁，刷新也无法恢复。
 *              故完成态点击改为项目自定义确认弹窗（非 uni.showModal 系统样式），防误触；正常完成不受影响。
 */
function handleGroupComplete(group: FirstLevelTask) {
  const wasComplete = isGroupCompleted(group);
  if (wasComplete) {
    openGroupCancelModal(group);
    return;
  }
  taskStore.completeGroup(group);
  uni.showToast({ title: '已全部完成', icon: 'none', duration: 1500 });
}

/** 打开「取消全部完成」确认弹窗 */
function openGroupCancelModal(group: FirstLevelTask) {
  pendingCancelGroup.value = group;
  showGroupCancelModal.value = true;
}

/** 关闭确认弹窗（遮罩/关闭按钮/ESC/「再想想」），并清空待确认组 */
function closeGroupCancelModal() {
  showGroupCancelModal.value = false;
  pendingCancelGroup.value = null;
}

/** 确认取消：执行 completeGroup 并提示 */
function confirmCancelGroup() {
  const group = pendingCancelGroup.value;
  closeGroupCancelModal();
  if (group) {
    taskStore.completeGroup(group);
    uni.showToast({ title: '已取消完成', icon: 'none', duration: 1500 });
  }
}

/* ---------- 阶段一 Product Tour（新商家首次进入引导，R60） ---------- */
/**
 * 账号级新手引导（后端事实源 GET/POST /api/tour/seen，全账号仅一次）
 * @description 触发前 GET /api/tour/seen：data.seen === false 才弹；
 *              完成/跳过 POST /api/tour/seen 标记已看；「重新观看引导」POST /api/tour/seen/reset 后重触发。
 */
const tourActive = ref(false);

/** 阶段一 Tour 步骤（6 步：欢迎/展开/资费/完成/取消完成/切换阶段） */
const TOUR_STEPS: TourStep[] = [
  {
    title: '欢迎来到任务中心',
    text: '这里是入驻准备阶段：完成 5 组任务（模式选择、资质准备、申请入驻等）即可解锁开店搭建。',
    focus: false,
  },
  {
    title: '点击任务卡展开',
    text: '点击任务卡片可展开详情，查看任务说明、类目要求与资费信息。',
    target: '.task-card',
  },
  {
    title: '查询类目资费',
    text: '在「了解类目资费」任务卡中，可查询各经营类目的保证金档位与技术服务费率。',
    target: '[data-tour-anchor="fee"]',
  },
  {
    title: '完成任务',
    text: '勾选任务卡左侧的圆点即可标记该任务完成，进度会实时同步。',
    target: '.task-card__checkbox',
  },
  {
    title: '取消完成任务',
    text: '组内任务全部完成后，组头按钮变为对勾；再次点击会弹确认框，确认后才取消整组完成。',
    target: '.stage-header__btn',
    placement: 'left',
  },
  {
    title: '切换阶段',
    text: '完成阶段一全部任务后，点击此处切换进入阶段二「开店搭建」。',
    target: '.sidebar__switch',
    placement: 'right',
  },
];

/** 首次进入阶段一 → 查询账号级已看状态，未看过（seen===false）才启动 Tour */
async function maybeStartTour() {
  try {
    const res = await request.get<{ seen: boolean }>('/api/tour/seen');
    if (res.data && res.data.seen === false) {
      tourActive.value = true;
    }
  } catch (err) {
    // 后端接口未就绪/失败时静默：不打扰首次进入流程（可在控制台查看）
    console.error('查询新手引导状态失败:', err);
  }
}

/** 完成/跳过 → POST 标记账号已看（替代组件内 localStorage markSeen） */
function handleTourComplete() {
  request.post('/api/tour/seen', {}).catch(() => {});
}

/** 重新观看引导（仅开发调试）：POST 重置账号已看标记后强制重新触发 Tour */
async function restartTour() {
  try {
    await request.post('/api/tour/seen/reset', {});
  } catch {
    /* ignore */
  }
  tourActive.value = true;
}

/**
 * 进度提示重试：先重新恢复进度（重算未同步状态、补发未落库的完成项），
 * 再补发未落库的取消项（用户主动点击即明确表达取消意图）；成功即清除对应未同步标记。
 */
async function retryRestoreProgress() {
  await taskStore.restoreProgress();
  taskStore.retryUnsyncedPending();
}

// 打开弹窗
function openFeeModal() { showFeeModal.value = true }
function openQRModal() { showQRModal.value = true }
function openRejectModal() { showRejectModal.value = true }

/* ---------- 意见反馈 ---------- */
/** 浮窗打开 → 弹反馈弹窗并埋点（action_click + element=feedback） */
function openFeedback() {
  showFeedbackModal.value = true;
  trackEvent(EventType.ACTION_CLICK, { element: 'feedback' });
}

/** Modal visible 双向同步（关闭按钮/遮罩/ESC） */
function onFeedbackModalVisible(visible: boolean) {
  showFeedbackModal.value = visible;
}

/** 提交反馈：校验 content 非空 → POST /api/feedback（失败由 request 封装提示，不阻塞页面） */
async function handleSubmitFeedback() {
  const content = feedbackContent.value.trim();
  if (!content) {
    uni.showToast({ title: '请填写反馈内容', icon: 'none' });
    return;
  }
  if (submitting.value) return;
  submitting.value = true;
  try {
    await submitFeedback({
      content,
      category: feedbackCategory.value || undefined,
    });
    uni.showToast({ title: '反馈已提交，感谢您的建议', icon: 'none' });
    trackEvent(EventType.ACTION_CLICK, {
      element: 'feedback',
      meta: { action: 'submit', category: feedbackCategory.value || '' },
    });
    showFeedbackModal.value = false;
    feedbackContent.value = '';
    feedbackCategory.value = '';
  } catch (err) {
    // request 封装已 toast 失败原因（网络异常/后端 message），此处静默
    console.warn('提交反馈失败:', err);
  } finally {
    submitting.value = false;
  }
}

/** 客服入口占位：M5 智能客服接入中，前端提示（后端 /api/support/* 接入后替换为跳转/拉起） */
function openSupport() {
  uni.showToast({ title: '客服接入中，敬请期待', icon: 'none' });
}

// 处理任务操作按钮点击
function handleTaskAction(taskId) {
  if (taskId === 'T1.3.7') {
    showQRModal.value = true
  }
}

/**
 * 阶段二入口：未解锁（任务未完成且后端无解锁标记）则拦截提示，解锁后进入独立阶段二页面
 * @description 未解锁时提示剩余未完成任务数（进度统计仅含阶段一启用任务），
 *              让用户明确还差哪些任务，避免误以为全部完成后仍被拦截。
 */
function handleStage2Entry() {
  if (!taskStore.stage2Unlocked) {
    const { total, completed } = taskStore.progress;
    const remaining = total - completed;
    uni.showToast({
      title: remaining > 0
        ? `还差 ${remaining} 个任务未完成，完成后可进入阶段二`
        : '完成阶段一全部任务后可开启阶段二',
      icon: 'none',
      duration: 2000,
    });
    return;
  }
  uni.navigateTo({ url: '/pages/stage2/index' });
}

/** 完成弹窗「进入阶段二」 */
/** 打开退出登录确认弹窗 */
function openLogoutModal() {
  showLogoutModal.value = true
}

/** 关闭退出登录确认弹窗（二次确认的「取消」/遮罩/ESC/关闭按钮） */
function closeLogoutModal() {
  showLogoutModal.value = false
}

/** Modal visible 双向同步（关闭按钮/遮罩/ESC） */
function onLogoutModalVisible(visible: boolean) {
  showLogoutModal.value = visible
}

/** 确认退出：清登录态并回登录页（复用 utils/auth 的登出实现，不另写一套清理逻辑） */
function confirmLogout() {
  showLogoutModal.value = false
  logout()
}

function goStage2FromModal() {
  showStage2Modal.value = false;
  uni.navigateTo({ url: '/pages/stage2/index' });
}

/** 滚动到指定一级任务（用缓存偏移，避免 taskId 含点号导致 id 选择器不命中） */
function scrollToTask(idx: number) {
  // 移动端：选中导航项后自动收起抽屉，避免遮罩挡住内容
  closeDrawer();
  activeTab.value = idx;
  if (taskTops.value.length === taskGroups.value.length && taskTops.value[idx] !== undefined) {
    uni.pageScrollTo({ scrollTop: Math.max(0, taskTops.value[idx] - 120), duration: 300 });
    return;
  }
  // 位置未就绪：先刷新再滚动
  refreshTaskTops(() => {
    if (taskTops.value[idx] !== undefined) {
      uni.pageScrollTo({ scrollTop: Math.max(0, taskTops.value[idx] - 120), duration: 300 });
    }
  });
}

/** 一级任务区块位置缓存（归一化为页面顶部偏移） */
const taskTops = ref<number[]>([]);
const scrollTop = ref(0);

function refreshTaskTops(onReady?: () => void) {
  uni.createSelectorQuery()
    .selectAll('.first-level-task-group')
    .boundingClientRect((rects) => {
      const list = (rects || []) as Array<{ top: number }>;
      taskTops.value = list.map((r) => (r ? r.top + scrollTop.value : 0));
      onReady?.();
    })
    .exec();
}

/** 滚动时联动左侧导航高亮 */
onPageScroll((e) => {
  scrollTop.value = e.scrollTop;
  if (taskTops.value.length !== taskGroups.value.length) {
    refreshTaskTops();
  }
  let next = 0;
  taskTops.value.forEach((top, i) => {
    if (top <= e.scrollTop + 120) next = i;
  });
  if (next !== activeTab.value) activeTab.value = next;
});

onMounted(async () => {
  if (typeof uni.onWindowResize === 'function') uni.onWindowResize(handleWindowResize);
  trackPageView('task-center');
  // 用户名：唯一读取入口 @/utils/merchant（未登录返回空串 → 侧栏/顶栏用户区不渲染）
  userName.value = getMerchantNickname();
  // 登录态：决定「退出登录」入口是否显示（与 nickname 是否存在解耦）
  isLoggedIn.value = !!uni.getStorageSync('token');
  restoring = true;
  await taskStore.fetchStages();
  await taskStore.restoreProgress();
  restoring = false;
  await nextTick();
  refreshTaskTops();
  sidebarFillEl = resolveEl(sidebarFillRef.value);
  sidebarProgressBarEl = resolveEl(sidebarProgressBarRef.value);
  if (sidebarFillEl) {
    gsap.set(sidebarFillEl, { scaleX: taskStore.progress.percent / 100, transformOrigin: 'left' });
  }
  // #F-ANIM1：恢复窗口内解锁变化被 restoring 拦截后补触发一次完成庆祝（首次识别到解锁时）
  // 触发过庆祝（已完成商家）则本轮跳过新商家引导，避免遮罩层叠加
  const celebrated = maybePlayCelebrationOnRestore();
  if (!celebrated) {
    // R60：新商家首次进入显示引导（已完成/跳过标记后不再打扰）
    maybeStartTour();
  }
});

// 任务进度变化后刷新区块位置（完成态/展开会影响高度）
watch(() => taskStore.progress, () => {
  nextTick(() => refreshTaskTops());
});

/** 写入跨进入的「已看」标记（存储不可用不影响本次会话防重与动画展示） */
function markCelebrationSeen() {
  try {
    uni.setStorageSync(CELEBRATION_SEEN_KEY, '1');
  } catch {
    /* ignore */
  }
}

/**
 * 完成庆祝展示一次
 * @description stage2ModalShown 负责会话内防重；CELEBRATION_SEEN_KEY 由 playCompletionCelebration
 *              在动画确实开始（或弹窗兜底展示）后写入，避免动画启动失败时误标「已看」。
 */
function playCelebrationOnce() {
  stage2ModalShown = true;
  playCompletionCelebration();
}

function hasCelebrationSeen(): boolean {
  try {
    return !!uni.getStorageSync(CELEBRATION_SEEN_KEY);
  } catch {
    return false;
  }
}

/**
 * 恢复路径补触发（修复 #F-ANIM1）
 * @description watch(stage2Unlocked) 只对值变化触发：若解锁发生在 restoring=true 窗口（恢复进度期间，
 *              如商家此前已完成/运营已解锁），首次 watch 被 restoring 拦截后值不再变化 → 动画永不播放。
 *              故 restoring=false 后补查一次：已解锁且本账号从未展示过完成庆祝 → 补弹一次。
 *              返回是否已触发（触发则本轮跳过新商家 Tour，避免遮罩层叠加）。
 */
function maybePlayCelebrationOnRestore(): boolean {
  if (!taskStore.stage2Unlocked || restoring || stage2ModalShown || hasCelebrationSeen()) return false;
  playCelebrationOnce();
  return true;
}

// 阶段一完成/解锁引导：先播升华汇聚动画，再弹完成弹窗（会话内解锁变化；恢复路径由 maybePlayCelebrationOnRestore 补触发）
watch(() => taskStore.stage2Unlocked, (val) => {
  if (!val || restoring || stage2ModalShown) return;
  playCelebrationOnce();
});

/**
 * 动画结束后弹出完成引导（组件不可用/无卡片时直接弹窗兜底）
 * @description 「已看」标记只在动画确实开始（play resolve）或弹窗兜底展示后写入；
 *              动画启动失败则本次不标记，下次进入可重新播放。
 */
async function playCompletionCelebration() {
  await nextTick();
  const burst = burstRef.value;
  const cards = Array.from(taskCardElMap.values());
  if (!burst || cards.length === 0) {
    showStage2Modal.value = true;
    markCelebrationSeen();
    return;
  }
  const groups = taskGroups.value.map((g) => ({
    el: taskGroupElMap.get(g.taskId) ?? null,
    cardCount: (g.secondLevelTasks || []).length,
  }));
  try {
    // 组件内 play 为 async：await 到时间线建立（动画确实开始）后才标记已看
    await burst.play(cards, groups, () => {
      showStage2Modal.value = true;
    });
    markCelebrationSeen();
  } catch (e) {
    console.error('[完成庆祝] 动画启动失败，本次不写入已看标记', e);
    // 异常清理（#F-3 R1）：play 启动时已置 visible 并锁 body 滚动，用组件既有 stop() 释放，避免遮罩/禁滚残留
    burst.stop();
  }
}

/** 弹窗出现：modal-box 入场动画；弹窗关闭：恢复任务卡可见（动画期间保持隐藏） */
watch(showStage2Modal, async (val) => {
  if (val) {
    await nextTick();
    const box = resolveEl(stage2ModalBoxRef.value);
    if (box) {
      gsap.fromTo(
        box,
        { y: 24, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.35, ease: 'power2.out', overwrite: 'auto' },
      );
    }
    return;
  }
  taskCardElMap.forEach((el) => {
    gsap.set(el, {
      scale: 1,
      opacity: 1,
      borderRadius: '',
      filter: 'none',
      boxShadow: 'none',
      overwrite: 'auto',
    });
  });
  taskGroupElMap.forEach((el) => {
    gsap.set(el, { opacity: 1, overwrite: 'auto' });
  });
});

/** 侧边栏进度条脉冲反馈：GSAP 时间线（高亮 → 淡出），onComplete 收尾，无定时器 */
const progressPulse = ref(false);
watch(() => taskStore.progress.completed, () => {
  if (restoring) return;
  if (!sidebarProgressBarEl) return;
  progressPulse.value = true;
  gsap.killTweensOf(sidebarProgressBarEl);
  gsap.timeline({ onComplete: () => { progressPulse.value = false; } })
    .set(sidebarProgressBarEl, { opacity: 0.55 })
    .to(sidebarProgressBarEl, { opacity: 1, duration: 0.5, ease: 'power1.inOut' });
});

/** 一级任务数字进度脉冲反馈：GSAP 时间线（高亮 → 淡出），onComplete 收尾，无定时器 */
const pulseGroupIdx = ref(-1);
watch(
  () => taskGroups.value.map((g) => groupCompleted(g)),
  (cur, prev) => {
    if (restoring) return;
    let changed = -1;
    cur.forEach((c, i) => {
      if (prev[i] !== undefined && c !== prev[i]) changed = i;
    });
    if (changed < 0) return;
    pulseGroupIdx.value = changed;
    const el = navCountEls[changed];
    if (!el) {
      gsap.timeline({ onComplete: () => { pulseGroupIdx.value = -1; } }).to({}, { duration: 0.5 });
      return;
    }
    gsap.killTweensOf(el);
    gsap.timeline({ onComplete: () => { pulseGroupIdx.value = -1; } })
      .set(el, { opacity: 0.55 })
      .to(el, { opacity: 1, duration: 0.5, ease: 'power1.inOut' });
  },
);

/** 侧栏进度填充：scaleX + transformOrigin left，约 0.6s（原 width 过渡的替代） */
watch(() => taskStore.progress.percent, (val) => {
  if (!sidebarFillEl) return;
  gsap.to(sidebarFillEl, {
    scaleX: val / 100,
    duration: 0.6,
    ease: 'power1.out',
    overwrite: 'auto',
  });
});

onBeforeUnmount(() => {
  if (typeof uni.offWindowResize === 'function') uni.offWindowResize(handleWindowResize);
  setBodyScrollLock(false);
  if (sidebarFillEl) gsap.killTweensOf(sidebarFillEl);
  if (sidebarProgressBarEl) gsap.killTweensOf(sidebarProgressBarEl);
  navCountEls.forEach((el) => { if (el) gsap.killTweensOf(el); });
});
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

/* 移动端壳层几何（T-3）：抽屉宽度 / 顶栏高度按设备像素固定（不随 rpx 缩放，
   与阶段二同方案取值一致）；仅在 ≤600px 媒体查询内使用，PC 不参与布局 */
$stage1-drawer-width: 280px;
$stage1-topbar-height: 56px;

.page-layout {
  display: flex;
  min-height: 100vh;
  background-color: $u-bg-color;
}

/* 左侧导航栏 */
.sidebar {
  width: 20%;
  background-color: $u-white;
  border-right: 1rpx solid $u-border-color;
  display: flex;
  flex-direction: column;
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 100;
}

.sidebar__logo {
  display: flex;
  align-items: center;
  padding: $up-space-6 $up-space-5;
  border-bottom: 1rpx solid $u-border-color;
}

.sidebar__icon {
  width: 48rpx;
  height: 48rpx;
  background-color: $u-main-color;
  border-radius: $up-radius-sm;
  display: flex;
  align-items: center;
  justify-content: center;
  color: $u-white;
  font-size: $up-font-size-caption;
  font-weight: 700;
}

.sidebar__brand {
  margin-left: $up-space-2;
  font-size: $up-font-size-body-sm;
  font-weight: 600;
  color: $u-main-color;
}

/* 阶段标识 */
.sidebar__stage {
  display: flex;
  align-items: center;
  padding: $up-space-4 $up-space-5;
  border-bottom: 1rpx solid $u-border-color;
  background-color: $u-primary-light;
}

.sidebar__stage-num {
  width: 40rpx;
  height: 40rpx;
  background-color: $u-primary;
  color: $u-white;
  border-radius: $up-radius-full;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: $up-font-size-caption;
  font-weight: 600;
}

.sidebar__stage-title {
  margin-left: $up-space-2;
  font-size: $up-font-size-body-sm;
  font-weight: 600;
  color: $u-main-color;
}

.sidebar__progress {
  padding: $up-space-4 $up-space-5;
  border-bottom: 1rpx solid $u-border-color;
}

.sidebar__progress-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sidebar__progress-label {
  font-size: $up-font-size-caption;
  color: $u-tips-color;
  margin-bottom: $up-space-2;
}

.sidebar__progress-value {
  font-size: $up-font-size-body-sm;
  color: $u-main-color;
  font-variant-numeric: tabular-nums;
}

.sidebar__progress-bar {
  height: 8rpx;
  background-color: $u-border-color;
  border-radius: 4rpx;
  overflow: hidden;
  margin-bottom: $up-space-2;
  transition: background-color $up-ease-normal;

  &--pulse {
    background-color: $u-primary-light;
  }
}

.sidebar__progress-fill {
  width: 100%;
  height: 100%;
  background-color: $u-primary;
  border-radius: 4rpx;
  transform-origin: left;
}

.sidebar__switch {
  margin-top: $up-space-3;
  padding: $up-space-2 0;
  text-align: center;
  background-color: $u-primary-light;
  border: 1rpx solid $u-primary;
  border-radius: $up-radius-sm;
  transition: all $up-ease-normal;

  &--active {
    background-color: $u-primary;
    border-color: $u-primary;
    box-shadow: $up-shadow-btn;

    .sidebar__switch-text {
      color: $u-white;
      font-weight: 600;
    }
  }
}

.sidebar__switch-text {
  font-size: $up-font-size-caption;
  color: $u-primary;
  font-weight: 500;
  transition: color $up-ease-normal;
}

.sidebar__nav {
  flex: 1;
  padding: $up-space-4 0;
  overflow-y: auto;
}

.sidebar__nav-item {
  display: flex;
  align-items: center;
  padding: $up-space-3 $up-space-5;
  transition: background-color $up-ease-normal;

  &:hover {
    background-color: $u-bg-color;
  }

  &.active {
    background-color: $u-primary-light;
  }
}

.sidebar__nav-num {
  width: 36rpx;
  height: 36rpx;
  border-radius: 50%;
  background-color: $u-border-color;
  color: $u-tips-color;
  font-size: $up-font-size-mini;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s ease;

  &.active {
    background-color: $u-main-color;
    color: $u-white;
  }
}

.sidebar__nav-info {
  margin-left: $up-space-3;
  display: flex;
  flex-direction: column;
}

.sidebar__nav-title {
  font-size: $up-font-size-body-sm;
  color: $u-tips-color;
  line-height: 1.4;

  .sidebar__nav-item.active & {
    color: $u-main-color;
    font-weight: 500;
  }
}

.sidebar__nav-btn {
  font-size: $up-font-size-mini;
  color: $u-primary;
  margin-top: 2rpx;
}

.sidebar__nav-count {
  font-size: $up-font-size-mini;
  color: $u-tips-color;
  margin-top: 2rpx;
  transition: color $up-ease-normal;
  font-variant-numeric: tabular-nums;

  &--pulse {
    color: $u-primary;
  }
}

.sidebar__user {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $up-space-4 $up-space-5;
  border-top: 1rpx solid $u-border-color;
}

/* 左侧登录态（头像 + 商家名）；min-width:0 允许长昵称收缩，不挤压右侧退出入口 */
.sidebar__user-main {
  display: flex;
  align-items: center;
  min-width: 0;
}

.sidebar__avatar {
  width: 40rpx;
  height: 40rpx;
  background-color: $u-main-color;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: $u-white;
  font-size: $up-font-size-caption;
  font-weight: 600;
}

.sidebar__username {
  margin-left: $up-space-2;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: $up-font-size-body-sm;
  color: $u-main-color;
}

/* 退出登录入口：用户信息同一行、右对齐的轻量文字按钮（不再单独占一行） */
.sidebar__logout {
  flex-shrink: 0;
  margin-left: $up-space-3;
  font-size: $up-font-size-caption;
  color: $u-tips-color;
  transition: color $up-ease-fast;

  &:hover {
    color: $u-primary;
  }

  &:active {
    color: $u-primary;
  }
}

/* 重新观看引导入口（轻量链接风格，Token 化） */
.sidebar__tour-entry {
  padding: $up-space-3 $up-space-5;
  text-align: center;
  border-top: 1rpx solid $u-border-color;
  transition: background-color $up-ease-fast;

  &:active {
    background-color: $u-bg-color;
  }

  &-text {
    font-size: $up-font-size-caption;
    color: $u-tips-color;
    transition: color $up-ease-fast;

    .sidebar__tour-entry:active & {
      color: $u-primary;
    }
  }
}

/* 右侧内容区 */
.main-content {
  flex: 1;
  /* 窄视口：允许收缩到可用宽度（flex 项默认 min-width:auto 会被内容 min-content 撑破视口，T-1） */
  min-width: 0;
  margin-left: 20%;
  padding: $up-space-6;
}

/* ============================================================
   移动端壳层（≤600px，T-3 方案）：侧栏转抽屉 + 新增固定顶栏
   PC（>600px）零回归：顶栏/遮罩基础规则即 display:none（不渲染、不占位），
   侧栏宽度/定位/层级/内容保持原样；只有媒体查询命中时才切换为抽屉形态。
   ============================================================ */

/* 顶栏与遮罩：PC 隐藏（抽屉展开态也只可能出现在 ≤600px） */
.sidebar__topbar,
.sidebar__mask {
  display: none;
}

/* 顶栏左：汉堡按钮（三横线） */
.sidebar__topbar-toggle {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: $up-space-1;
  width: 40rpx;
  height: 40rpx;
  flex-shrink: 0;
}

.sidebar__topbar-bar {
  width: 100%;
  height: 4rpx;
  background-color: $u-main-color;
  border-radius: $up-radius-xs;
}

/* 顶栏中：当前阶段 + 进度摘要（紧凑两行） */
.sidebar__topbar-info {
  flex: 1;
  min-width: 0;
  margin-left: $up-space-4;
  display: flex;
  flex-direction: column;
}

.sidebar__topbar-title {
  font-size: $up-font-size-h3;
  font-weight: 600;
  line-height: $up-line-height-tight;
  color: $u-main-color;
}

.sidebar__topbar-progress {
  font-size: $up-font-size-caption;
  line-height: $up-line-height-tight;
  color: $u-tips-color;
}

/* 顶栏右：用户头像（尺寸/配色与 .sidebar__avatar 一致） */
.sidebar__topbar-avatar {
  flex-shrink: 0;
  width: 40rpx;
  height: 40rpx;
  background-color: $u-main-color;
  border-radius: $up-radius-full;
  display: flex;
  align-items: center;
  justify-content: center;
  color: $u-white;
  font-size: $up-font-size-caption;
  font-weight: 600;
}

@media (max-width: 600px) {
  /* 侧栏 → 抽屉：固定 280px，默认整体左移出屏（负方向不产生横向溢出） */
  .sidebar {
    width: $stage1-drawer-width;
    transform: translateX(-100%);
    transition: transform $up-ease-slow;
    z-index: 200;
  }

  /* 展开态：滑入 + 抽屉投影（层级 200 > 遮罩 150 > 顶栏 100，抽屉盖住顶栏左段） */
  .sidebar--open {
    transform: translateX(0);
    box-shadow: $up-shadow-lg;
  }

  /* 固定顶栏：占满宽度、高 56px，为主内容区上方的常驻入口 */
  .sidebar__topbar {
    display: flex;
    align-items: center;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: $stage1-topbar-height;
    padding: 0 $up-space-5;
    background-color: $u-white;
    border-bottom: 1rpx solid $u-border-color;
    z-index: 100;
  }

  /* 遮罩：铺满视口、拦截背景点击（点击即收起抽屉） */
  .sidebar__mask {
    display: block;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-color: $u-overlay;
    z-index: 150;
  }

  /* 主内容：脱离 20% 侧栏留白；顶部为固定顶栏让位并保留 $up-space-6 内容节奏 */
  .main-content {
    margin-left: 0;
    padding-top: calc(#{$stage1-topbar-height} + #{$up-space-6});
  }
}

/* 进度恢复失败轻量提示（非阻塞横幅，Token 化） */
.restore-fail-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: $up-space-2;
  margin-bottom: $up-space-3;
  padding: $up-space-2 $up-space-4;
  background-color: $u-warning-light;
  border: 1rpx solid $u-tag-warning-border;
  border-radius: $up-radius-md;
  cursor: pointer;
  transition: background-color $up-ease-fast;

  &:active {
    opacity: 0.85;
  }

  &__text {
    font-size: $up-font-size-body-sm;
    color: $u-warning-dark;
  }

  &__refresh {
    font-size: $up-font-size-body-sm;
    font-weight: $up-font-weight-medium;
    color: $u-primary;
  }
}


/* 弹窗样式 */
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
  border-radius: $up-radius-md;
  width: 90%;
  max-width: 600rpx;
  max-height: 80vh;
  overflow: hidden;

  &--small {
    max-width: 400rpx;
  }
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $up-space-3 $up-space-5;
  border-bottom: 1px solid $u-border-color;
}

.modal-title {
  font-size: $up-font-size-h3;
  font-weight: 600;
  color: $u-main-color;
}

.modal-close {
  font-size: $up-font-size-h2;
  color: $u-tips-color;
  padding: $up-space-2;
}

.modal-body {
  padding: $up-space-5;
}

.modal-table {
  width: 100%;
}

.modal-table-row {
  display: flex;
  border-bottom: 1px solid $u-border-color;

  &:last-child {
    border-bottom: none;
  }
}

.modal-table-header {
  background-color: $u-bg-color;
}

.modal-table-cell {
  flex: 1;
  padding: $up-space-3 $up-space-4;
  font-size: $up-font-size-caption;
  color: $u-main-color;
  font-variant-numeric: tabular-nums;
}

.modal-note {
  margin-top: $up-space-4;
  padding: $up-space-3;
  background-color: $u-warning-light;
  border: 1px solid $u-tag-warning-border;
  border-radius: $up-radius-sm;
  font-size: $up-font-size-caption;
  color: $u-warning-dark;
}

.modal-text {
  margin-top: $up-space-4;
  font-size: $up-font-size-body-sm;
  color: $u-content-color;
}

.modal-box--large {
  max-width: 700rpx;
}

.qr-code-area {
  padding: 40rpx 0;
}

.qr-code-placeholder {
  width: 400rpx;
  height: 400rpx;
  background-color: $u-bg-color;
  border: 2rpx dashed $u-light-color;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
  border-radius: $up-radius-md;
}

.qr-code-placeholder__text {
  font-size: $up-font-size-h3;
  color: $u-tips-color;
  font-weight: 500;
}

.qr-code-placeholder__hint {
  font-size: $up-font-size-caption;
  color: $u-light-color;
  margin-top: $up-space-2;
}

.qr-code-image {
  width: 400rpx;
  height: 400rpx;
  margin: 0 auto;
  border-radius: $up-radius-md;
}

.modal-hint {
  margin-top: $up-space-4;
  font-size: $up-font-size-caption;
  color: $u-tips-color;
}

/* 阶段一完成弹窗 */
.stage2-done-modal {
  padding: $up-space-8 $up-space-6 $up-space-6;
  text-align: center;
}

.stage2-done-modal__icon {
  width: 96rpx;
  height: 96rpx;
  margin: 0 auto $up-space-4;
  border-radius: $up-radius-full;
  background-color: $u-primary-light;
  color: $u-primary;
  font-size: $up-font-size-h1;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stage2-done-modal__title {
  font-size: $up-font-size-h3;
  font-weight: 600;
  color: $u-main-color;
  margin-bottom: $up-space-3;
}

.stage2-done-modal__desc {
  font-size: $up-font-size-body;
  color: $u-content-color;
  line-height: 1.6;
  margin-bottom: $up-space-6;
}

.stage2-done-modal__actions {
  display: flex;
  gap: $up-space-3;
}

.stage2-done-modal__btn {
  flex: 1;
  padding: $up-space-3 0;
  border-radius: $up-radius-sm;
  text-align: center;
  transition: transform $up-ease-fast, background-color $up-ease-fast, box-shadow $up-ease-fast;

  /* 按压微动效 */
  &:active {
    transform: scale(0.97);
  }

  &--secondary {
    background-color: $u-white;
    border: 1rpx solid $u-border-color;

    &:active {
      background-color: $u-bg-color;
    }
  }

  &--primary {
    background-color: $u-primary;
    border: 1rpx solid $u-primary;
    box-shadow: $up-shadow-btn;

    &:active {
      background-color: $u-primary-dark;
    }
  }
}

.stage2-done-modal__btn-text {
  font-size: $up-font-size-body-sm;
  font-weight: 500;

  .stage2-done-modal__btn--secondary & {
    color: $u-content-color;
  }

  .stage2-done-modal__btn--primary & {
    color: $u-white;
  }
}

.stage-section {
  margin-bottom: $up-space-12;
}

/* 取消全部完成确认弹窗（全 Token：遮罩/圆角/阴影/按钮配色取设计规范 §3.3） */
.group-cancel-modal {
  &__text {
    display: block;
    font-size: $up-font-size-body;
    color: $u-content-color;
    line-height: 1.6;
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
  }
}

/* ---------- 右下角反馈浮窗（fixed；移动端 + PC Web 通用） ---------- */
.feedback-fab {
  position: fixed;
  right: $up-space-6;
  bottom: $up-space-8;
  z-index: 300;
  display: flex;
  align-items: center;
  gap: $up-space-2;
  padding: $up-space-3 $up-space-5;
  background-color: $u-primary;
  border-radius: $up-radius-full;
  box-shadow: $up-shadow-btn;
  cursor: pointer;
  transition: transform $up-ease-fast, background-color $up-ease-fast, box-shadow $up-ease-fast;

  &--hover {
    transform: translateY(-2rpx);
    background-color: $u-primary-dark;
    box-shadow: $up-shadow-lg;
  }

  &__icon {
    font-size: $up-font-size-body;
    color: $u-white;
    line-height: 1;
  }

  &__text {
    font-size: $up-font-size-body-sm;
    font-weight: $up-font-weight-medium;
    color: $u-white;
    white-space: nowrap;
  }
}

/* ---------- 退出登录确认弹窗（Modal slot 内容，Token 化） ---------- */
.logout-modal {
  display: flex;
  flex-direction: column;
  gap: $up-space-5;

  &__text {
    font-size: $up-font-size-body-sm;
    color: $u-content-color;
    line-height: 1.6;
  }

  &__actions {
    display: flex;
    gap: $up-space-3;
  }

  &__btn {
    flex: 1;
    padding: $up-space-3 0;
    border-radius: $up-radius-sm;
    text-align: center;
    transition: background-color $up-ease-fast;

    &--secondary {
      background-color: $u-white;
      border: 1rpx solid $u-border-color;
    }

    &--primary {
      background-color: $u-primary;
      border: 1rpx solid $u-primary;

      &:hover {
        background-color: $u-primary-dark;
      }

      &:active {
        background-color: $u-primary-dark;
      }
    }
  }

  &__btn-text {
    font-size: $up-font-size-body-sm;
    font-weight: 500;
    color: $u-content-color;

    .logout-modal__btn--primary & {
      color: $u-white;
    }
  }
}

/* ---------- 意见反馈弹窗表单（Modal slot 内容，Token 化） ---------- */
.feedback-form {
  display: flex;
  flex-direction: column;
  gap: $up-space-4;

  &__field {
    display: flex;
    flex-direction: column;
    gap: $up-space-2;
  }

  &__label {
    font-size: $up-font-size-caption;
    color: $u-tips-color;
  }

  &__textarea {
    width: 100%;
    min-height: 200rpx;
    padding: $up-space-3;
    background-color: $u-white;
    border: 1rpx solid $u-border-color;
    border-radius: $up-radius-sm;
    font-size: $up-font-size-body-sm;
    color: $u-main-color;
    line-height: 1.6;
    box-sizing: border-box;
  }

  &__placeholder {
    color: $u-tips-color;
    font-size: $up-font-size-body-sm;
  }

  &__count {
    align-self: flex-end;
    font-size: $up-font-size-mini;
    color: $u-tips-color;
  }

  &__cats {
    display: flex;
    flex-wrap: wrap;
    gap: $up-space-2;
  }

  &__cat {
    padding: $up-space-2 $up-space-4;
    border: 1rpx solid $u-border-color;
    border-radius: $up-radius-full;
    background-color: $u-white;
    cursor: pointer;
    transition: all $up-ease-fast;

    &--active {
      background-color: $u-primary-light;
      border-color: $u-primary;
    }

    &--active &-text {
      color: $u-primary-dark;
    }
  }

  &__cat-text {
    font-size: $up-font-size-caption;
    color: $u-content-color;
  }

  &__service {
    display: flex;
    align-items: center;
    gap: $up-space-3;
    padding: $up-space-3 $up-space-4;
    background-color: $u-bg-color;
    border: 1rpx dashed $u-border-color;
    border-radius: $up-radius-sm;
    cursor: pointer;
    transition: background-color $up-ease-fast;

    &:active {
      background-color: $u-primary-light;
    }
  }

  &__service-icon {
    font-size: $up-font-size-h3;
    line-height: 1;
  }

  &__service-info {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2rpx;
  }

  &__service-title {
    font-size: $up-font-size-body-sm;
    font-weight: $up-font-weight-medium;
    color: $u-main-color;
  }

  &__service-desc {
    font-size: $up-font-size-mini;
    color: $u-tips-color;
  }

  &__service-arrow {
    font-size: $up-font-size-h3;
    color: $u-tips-color;
  }

  &__submit {
    padding-top: $up-space-2;
  }

  &__btn {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 80rpx;
    border-radius: $up-radius-sm;
    cursor: pointer;
    transition: background-color $up-ease-fast, opacity $up-ease-fast;

    &--primary {
      background-color: $u-primary;

      &:active {
        background-color: $u-primary-dark;
      }
    }

    &--disabled {
      opacity: 0.6;
    }
  }

  &__btn-text {
    font-size: $up-font-size-body;
    font-weight: $up-font-weight-medium;
    color: $u-white;
  }
}

</style>












