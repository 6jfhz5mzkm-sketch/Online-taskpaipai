<!--
  @Component Stage2Sidebar
  @Version 1.6.1
  @Description 阶段二（开店搭建）左侧导航：Logo/返回任务中心、阶段标识、阶段进度、
               T2.1-T2.4 模块导航（含各模块完成数）、数据分析专区（排版对齐侧边栏节奏：
               白底弱化容器 + 顶部主色短装饰线 + 标题锚点 + PNG 图标入口行（static/images/data-center-upload.png 上传[主按钮] /
               data-center-visual.png 看板及AI经营分析[次按钮]），无冗余编号，hover 200ms + GSAP 轻入场，始终显示）、
               用户信息。视觉与阶段一 index.vue 侧边栏一致，
               样式遵循设计规范 §3.3/§3.5/§3.6/§3.7/§3.8（排版优先、主次分明、展现克制）。
               T-3 移动端（≤600px）：同一份侧栏 DOM 转抽屉（280px，translateX 滑入/滑出）+
               固定顶栏（56px：汉堡开合 + 当前阶段与进度摘要 + 用户头像）+ 遮罩点击关闭；
               抽屉展开时禁止背景滚动，选中导航项/跳转前自动收起；PC（>600px）完全不变。
               #F-19：用户区新增「退出登录」入口（按本地登录态显隐）+ 二次确认弹窗（共享 Modal），
               确认后清 token + merchant 并回登录页；交互与文案与阶段一侧栏完全一致。
               #F-26：经营类目入口行加前置店铺图标（与弹窗内一级入口同一枚，见 ./_icons.scss），
               不改该行结构、位置与「未保存」小红点。
