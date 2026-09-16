<template>
  <!-- visible 由 modelValue 计算（v-model），true 显示、false 隐藏 -->
  <view v-if="visible" class="imo-modal" @tap="close">
    <view class="imo-modal__box" @tap.stop>
      <view class="imo-modal__header">
        <text class="imo-modal__title">AI 优化主图</text>
        <view class="imo-modal__header-actions">
          <!-- 分析中可收起为小窗后台执行（请求不中断，完成后小窗变色提示） -->
          <view v-if="analyzing" class="imo-modal__mini" @tap="minimize">
            <text class="imo-modal__mini-text">后台运行</text>
          </view>
          <text class="imo-modal__close" @tap="close">×</text>
        </view>
      </view>

      <view class="imo-modal__body">
        <!-- 左侧：上传图片区 -->
        <view class="imo-modal__left">
          <view class="imo-modal__upload" @tap="chooseImage">
            <image v-if="imagePath" class="imo-modal__preview" :src="imagePath" mode="aspectFit" />
            <template v-else>
              <text class="imo-modal__upload-icon">🖼️</text>
              <text class="imo-modal__upload-text">点击上传商品主图</text>
              <text class="imo-modal__upload-hint">支持 JPG / PNG，建议 1:1 方图</text>
            </template>
          </view>
          <view v-if="imagePath" class="imo-modal__actions">
            <ActionButton type="secondary" size="small" :block="false" @click="chooseImage">重新选择</ActionButton>
            <ActionButton type="primary" size="small" :block="false" :loading="analyzing" @click="upload">
              {{ analyzing ? '分析中…' : '开始分析' }}
            </ActionButton>
          </view>
        </view>

        <!-- 右侧：AI 建议区 -->
        <view class="imo-modal__right">
          <!-- 未上传：引导提示（占位居中） -->
          <view v-if="!imagePath && !result && !error" class="imo-modal__empty">
            <EmptyState text="上传主图后生成 AI 优化建议" sub-text="左侧选择商品主图并开始分析" />
          </view>

          <!-- 分析中：LoadingOverlay（局部样式浅遮罩/圆角对齐见 .imo-modal__loading） -->
          <LoadingOverlay v-else-if="analyzing" text="AI 分析中…" class="imo-modal__loading" />

          <!-- 失败：可读错误 + 重试（占位居中） -->
          <view v-else-if="error" class="imo-modal__empty">
            <EmptyState type="error" :text="error" action-text="重试" @action="retry" />
          </view>

          <!-- 成功：结构化报告 -->
          <view v-else-if="result && !hasReportContent" class="imo-modal__empty">
            <EmptyState text="暂未生成有效建议" sub-text="请更换图片后重试" />
          </view>
          <view v-else-if="result" class="imo-modal__report">
            <view class="imo-modal__report-head">
              <text class="imo-modal__report-title">AI 优化建议</text>
              <ActionButton type="ghost" size="small" :block="false" @click="copyReport">复制全文</ActionButton>
            </view>
            <scroll-view scroll-y class="imo-modal__report-scroll">
              <!-- 问题清单（优先级等级前置：【重要/一般/可选】+ 问题描述） -->
              <view v-if="result.issues && result.issues.length" class="report-block">
                <text class="report-block__title">问题清单</text>
                <view v-for="(iss, i) in result.issues" :key="'i' + i" class="report-issue">
                  <view class="report-issue__head">
                    <!-- 等级徽章（彩色底白字，与正文明显区分）：重要=红 / 一般=橙 / 可选=蓝 -->
                    <Badge :type="priorityBadgeType(iss.priority)" :text="mapPriority(iss.priority)" />
                    <text class="report-issue__item">{{ iss.item }}</text>
                  </view>
                  <text class="report-issue__suggestion">{{ iss.suggestion }}</text>
                </view>
              </view>

              <view v-if="result.plan && (result.plan.layout || result.plan.copy || (result.plan.action_steps && result.plan.action_steps.length))" class="report-block">
                <text class="report-block__title">优化方案</text>
                <text v-if="result.plan.layout" class="report-issue__suggestion">构图：{{ result.plan.layout }}</text>
                <text v-if="result.plan.copy" class="report-issue__suggestion">文案：{{ result.plan.copy }}</text>
                <view v-if="result.plan.action_steps && result.plan.action_steps.length" class="report-steps">
                  <text class="report-block__sub">执行步骤</text>
                  <view v-for="(s, i) in result.plan.action_steps" :key="'s' + i" class="report-item">
                    <text class="report-item__num">{{ i + 1 }}</text>
                    <text class="report-item__text">{{ s }}</text>
                  </view>
                </view>
              </view>
            </scroll-view>
          </view>
        </view>
      </view>
    </view>
  </view>

  <!-- 挂起小窗：后台执行中/完成/失败提示（大弹窗收起后显示；点击恢复大弹窗查看完整报告） -->
  <view
    v-if="minimized && !visible"
    class="imo-float"
    :class="floatState.cls"
    @tap="restore"
  >
    <text class="imo-float__icon">{{ floatState.icon }}</text>
    <view class="imo-float__info">
      <text class="imo-float__title">{{ floatState.title }}</text>
      <text class="imo-float__sub">{{ floatState.sub }}</text>
    </view>
    <text class="imo-float__arrow">›</text>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { optimizeMainImage, type ImageOptimizeData } from '@/api/stage2';
