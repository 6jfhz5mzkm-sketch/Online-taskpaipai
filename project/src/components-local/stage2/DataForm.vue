<!--
  @Component DataForm
  @Version 1.0.0
  @Description 店铺数据表单（T2.5.1 / T2.5.5 / T2.5.6）：按字段 schema 渲染、校验并提交，
               提交成功即完成任务（emit complete）。
-->
<template>
  <view class="data-form">
    <view v-for="field in fields" :key="field.key" class="data-form__field">
      <text class="data-form__label">
        {{ field.label }}<text v-if="field.required" class="data-form__required"> *</text>
      </text>
      <view class="data-form__control">
        <input
          v-model="values[field.key]"
          class="data-form__input"
          :type="field.integer ? 'number' : 'digit'"
          :placeholder="field.placeholder || '请输入'"
        />
        <text v-if="errors[field.key]" class="data-form__error">{{ errors[field.key] }}</text>
      </view>
    </view>

    <view class="data-form__actions">
      <view
        class="data-form__btn"
        :class="{ 'data-form__btn--disabled': submitting }"
        @tap="submit"
      >
        <text class="data-form__btn-text">{{ submitting ? '提交中...' : '提交' }}</text>
      </view>
    </view>

    <text
      v-if="statusText"
      class="data-form__status"
      :class="success ? 'data-form__status--success' : 'data-form__status--error'"
    >
      {{ statusText }}
    </text>
  </view>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue';
import { STAGE2_FORM_SCHEMAS } from '@/constants/stage2';
import {
  validateShopStar,
  validateProductCount,
  validateHealthScore,
  todayDateString,
} from '@/utils/stage2';
import {
  saveShopStarData,
  saveProductCountData,
  saveHealthScoreData,
} from '@/api/stage2';

const props = defineProps<{ formKey: string }>();
const emit = defineEmits<{ complete: [] }>();

const fields = computed(() => STAGE2_FORM_SCHEMAS[props.formKey] || []);
const values = reactive<Record<string, string>>({});
const errors = reactive<Record<string, string>>({});
const submitting = ref(false);
const statusText = ref('');
const success = ref(false);

/* 分发键 = 后端 actionType/actionParam 原值（#FE-29：由 data_form + actionParam 下发，
   对应 constants/stage2.ts 的 STAGE2_FORM_SCHEMAS 键，不再使用历史 'form:xxx' 拼接串） */
const VALIDATORS: Record<string, (v: Record<string, unknown>) => Record<string, string>> = {
  star: validateShopStar,
  'product-count': validateProductCount,
  'health-score': validateHealthScore,
};

const SUBMITTERS: Record<string, (v: Record<string, unknown>) => Promise<unknown>> = {
  star: saveShopStarData as (v: Record<string, unknown>) => Promise<unknown>,
  'product-count': saveProductCountData as (v: Record<string, unknown>) => Promise<unknown>,
  'health-score': saveHealthScoreData as (v: Record<string, unknown>) => Promise<unknown>,
};

async function submit() {
  for (const key of Object.keys(errors)) delete errors[key];

  const payload: Record<string, unknown> = {};
  for (const field of fields.value) {
    const raw = values[field.key];
    const empty = raw === undefined || raw === '';
    /* 留空：默认不提交该字段；schema 声明 emptyAsZero 的字段（健康分）以 0 提交
       （#F-29 与后端约定：空 = 0，全 0 = 无该项数据，由分析侧跳过） */
    payload[field.key] = empty ? (field.emptyAsZero ? 0 : undefined) : Number(raw);
  }
  payload.dataDate = todayDateString();

  const validator = VALIDATORS[props.formKey];
  const errs = validator ? validator(payload) : {};
  for (const key of Object.keys(errs)) errors[key] = errs[key];
  if (Object.keys(errors).length > 0) return;

  const submitter = SUBMITTERS[props.formKey];
  if (!submitter) return;

  submitting.value = true;
  try {
    await submitter(payload);
    success.value = true;
    statusText.value = '提交成功';
    emit('complete');
  } catch (e) {
    success.value = false;
    statusText.value = (e as Error)?.message || '提交失败，请重试';
  } finally {
    submitting.value = false;
  }
}
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.data-form {
  margin-top: $up-space-3;
  /* 左右 padding 收窄（$up-space-2）为 3 列卡片内 label 单行完整腾出空间 */
  padding: $up-space-3 $up-space-2;
  background-color: $u-white;
  border: 1rpx solid $u-border-color;
  border-radius: $up-radius-md;

  /* 字段同行布局：label 左侧单行完整（nowrap 不换行不截断），输入框右侧（与提交按钮右对齐） */
  &__field {
    display: flex;
    align-items: center;
    margin-bottom: $up-space-3;
  }

  &__label {
    /* 强制单行：nowrap 禁止换行、无 ellipsis 截断；flex:0 0 auto 按内容宽固定（不收缩挤压）；
       字号 12px（caption）+ 表单左右 padding 8px + margin 8px 组合，保证 1280px 起桌面 100% 缩放
       下最长 label（如「客服咨询因子得分（5.5-10）」≈178px）+ input 72px 单行放得下；
       padding-left 4px 让文字不贴卡片边缘；line-height 1 使文字 box 紧凑、与输入框垂直居中对齐
       （field 已 align-items:center，按 box 中线对齐） */
    flex: 0 0 auto;
    white-space: nowrap;
    padding-left: $up-space-1;
    margin-right: $up-space-2;
    font-size: $up-font-size-caption;
    color: $u-content-color;
    line-height: 1;
  }

  &__required {
    color: $u-error;
  }

  /* 输入控制区：随 input 定宽（不占满整行），margin-left:auto 推到行右侧，
     右边缘与右下角提交按钮（flex-end）右对齐；错误提示在 input 下方 */
  &__control {
    flex: 0 1 auto;
    min-width: 0;
    margin-left: auto;
  }

  &__input {
    /* 限宽：固定 72px ≈ 4-6 个数字字符（跨端一致；rpx 在桌面封顶会放大到 200rpx≈256px，
       挤占 3 列卡片内 label 单行空间，故改用 px 定宽）；max-width:100% 防极窄容器溢出；
       min-height:56rpx 与侧边栏按钮高度协调，纵向更紧凑 */
    width: 72px;
    max-width: 100%;
    min-height: 56rpx;
    padding: $up-space-1 $up-space-3;
    background-color: $u-bg-color;
    border: 1rpx solid $u-border-color;
    border-radius: $up-radius-sm;
    font-size: $up-font-size-body-sm;
    color: $u-main-color;
  }

  &__error {
    display: block;
    margin-top: $up-space-1;
    font-size: $up-font-size-caption;
    color: $u-error;
  }

  &__actions {
    display: flex;
    justify-content: flex-end;
  }

  &__btn {
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 160rpx;
    padding: $up-space-3 $up-space-5;
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

  &__status {
    display: block;
    margin-top: $up-space-3;
    font-size: $up-font-size-caption;

    &--success {
      color: $u-success;
    }

    &--error {
      color: $u-error;
    }
  }
}

/* 窄视口（<600px，与 upload.vue 降列断点一致）：label 换行到输入框上方，取消单行 nowrap 定宽，
   避免「label 单行宽（≈156px）+ input 72px」把卡片与页面撑出横向溢出（D1） */
@media (max-width: 600px) {
  .data-form__field {
    flex-wrap: wrap;
  }

  .data-form__label {
    flex: 1 1 100%;
    white-space: normal;
    margin-bottom: $up-space-1;
  }
}
</style>