-->
<template>
  <view class="stage2-sidebar">
  <!-- 移动端顶栏（≤600px 显示；PC 为 display:none，不参与布局与渲染）：
       左侧汉堡开合抽屉 + 中间当前阶段与进度摘要 + 右侧用户头像 -->
  <view class="sidebar__topbar">
    <view class="sidebar__topbar-toggle" @tap="toggleDrawer">
      <view class="sidebar__topbar-bar" />
      <view class="sidebar__topbar-bar" />
      <view class="sidebar__topbar-bar" />
    </view>
    <view class="sidebar__topbar-info">
      <text class="sidebar__topbar-title">开店搭建</text>
      <text class="sidebar__topbar-progress">阶段进度 {{ progress.completed }}/{{ progress.total }}</text>
    </view>
    <view v-if="userName" class="sidebar__topbar-avatar">{{ userName.charAt(0) }}</view>
  </view>

  <!-- 抽屉遮罩（≤600px 且抽屉展开时渲染；点击关闭，PC 不渲染） -->
  <view v-if="drawerOpen" class="sidebar__mask" @tap="closeDrawer" />

  <view class="sidebar" :class="{ 'sidebar--open': drawerOpen }">
    <!-- Logo -->
    <view class="sidebar__logo" @tap="handleGoHome">
      <view class="sidebar__icon">P</view>
      <text class="sidebar__brand">商家任务中心</text>
    </view>

    <!-- 阶段标识 -->
    <view class="sidebar__stage">
      <view class="sidebar__stage-num">2</view>
      <text class="sidebar__stage-title">开店搭建</text>
    </view>

    <!-- 阶段进度 -->
    <view class="sidebar__progress">
      <view class="sidebar__progress-row">
        <text class="sidebar__progress-label">阶段进度</text>
        <text class="sidebar__progress-value">{{ progress.completed }}/{{ progress.total }}</text>
      </view>
      <view class="sidebar__progress-bar">
        <view class="sidebar__progress-fill" ref="progressFillRef" />
      </view>
      <view class="sidebar__switch sidebar__switch--active" @tap="handleGoHome">
        <text class="sidebar__switch-text">切换阶段 ←</text>
      </view>
    </view>

    <!-- 一级任务导航 -->
    <view class="sidebar__nav">
      <view
        v-for="(stage, idx) in stages"
        :key="stage.stageId"
        class="sidebar__nav-item"
        :class="{ active: activeIndex === idx }"
        @tap="handleSelect(idx)"
      >
        <view class="sidebar__nav-num" :class="{ active: activeIndex === idx }">{{ idx + 1 }}</view>
        <view class="sidebar__nav-info">
          <text class="sidebar__nav-title">{{ stage.title }}</text>
          <text class="sidebar__nav-count">{{ getCompletedCount(stage) }}/{{ getTotalCount(stage) }}</text>
        </view>
      </view>
    </view>

    <!-- 数据分析专区（排版对齐侧边栏节奏；容器弱化为背景、标题主色锚点、按钮为操作焦点；
         行内 PNG 图标（static/images/data-center-upload.png / data-center-visual.png）、无冗余编号；hover 200ms 微交互 + GSAP 轻入场） -->
    <view class="sidebar__section">
      <view class="sidebar__section-accent" />
      <text class="sidebar__section-title">数据分析专区</text>
      <DataSectionEntry
        icon-src="/static/images/data-center-upload.png"
        label="店铺数据上传"
        button-text="上传"
        variant="primary"
        :icon-size="44"
        @click="goDataUpload"
      />
      <DataSectionEntry
        icon-src="/static/images/data-center-visual.png"
        label="数据看板及AI经营分析"
        button-text="查看"
        variant="secondary"
        @click="goDataBoard"
      />
    </view>

    <!-- 经营类目入口（常驻；位于用户区上方，移动端抽屉内同样可见）：打开经营类目选择与保存弹窗；
         未保存时入口内显示小红点（状态与自动弹窗判定同源，见 props.categoryUnsaved） -->
    <view class="sidebar__category" @tap="openCategoryDialog">
      <view class="sidebar__category-icon" />
      <text class="sidebar__category-text">{{ CATEGORY_PICKER_TITLE }}</text>
      <view v-if="categoryUnsaved" class="sidebar__category-dot" />
    </view>

    <!-- 用户信息 + 退出登录（融合为同一行：左侧登录态、右侧退出入口；与阶段一同一交互与文案） -->
    <view v-if="userName || isLoggedIn" class="sidebar__user">
      <template v-if="userName">
        <view class="sidebar__avatar">{{ userName.charAt(0) }}</view>
        <text class="sidebar__username">{{ userName }}</text>
      </template>
      <view v-if="isLoggedIn" class="sidebar__logout" @tap="openLogoutModal">
        <text class="sidebar__logout-text">{{ LOGOUT_ENTRY_TEXT }}</text>
      </view>
    </view>
  </view>

  <!-- 退出登录二次确认（复用共享 Modal 组件；必须与 .sidebar 同级——抽屉的 transform 会成为
       fixed 后代的包含块，挂在 .sidebar 内会随抽屉滑动/被裁切） -->
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

  <!-- 经营类目选择与保存弹窗（首次进入自动弹 + 侧栏入口同一实例；同样与 .sidebar 同级） -->
  <CategoryPicker
    :visible="categoryDialogVisible"
    @update:visible="onCategoryDialogVisible"
    @skip="onCategorySkip"
    @saved="onCategorySaved"
  />
  </view>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue';
import Modal from '@/components/Modal/index.vue';
import DataSectionEntry from '@/components-local/stage2/DataSectionEntry.vue';
import CategoryPicker from '@/components-local/stage2/CategoryPicker.vue';
import { logout } from '@/utils/auth';
import {
  LOGOUT_CONFIRM_CANCEL_TEXT,
  LOGOUT_CONFIRM_MESSAGE,
  LOGOUT_CONFIRM_OK_TEXT,
  LOGOUT_CONFIRM_TITLE,
  LOGOUT_ENTRY_TEXT,
} from '@/constants/auth';
import { CATEGORY_PICKER_TITLE } from '@/constants/category';
import type { StageInfo, TaskProgress } from '@/types/task';

interface Props {
  stages: StageInfo[];
  progress: TaskProgress;
  activeIndex?: number;
  userName?: string;
  /** 宿主页判定「未保存经营类目」时置 true：本次驻留自动弹一次经营类目弹窗（可跳过） */
  autoPromptCategory?: boolean;
  /** 经营类目是否尚未保存（与 autoPromptCategory 同源、由宿主页同一次查询得出）：控制入口小红点显隐 */
  categoryUnsaved?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  activeIndex: 0,
  userName: '',
  autoPromptCategory: false,
  categoryUnsaved: false,
});