import { useEscapeClose } from '@/composables/useEscapeClose';
import ActionButton from '@/components/ActionButton/index.vue';
import Badge from '@/components/Badge/index.vue';
import EmptyState from '@/components/EmptyState/index.vue';
import LoadingOverlay from '@/components-local/stage2/LoadingOverlay.vue';

/**
 * ImageOptimizeModal - 商品主图 AI 优化弹窗（方案 A）
 * @description 左侧上传商品主图（uni.chooseImage + 预览），右侧展示 AI 结构化建议
 *              （概览/合规核查/问题清单/优化方案），支持一键复制全文（uni.setClipboardData）；
 *              加载中 LoadingOverlay「AI 分析中…」，失败可读错误可重试，空结果兜底提示。
 *
 * @example
 * <ImageOptimizeModal v-model="visible" />
 */
interface Props {
  /** 是否显示弹窗（v-model） */
  modelValue: boolean;
}

const props = defineProps<Props>();
const emit = defineEmits<{ 'update:modelValue': [value: boolean] }>();

/** 弹窗可见性：由 v-model（modelValue）驱动 */
const visible = computed(() => props.modelValue);

const imagePath = ref('');
const analyzing = ref(false);
const result = ref<ImageOptimizeData | null>(null);
const error = ref('');
/** 是否处于「挂起小窗」模式：大弹窗收起、后台继续执行，完成后小窗变色提示 */
const minimized = ref(false);

/**
 * 打开弹窗时重置分析状态（保留已选图片，重新打开可继续上传/重试）
 * @description 从挂起小窗恢复查看（minimized 为 true）时**不重置**：保留 analyzing/result/error
 *              以便看到后台执行完成后的完整报告；正常新开才重置。
 */
watch(() => props.modelValue, (v) => {
  if (v) {
    const restoring = minimized.value;
    minimized.value = false;
    if (restoring) return;
    analyzing.value = false;
    result.value = null;
    error.value = '';
  }
});

/** 小窗展示内容（按后台执行状态：优化中 / 完成 / 失败） */
const floatState = computed(() => {
  if (analyzing.value) {
    return {
      cls: 'imo-float--running',
      icon: '…',
      title: 'AI 建议输出中',
      sub: '后台执行中，可继续操作其它任务',
    };
  }
  if (error.value) {
    return {
      cls: 'imo-float--fail',
      icon: '×',
      title: '优化失败',
      sub: '点击查看失败原因并重试',
    };
  }
  return {
    cls: 'imo-float--done',
    icon: '✓',
    title: '优化完成',
    sub: '点击查看 AI 优化建议',
  };
});

/** 收起为小窗（后台运行）：关闭大弹窗并保留执行状态，完成后小窗变色提示 */
function minimize() {
  minimized.value = true;
  emit('update:modelValue', false);
}

/** 点击小窗：恢复大弹窗查看（watch 分支不重置状态） */
function restore() {
  emit('update:modelValue', true);
}

