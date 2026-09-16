<!--
  @Component ExcelUpload
  @Version 1.0.0
  @Description 店铺数据 Excel 上传（T2.5.2~T2.5.4）：选择 .xlsx 文件并上传，
               上传成功即完成任务（emit complete）。
-->
<template>
  <view class="excel-upload">
    <view class="excel-upload__row">
      <view class="excel-upload__pick" @tap="chooseFile">
        <text class="excel-upload__pick-text">{{ fileName || '选择 Excel 文件' }}</text>
      </view>
      <view
        class="excel-upload__btn"
        :class="{ 'excel-upload__btn--disabled': !fileName || uploading }"
        @tap="upload"
      >
        <text class="excel-upload__btn-text">{{ uploading ? '上传中...' : '上传' }}</text>
      </view>
    </view>
    <text class="excel-upload__hint">仅支持 .xlsx（.xls 请先另存为 .xlsx），单文件不超过 10MB；上传成功即完成任务</text>
    <text
      v-if="statusText"
      class="excel-upload__status"
      :class="success ? 'excel-upload__status--success' : 'excel-upload__status--error'"
    >
      {{ statusText }}
    </text>

    <!-- 导入结果（#PB-24-3）：汇总行常显；逐行问题清单仅在「有坏行/有归一」时渲染，
         避免全合法文件下出现空框。原因文案一律用后端 message（单一真源在后端 ISSUE_MESSAGES），
         前端不另造；字段名经 SHOP_METRIC_LABELS 映射为中文，未收录时回退库列名。 -->
    <view v-if="result" class="excel-upload__result">
      <text class="excel-upload__summary">{{ summaryText }}</text>
      <view v-if="issueItems.length > 0" class="excel-upload__issues">
        <view
          v-for="(item, idx) in issueItems"
          :key="item.row + '-' + item.field + '-' + idx"
          class="excel-upload__issue"
        >
          <text class="excel-upload__issue-text">{{ issueLine(item) }}</text>
        </view>
        <text v-if="result.issues_truncated" class="excel-upload__truncated">
          {{ EXCEL_ISSUES_TRUNCATED_TEXT }}
        </text>
      </view>
    </view>

    <!-- 上传中加载遮罩（转圈 + 文案） -->
    <LoadingOverlay v-if="uploading" text="上传中，请稍候..." />
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { uploadShopExcel, type ShopExcelIssue, type ShopExcelUploadResult } from '@/api/stage2';
import {
  EXCEL_ISSUES_TRUNCATED_TEXT,
  EXCEL_ISSUE_LINE_TEMPLATE,
  EXCEL_RESULT_ROW_UNIT,
  EXCEL_RESULT_SEPARATOR,
  EXCEL_RESULT_SUMMARY_LABELS,
  SHOP_METRIC_LABELS,
} from '@/constants/stage2';
import LoadingOverlay from '@/components-local/stage2/LoadingOverlay.vue';

const props = defineProps<{ type: 'trade' | 'traffic' | 'product' }>();
const emit = defineEmits<{ complete: [] }>();

const fileName = ref('');
const filePath = ref('');
const uploading = ref(false);
const statusText = ref('');
const success = ref(false);
/** 后端导入结果（#PB-24-2 契约；空 = 尚未上传成功，不渲染结果区） */
const result = ref<ShopExcelUploadResult | null>(null);

/** 问题清单（仅渲染有内容的条目；后端未回 issues 时视为空） */
const issueItems = computed<ShopExcelIssue[]>(() => result.value?.issues ?? []);

/** 汇总行：共 N 行 / 写入 X 行 / 跳过 Y 行 / 修正 Z 行（文案片段全部取自 constants/stage2.ts） */
const summaryText = computed(() => {
  const r = result.value;
  if (!r) return '';
  const L = EXCEL_RESULT_SUMMARY_LABELS;
  const unit = EXCEL_RESULT_ROW_UNIT;
  return [
    `${L.total} ${r.total_rows ?? 0} ${unit}`,
    `${L.written} ${r.count ?? 0} ${unit}`,
    `${L.skipped} ${r.skipped ?? 0} ${unit}`,
    `${L.normalized} ${r.normalized ?? 0} ${unit}`,
  ].join(EXCEL_RESULT_SEPARATOR);
});

/** 字段展示名：优先中文名（SHOP_METRIC_LABELS），未收录时回退后端下发的库列名 */
function issueFieldLabel(field: string): string {
  return SHOP_METRIC_LABELS[field] || field;
}