const emit = defineEmits<{
  select: [index: number];
  'go-home': [];
  /** 经营类目弹窗关闭（供宿主页续跑后续引导，避免弹层叠加） */
  'category-closed': [];
  /** 经营类目保存成功（宿主页据此立即把「未保存」翻转为已保存，红点即时消失） */
  'category-saved': [];
}>();

/** 移动端主断点：与 #F-5/T-1 已确立的 600px 主断点一致（抽屉/顶栏仅在 ≤600px 生效） */
const MOBILE_BREAKPOINT = 600;

/** 移动端抽屉展开状态（≤600px 才有顶栏/遮罩可操作；PC 恒为 false） */
const drawerOpen = ref(false);

/** 是否已登录（本地有 token）：控制「退出登录」入口显隐，不依赖 nickname 是否存在 */
const isLoggedIn = ref(false);

/** 退出登录二次确认弹窗可见性 */
const showLogoutModal = ref(false);

/** 打开退出登录确认弹窗 */
function openLogoutModal(): void {
  showLogoutModal.value = true;
}

/** 关闭退出登录确认弹窗（二次确认的「取消」/遮罩/ESC/关闭按钮；取消即不退出） */
function closeLogoutModal(): void {
  showLogoutModal.value = false;
}

/** 共享 Modal 的 visible 双向同步 */
function onLogoutModalVisible(visible: boolean): void {
  showLogoutModal.value = visible;
}

/** 确认退出：清登录态（token + merchant）并回登录页（复用 utils/auth 的登出实现，不另写清理逻辑） */
function confirmLogout(): void {
  showLogoutModal.value = false;
  logout();
}

/* ---------- 经营类目弹窗（首次进入自动弹 + 侧栏常驻入口，同一实例） ---------- */

/** 经营类目弹窗可见性 */
const categoryDialogVisible = ref(false);

/** 本次页面驻留是否已自动弹过（不落任何持久标记） */
const categoryPrompted = ref(false);

/** 本次页面驻留用户是否点过「跳过」（仅内存态，不写 storage/后端；下次进入重新判定） */
const categorySkipped = ref(false);

/** 侧栏常驻入口 / 自动弹窗共用打开动作 */
function openCategoryDialog(): void {
  categoryDialogVisible.value = true;
}

/** 共享 Modal/弹窗的 visible 同步（× / 遮罩 / ESC 关闭亦不写库） */
function onCategoryDialogVisible(visible: boolean): void {
  categoryDialogVisible.value = visible;
  if (!visible) emit('category-closed');
}

/** 跳过：仅本次驻留不再自动弹（不写库、不报错、不写永久静默标记） */
function onCategorySkip(): void {
  categorySkipped.value = true;
}

/** 保存成功：本次驻留不再自动弹，并上抛给宿主页刷新「未保存」状态（小红点即时消失） */
function onCategorySaved(): void {
  categoryPrompted.value = true;
  emit('category-saved');
}

/** 宿主页判定「未保存经营类目」→ 本次驻留自动弹一次（已弹过/已跳过则不再弹） */
watch(
  () => props.autoPromptCategory,
  (shouldPrompt) => {
    if (!shouldPrompt || categoryPrompted.value || categorySkipped.value) return;
    categoryPrompted.value = true;
    categoryDialogVisible.value = true;
  },
  { immediate: true },
);

/** 当前视口是否为移动端（跨端取 uni 系统信息，不依赖 window） */
function isMobileViewport(): boolean {
  return uni.getSystemInfoSync().windowWidth <= MOBILE_BREAKPOINT;
}

/** 变更抽屉状态（唯一入口）：同步改写/还原页面滚动锁，
 *  不依赖 watch 的异步 flush —— 选中导航项时「先解锁再触发页面滚动」必须在同一个 tick 内完成，
 *  否则 pageScrollTo 在 html{overflow:hidden} 期间会被浏览器忽略（T-3 实测）。 */
function setDrawerOpen(open: boolean): void {
  if (drawerOpen.value === open) return;
  drawerOpen.value = open;
  setPageScrollLock(open);
}