/** 选择商品主图（uni.chooseImage，H5 返回临时路径可预览/上传） */
function chooseImage() {
  uni.chooseImage({
    count: 1,
    sizeType: ['compressed'],
    success: (res) => {
      const path = res.tempFilePaths?.[0];
      if (path) {
        imagePath.value = path;
        error.value = '';
      }
    },
    fail: () => {},
  });
}

/** 上传并触发 AI 优化分析 */
async function upload() {
  if (!imagePath.value || analyzing.value) return;
  analyzing.value = true;
  error.value = '';
  result.value = null;
  try {
    result.value = await optimizeMainImage(imagePath.value);
  } catch (e) {
    error.value = (e as Error)?.message || 'AI 分析失败，请重试';
  } finally {
    analyzing.value = false;
  }
}

function retry() {
  upload();
}

/** 是否有结构化报告内容（空结果兜底判断；仅问题清单 + 优化方案） */
const hasReportContent = computed(() => {
  if (!result.value) return false;
  const r = result.value;
  return !!((r.issues && r.issues.length) || (r.plan && (r.plan.layout || r.plan.copy || (r.plan.action_steps && r.plan.action_steps.length))));
});

/** 优先级 → 中文等级（后端新值为「重要/一般/可选」，兼容旧值 P0/P1/P2 容错映射） */
function mapPriority(p: string): string {
  if (p === '重要' || p === 'P0') return '重要';
  if (p === '可选' || p === 'P2') return '可选';
  return '一般'; // '一般' / 'P1' / 未知均按一般
}

/** 优先级 → Badge 语义色：重要=error 红 / 一般=warning 橙 / 可选=info 蓝（§3.4 Tag 语义 Token） */
function priorityBadgeType(p: string): 'error' | 'warning' | 'info' {
  if (p === '重要' || p === 'P0') return 'error';
  if (p === '可选' || p === 'P2') return 'info';
  return 'warning';
}

/** 结构化报告 → 纯文本（复制全文用；仅问题清单 + 优化方案，等级前置） */
function formatReportText(data: ImageOptimizeData): string {
  const lines: string[] = [];
  if (data.issues && data.issues.length) {
    lines.push('【问题清单】');
    data.issues.forEach((iss) => lines.push('【' + mapPriority(iss.priority) + '】' + iss.item + '：' + iss.suggestion));
  }
  if (data.plan) {
    lines.push('【优化方案】');
    if (data.plan.layout) lines.push('构图：' + data.plan.layout);
    if (data.plan.copy) lines.push('文案：' + data.plan.copy);
    if (data.plan.action_steps && data.plan.action_steps.length) {
      data.plan.action_steps.forEach((s, i) => lines.push((i + 1) + '. ' + s));
    }
  }
  return lines.join('\n');
}

/** 一键复制全文（uni.setClipboardData） */
function copyReport() {
  if (!result.value) return;
  const text = formatReportText(result.value);
  uni.setClipboardData({
    data: text,
    success: () => uni.showToast({ title: '已复制到剪贴板', icon: 'none' }),
    fail: () => uni.showToast({ title: '复制失败，请重试', icon: 'none' }),
  });
}

function close() {
  // 分析进行中关闭（×/遮罩/ESC/后台运行共用路径）：转小窗后台执行，不丢请求与结果
  if (analyzing.value && imagePath.value) {
    minimize();
    return;
  }
  minimized.value = false;
  emit('update:modelValue', false);
}