/** 问题条目一行：按 constants 里的模板拼装（第 <物理行号> 行 · <字段> · <后端 message>） */
function issueLine(item: ShopExcelIssue): string {
  return EXCEL_ISSUE_LINE_TEMPLATE.replace('{row}', String(item.row))
    .replace('{field}', issueFieldLabel(item.field))
    .replace('{message}', item.message || '');
}

function chooseFile() {
  // #ifdef H5
  uni.chooseFile({
    count: 1,
    extension: ['.xlsx'],
    success: (res) => {
      const path = res.tempFilePaths?.[0];
      if (path) {
        filePath.value = path;
        const tempFiles = (res as unknown as { tempFiles?: Array<{ name?: string }> }).tempFiles;
        fileName.value = tempFiles?.[0]?.name || path.split('/').pop() || '已选择文件';
        statusText.value = '';
        result.value = null;
      }
    },
    fail: () => {},
  });
  // #endif
  // #ifndef H5
  uni.chooseMessageFile({
    count: 1,
    extension: ['.xlsx'],
    success: (res) => {
      const file = res.tempFiles?.[0];
      if (file?.path) {
        filePath.value = file.path;
        fileName.value = file.name || '已选择文件';
        statusText.value = '';
      }
    },
    fail: () => {},
  });
  // #endif
}

async function upload() {
  if (!filePath.value || uploading.value) return;
  uploading.value = true;
  try {
    // 成功响应含 201（有写入）与 200（全部行皆坏、count=0）两种：都是成功，均渲染导入结果
    result.value = await uploadShopExcel(props.type, filePath.value);
    success.value = true;
    statusText.value = '上传成功';
    emit('complete');
  } catch (e) {
    success.value = false;
    statusText.value = (e as Error)?.message || '上传失败，请重试';
    result.value = null;
  } finally {
    uploading.value = false;
  }
}
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.excel-upload {
  position: relative;
  margin-top: $up-space-3;
  padding: $up-space-4;
  background-color: $u-white;
  border: 1rpx solid $u-border-color;
  border-radius: $up-radius-md;

  &__row {
    display: flex;
    gap: $up-space-3;
  }

  &__pick {
    flex: 1;
    display: flex;
    align-items: center;
    min-height: 72rpx;
    padding: $up-space-2 $up-space-3;
    background-color: $u-bg-color;
    border: 1rpx dashed $u-border-color;
    border-radius: $up-radius-sm;
  }

  &__pick-text {
    font-size: $up-font-size-body-sm;
    color: $u-content-color;
  }

  &__btn {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 128rpx;
    background-color: $u-primary;
    border-radius: $up-radius-sm;

    &--disabled {
      background-color: $u-light-color;
    }
  }

  &__btn-text {
    font-size: $up-font-size-body-sm;
    color: $u-white;
    font-weight: 500;
  }

  &__hint {
    display: block;
    margin-top: $up-space-3;
    font-size: $up-font-size-caption;
    color: $u-tips-color;
  }

  &__status {
    display: block;
    margin-top: $up-space-2;
    font-size: $up-font-size-caption;

    &--success {
      color: $u-success;
    }

    &--error {
      color: $u-error;
    }
  }

  /* 导入结果（#PB-24-3）：汇总行 +（有坏行/归一时）问题清单 */
  &__result {
    margin-top: $up-space-3;
  }

  &__summary {
    display: block;
    font-size: $up-font-size-caption;
    color: $u-content-color;
    line-height: $up-line-height-normal;
  }

  /* 清单限高 + 内部滚动：后端最多回 200 条，不限高会把卡片撑到数千像素、破坏 3 列等高布局；
     限高取 Token 组合（$up-space-12 × 5 = 240px ≈ 10~12 行），超出部分由用户滚动查看 */
  &__issues {
    margin-top: $up-space-2;
    max-height: calc(#{$up-space-12} * 5);
    overflow-y: auto;
    padding: $up-space-2;
    background-color: $u-bg-color;
    border-radius: $up-radius-sm;
  }

  &__issue {
    padding: $up-space-1 0;
  }

  /* 长数字/长内容在窄卡片内换行，不产生横向溢出 */
  &__issue-text {
    font-size: $up-font-size-caption;
    color: $u-content-color;
    line-height: $up-line-height-normal;
    overflow-wrap: anywhere;
  }

  &__truncated {
    display: block;
    margin-top: $up-space-1;
    font-size: $up-font-size-mini;
    color: $u-tips-color;
  }

}
</style>