/** 汉堡按钮开合抽屉 */
function toggleDrawer(): void {
  setDrawerOpen(!drawerOpen.value);
}

/** 收起抽屉（遮罩点击 / 导航跳转 / 视口跨回 PC 宽度） */
function closeDrawer(): void {
  setDrawerOpen(false);
}

/** 抽屉展开期间被改写的滚动容器内联样式快照（收起时原样还原，不吃掉页面自身的设置） */
let scrollLockSnapshot: { html: string; body: string } | null = null;

/** 抽屉展开时禁止背景滚动（H5）。
 *  沿用项目既有做法（CompletionCelebration：document.body.style.overflow）并补一层 html：
 *  uni-app H5 的实际滚动容器是 <html>（T-3 实测：仅设 body 时 window.scrollTo 仍可滚动，
 *  设 html 后 scrollY 保持 0），故两者一并锁定/还原，不引入任何新依赖。 */
function setPageScrollLock(locked: boolean): void {
  if (typeof document === 'undefined' || !document.documentElement) return;
  const html = document.documentElement;
  const body = document.body;
  if (locked) {
    if (!scrollLockSnapshot) {
      scrollLockSnapshot = { html: html.style.overflow, body: body ? body.style.overflow : '' };
    }
    html.style.overflow = 'hidden';
    if (body) body.style.overflow = 'hidden';
    return;
  }
  if (scrollLockSnapshot) {
    html.style.overflow = scrollLockSnapshot.html;
    if (body) body.style.overflow = scrollLockSnapshot.body;
    scrollLockSnapshot = null;
  }
}

/** 视口跨回 PC 宽度时强制收起抽屉并解除滚动锁（保证 PC 零残留） */
function handleWindowResize(): void {
  if (!isMobileViewport()) closeDrawer();
}

onMounted(() => {
  if (typeof uni.onWindowResize === 'function') uni.onWindowResize(handleWindowResize);
  // 登录态：决定「退出登录」入口是否显示（与 nickname 是否存在解耦，与阶段一一致）
  isLoggedIn.value = !!uni.getStorageSync('token');
});

onUnmounted(() => {
  if (typeof uni.offWindowResize === 'function') uni.offWindowResize(handleWindowResize);
  setPageScrollLock(false);
});

/** 选中一级任务导航：先收起抽屉再上报宿主页 */
function handleSelect(index: number): void {
  closeDrawer();
  emit('select', index);
}

/** 返回任务中心：先收起抽屉再上报宿主页 */
function handleGoHome(): void {
  closeDrawer();
  emit('go-home');
}

/** 进度填充元素（CSS transition 驱动 transform: scaleX） */
const progressFillRef = ref<HTMLElement | null>(null);

function clampPercent(value: number): number {
  return Math.min(100, Math.max(0, value));
}

/** uni-view ref 解出真实 DOM 元素（H5 下 view 编译为 div；兼容 $el 包装） */
function resolveEl(refValue: unknown): HTMLElement | null {
  const v = refValue as { $el?: unknown } | HTMLElement | null;
  return (v && (v.$el as HTMLElement | undefined)) || (v as HTMLElement | null) || null;
}

/** 进度填充：直接写 transform: scaleX（F2-GSAP9：CSS transition 原生驱动，绕开 gsap 环境异常） */
function setFillScale(value: number): void {
  const el = resolveEl(progressFillRef.value);
  if (el) {
    el.style.transform = 'scaleX(' + value + ')';
  }
}

onMounted(() => {
  // 进度条：从 CSS 初始 scaleX(0) 生长到当前比例（transition 0.6s）
  setFillScale(clampPercent(props.progress.percent) / 100);
  // B12：数据分析专区的入场淡入上移改由纯 CSS 动画（.sidebar__section 的 animation）驱动，
  //      不再依赖 requestAnimationFrame 与 DOM classList —— 非 H5（小程序/App）下 <view> 的 ref
  //      拿不到真实 HTMLElement，原实现只在 H5 生效。
});

watch(
  () => props.progress.percent,
  (percent) => {
    setFillScale(clampPercent(percent) / 100);
  },
);