// ESC 键关闭（复用 useEscapeClose：仅弹窗可见时生效，卸载自动移除监听）
useEscapeClose(() => visible.value, close);
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.imo-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: $up-space-6;
  background-color: $u-overlay;

  /* 弹窗：接近全屏最大化（建议区展示空间充足）；模态框阴影 §3.9 $up-shadow-xl。
     宽度 96% 相对容器（100vw - padding），自动避开溢出；
     高度固定 94vh：上传前/上传后/分析中/完成各状态弹窗尺寸完全一致，不随内容收缩变矮；
     内部 body flex:1 + 左右区各自填满（右建议区 scroll 拉满可滚动） */
  &__box {
    width: 96%;
    height: 94vh;
    display: flex;
    flex-direction: column;
    background-color: $u-white;
    border-radius: $up-radius-lg;
    box-shadow: $up-shadow-xl;
    overflow: hidden;
  }

  &__header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: $up-space-4 $up-space-5;
    border-bottom: 1rpx solid $u-border-color;
  }

  &__title {
    font-size: $up-font-size-h3;
    font-weight: 600;
    color: $u-main-color;
  }

  &__close {
    font-size: $up-font-size-h2;
    color: $u-tips-color;
    line-height: 1;
    padding: $up-space-2;
  }

  &__header-actions {
    display: flex;
    align-items: center;
    gap: $up-space-2;
  }

  /* 「后台运行」胶囊按钮（仅分析中显示；挂起后请求不中断） */
  &__mini {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 4rpx $up-space-3;
    background-color: $u-primary-light;
    border: 1rpx solid $u-tag-primary-border;
    border-radius: $up-radius-full;
    cursor: pointer;
    transition: background-color $up-ease-fast;

    &:active {
      background-color: $u-primary;
    }
  }

  &__mini-text {
    font-size: $up-font-size-mini;
    font-weight: 500;
    color: $u-primary-dark;

    .imo-modal__mini:active & {
      color: $u-white;
    }
  }

  /* 两栏：左上传 + 右建议（桌面 flex row；窄屏降 column） */
  &__body {
    display: flex;
    flex: 1;
    min-height: 0;
  }

  &__left {
    width: min(30%, 420px);
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    padding: $up-space-5;
    border-right: 1rpx solid $u-border-color;
  }

  &__upload {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: $up-space-2;
    padding: $up-space-4;
    background-color: $u-bg-color;
    border: 2rpx dashed $u-border-color;
    border-radius: $up-radius-md;
    transition: border-color $up-ease-normal, background-color $up-ease-normal;

    &:active {
      border-color: $u-primary;
      background-color: $u-primary-light;
    }
  }

  &__preview {
    width: 100%;
    height: 100%;
    border-radius: $up-radius-sm;
  }

  &__upload-icon {
    font-size: $up-font-size-h1;
  }

  &__upload-text {
    font-size: $up-font-size-body-sm;
    color: $u-content-color;
    font-weight: 500;
  }

  &__upload-hint {
    font-size: $up-font-size-caption;
    color: $u-tips-color;
  }

  &__actions {
    display: flex;
    justify-content: space-between;
    gap: $up-space-3;
    margin-top: $up-space-4;
  }

  &__right {
    flex: 1;
    min-width: 0;
    position: relative;
    display: flex;
    flex-direction: column;
    padding: $up-space-5;
  }

  /* 占位容器（未上传/失败/空结果）：建议区垂直+水平居中 */
  &__empty {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  /* 建议区内 LoadingOverlay 局部调整（不影响其他页面使用）：
     浅遮罩（白 82% 半透明）+ 圆角与弹窗一致（$up-radius-lg），spinner/文字适配浅底清晰可见 */
  .imo-modal__loading {
    background-color: rgba($u-white, 0.82);
    border-radius: $up-radius-lg;

    :deep(.loading-overlay__spinner) {
      border-color: $u-border-color;
      border-top-color: $u-primary;
    }

    :deep(.loading-overlay__text) {
      color: $u-content-color;
    }
  }

  /* 结构化报告 */
  &__report {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  &__report-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: $up-space-3;
  }

  &__report-title {
    font-size: $up-font-size-body;
    font-weight: 600;
    color: $u-main-color;
  }

  &__report-scroll {
    flex: 1;
    min-height: 0;
  }
}

/* 报告区块（作用域类）：文字清晰可读、不拥挤（正文 14px 行高 1.8，段落间距 $up-space-4） */
.report-block {
  margin-bottom: $up-space-4;

  &__title {
    display: block;
    font-size: $up-font-size-body;
    font-weight: 600;
    color: $u-main-color;
    margin-bottom: $up-space-2;
  }

  &__sub {
    display: block;
    font-size: $up-font-size-caption;
    color: $u-tips-color;
    margin: $up-space-3 0 $up-space-2;
  }

  &__text {
    font-size: $up-font-size-body;
    color: $u-content-color;
    line-height: 1.8;
  }
}

.report-item {
  display: flex;
  align-items: flex-start;
  gap: $up-space-2;
  margin-bottom: $up-space-2;

  &__mark {
    flex-shrink: 0;
    color: $u-success;
    font-weight: 600;
  }

  &__num {
    flex-shrink: 0;
    width: 32rpx;
    height: 32rpx;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: $up-font-size-mini;
    color: $u-white;
    background-color: $u-primary;
    border-radius: $up-radius-full;
    font-weight: 500;
  }

  &__text {
    flex: 1;
    min-width: 0;
    font-size: $up-font-size-body-sm;
    color: $u-content-color;
    line-height: 1.7;
  }
}

/* 问题项：等级徽章（彩色底白字）+ 问题描述同行前置，建议紧凑排版尽量一屏 */
.report-issue {
  padding: $up-space-2 $up-space-3;
  margin-bottom: $up-space-2;
  background-color: $u-bg-color;
  border: 1rpx solid $u-border-color;
  border-radius: $up-radius-sm;

  &__head {
    display: flex;
    align-items: center;
    gap: $up-space-2;
  }

  &__item {
    flex: 1;
    min-width: 0;
    font-size: $up-font-size-body-sm;
    font-weight: 600;
    color: $u-main-color;
    line-height: 1.5;
  }

  &__suggestion {
    display: block;
    margin-top: $up-space-1;
    font-size: $up-font-size-caption;
    color: $u-content-color;
    line-height: 1.6;
  }
}

/* 窄视口（<768px）：两栏降一栏，左上传区固定高度 */
@media (max-width: 768px) {
  .imo-modal__body {
    flex-direction: column;
    overflow-y: auto;
  }

  .imo-modal__left {
    width: 100%;
    border-right: none;
    border-bottom: 1rpx solid $u-border-color;
  }

  .imo-modal__upload {
    min-height: 320rpx;
  }
}

/* ---------- 挂起小窗（后台执行提示条；Token 化，三态：优化中/完成/失败） ---------- */
.imo-float {
  position: fixed;
  right: $up-space-6;
  bottom: $up-space-8;
  z-index: 999;
  display: flex;
  align-items: center;
  gap: $up-space-3;
  min-width: 320rpx;
  max-width: 520rpx;
  padding: $up-space-3 $up-space-4;
  background-color: $u-white;
  border: 2rpx solid $u-border-color;
  border-radius: $up-radius-lg;
  box-shadow: $up-shadow-lg;
  cursor: pointer;
  transition: border-color $up-ease-normal, background-color $up-ease-normal, box-shadow $up-ease-normal;

  &:hover {
    box-shadow: $up-shadow-xl;
  }

  /* 运行中：主色描边 */
  &--running {
    border-color: $u-primary;
    background-color: $u-white;

    .imo-float__icon {
      color: $u-primary;
    }

    .imo-float__title {
      color: $u-primary-dark;
    }
  }

  /* 完成：浅绿底 + 成功绿描边（变亮提示成功） */
  &--done {
    border-color: $u-success;
    background-color: $u-success-light;
    box-shadow: $up-shadow-btn;

    .imo-float__icon {
      color: $u-success-dark;
    }

    .imo-float__title {
      color: $u-success-dark;
    }
  }

  /* 失败：浅红底 + 错误红描边 */
  &--fail {
    border-color: $u-error;
    background-color: $u-error-light;

    .imo-float__icon {
      color: $u-error;
    }

    .imo-float__title {
      color: $u-error-dark;
    }
  }

  &__icon {
    font-size: $up-font-size-h3;
    font-weight: 700;
    line-height: 1;
  }

  &__info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2rpx;
  }

  &__title {
    font-size: $up-font-size-body-sm;
    font-weight: 600;
    color: $u-main-color;
  }

  &__sub {
    font-size: $up-font-size-mini;
    color: $u-tips-color;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  &__arrow {
    font-size: $up-font-size-h3;
    color: $u-tips-color;
  }
}
</style>