function getTotalCount(stage: StageInfo): number {
  return (stage.firstLevelTasks || []).reduce((sum, flt) => sum + (flt.secondLevelTasks || []).length, 0);
}

function getCompletedCount(stage: StageInfo): number {
  return (stage.firstLevelTasks || []).reduce(
    (sum, flt) =>
      sum + (flt.secondLevelTasks || []).filter((t) => t.completionStatus === 'completed' || t.defaultCompleted === 1).length,
    0,
  );
}

/** 数据分析专区入口跳转（当前已在目标页时不再重复入栈） */
function goDataCenterPage(url: string) {
  const pages = getCurrentPages();
  const currentRoute = pages[pages.length - 1]?.route || '';
  if (currentRoute === url.replace(/^\//, '')) return;
  uni.navigateTo({ url });
}

/** 进入店铺数据上传独立页（抽屉内跳转，先收起抽屉） */
function goDataUpload() {
  closeDrawer();
  goDataCenterPage('/pages/data-center/upload');
}

/** 进入数据看板页（指标 + AI 经营分析一体；抽屉内跳转，先收起抽屉） */
function goDataBoard() {
  closeDrawer();
  goDataCenterPage('/pages/data-center/index');
}
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';
@import '@/components-local/stage2/_layout.scss';
@import '@/styles/mixins/_icons.scss';

/* 壳层根节点（.stage2-sidebar）：无自身样式，只把「固定顶栏 + 遮罩 + 侧栏」收在同一个组件根下。
   抽屉与顶栏必须是兄弟节点——侧栏抽屉的 transform 会成为内部 fixed 后代的包含块，顶栏若放在
   .sidebar 内会跟着一起滑走。三者都是 fixed 定位，不参与页面 flex 布局，PC 端布局与改动前一致。 */

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

.sidebar__progress-label {
  font-size: $up-font-size-caption;
  color: $u-tips-color;
  margin-bottom: $up-space-2;
}

.sidebar__progress-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sidebar__progress-value {
  font-size: $up-font-size-body-sm;
  color: $u-main-color;
}

.sidebar__progress-bar {
  height: 8rpx;
  background-color: $u-border-color;
  border-radius: 4rpx;
  overflow: hidden;
  margin-bottom: $up-space-2;
}

.sidebar__progress-fill {
  width: 100%;
  height: 100%;
  background-color: $u-primary;
  border-radius: 4rpx;
  /* F2-GSAP9：纯 CSS transition（开源进度条成熟做法），从 scaleX(0) 生长到目标比例 */
  transform-origin: left center;
  transform: scaleX(0);
  transition: transform 0.6s cubic-bezier(0.455, 0.03, 0.515, 0.955);
  will-change: transform;
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
  transition: background-color 0.2s ease;

  &.active {
    background-color: $u-primary-light;
  }
}

.sidebar__nav-num {
  width: 36rpx;
  height: 36rpx;
  border-radius: $up-radius-full;
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

.sidebar__nav-count {
  font-size: $up-font-size-mini;
  color: $u-tips-color;
  margin-top: 2rpx;
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

/* 数据分析专区：容器弱化为背景（白底 + 顶部短装饰线 + 与整体一致的 padding/分隔线节奏），
   标题为独立标题层级（§3.6 h3：16px/24px/600，主色锚点，不再与正文同字号同格式），
   入口行由 DataSectionEntry 封装（透明底 + hover 浅绿 §3.5，按钮按 §3.3 主/次配色）；
   排版对齐侧边栏：区块 padding $up-space-4/$up-space-5（与进度/用户区一致） */
.sidebar__section {
  padding: $up-space-4 $up-space-5;
  border-bottom: 1rpx solid $u-border-color;
  /* F2-GSAP9 / B12：入场淡入上移改由纯 CSS 动画驱动（挂载即播放），不依赖 requestAnimationFrame
     与 DOM classList，H5 / 小程序 / App 一致生效；时长与缓动取自设计规范 §3.10 $up-ease-slow */
  animation: sidebar-section-enter $up-ease-slow both;

  /* 顶部短装饰线：分区锚点（克制，不抢内容） */
  &-accent {
    width: 48rpx;
    height: 4rpx;
    border-radius: $up-radius-xs;
    background-color: $u-primary;
    margin-bottom: $up-space-2;
  }

  /* 分区标题：独立标题层级（§3.6 h3 16px/24px/600），主色锚点，与正文 body-sm 明确区分 */
  &-title {
    display: block;
    font-size: $up-font-size-h3;
    line-height: $up-line-height-normal;
    font-weight: 600;
    color: $u-primary;
    margin-bottom: $up-space-3;
  }
}

/* 数据分析专区入场：淡入 + 上移 8rpx（纯 CSS，跨端一致） */
@keyframes sidebar-section-enter {
  from {
    opacity: 0;
    transform: translateY(8rpx);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.sidebar__user {
  display: flex;
  align-items: center;
  min-width: 0;
  padding: $up-space-4 $up-space-5;
  border-top: 1rpx solid $u-border-color;
}

.sidebar__avatar {
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

.sidebar__username {
  flex: 1;
  min-width: 0;
  margin-left: $up-space-2;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  font-size: $up-font-size-body-sm;
  color: $u-main-color;
}

/* ---------- 经营类目入口（常驻，位于用户区上方；Token 化，与退出登录行同节奏） ----------
   行内布局用于承载「未保存」小红点；红点随文字居中，不改变行高、不缩小整行点击热区 */
.sidebar__category {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: $up-space-3 $up-space-5;
  border-top: 1rpx solid $u-border-color;
  transition: background-color $up-ease-fast;

  &:hover {
    background-color: $u-bg-color;
  }

  &:active {
    background-color: $u-bg-color;
  }

  /* 前置图标：与类目弹窗内一级入口同一枚店铺图标（造型见 _icons.scss 唯一真源） */
  &-icon {
    @include stage2-icon(stage2-shop-icon($u-primary), $up-font-size-body);
    margin-right: $up-space-1;
  }

  &-text {
    font-size: $up-font-size-caption;
    color: $u-content-color;
  }

  /* 未保存小红点（颜色/尺寸/圆角取 Token；移动端抽屉内同为行内元素，不会被裁剪） */
  &-dot {
    flex-shrink: 0;
    width: 12rpx;
    height: 12rpx;
    margin-left: $up-space-1;
    background-color: $u-error;
    border-radius: $up-radius-full;
  }
}

/* ---------- 退出登录（#F-19：用户区入口 + 二次确认；与阶段一侧栏同款视觉，全 Token） ---------- */

/* 入口：融合进用户行右侧的轻量按钮（不再独占一行；登录态下恒可达，移动端抽屉内可见） */
.sidebar__logout {
  flex-shrink: 0;
  margin-left: auto;
  padding: $up-space-1 $up-space-2;
  background-color: $u-white;
  border: 1rpx solid $u-border-color;
  border-radius: $up-radius-sm;
  transition: background-color $up-ease-fast, border-color $up-ease-fast;

  &:hover,
  &:active {
    background-color: $u-primary-light;
    border-color: $u-primary;
  }

  &-text {
    font-size: $up-font-size-caption;
    color: $u-tips-color;
  }
}

/* 二次确认弹窗（共享 Modal 的 slot 内容：说明 + 取消/确认） */
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

/* 顶栏左：汉堡按钮（三横线，线宽/圆角沿用 .sidebar__section-accent 的既有取值） */
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

/* 顶栏中：当前阶段 + 进度摘要（紧凑两行，字号取 Token h3 / caption） */
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
  /* 侧栏 → 抽屉：固定 280px，默认整体左移出屏（负方向不会产生横向溢出） */
  .sidebar {
    width: $stage2-drawer-width;
    transform: translateX(-100%);
    transition: transform $up-ease-slow;
    z-index: 200;
  }

  /* 展开态：滑入 + 抽屉投影（层级 200 > 遮罩 150 > 顶栏 100，抽屉盖住顶栏左段） */
  .sidebar--open {
    transform: translateX(0);
    box-shadow: $up-shadow-lg;
  }

  /* 固定顶栏：占满宽度、高 56px，内容为主内容区上方的常驻入口 */
  .sidebar__topbar {
    display: flex;
    align-items: center;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: $stage2-topbar-height;
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
}
</style>
