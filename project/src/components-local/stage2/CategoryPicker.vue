<!--
  @Component CategoryPicker
  @Version 1.2.0
  @Description 阶段二「经营类目」选择与保存弹窗（自 components-local/task-center/CategoryPicker.vue 迁移而来；
               阶段一旧面板与其用法由后续清理承接，两处不得长期并存）。
               结构（自上而下）：① 商家登记信息输入区（京麦商家ID / 店铺名称，**本弹窗是 PUT/GET
               /api/merchant/registration 的唯一宿主**——原「商家信息登记」弹窗已随 #F-26-R2 删除）→
               ② 一级类目 dropdown（单选）→ ③ 二级类目 dropdown（多选 1-3、唯一主类目）→
               ④ 已选清单（指定主类目 / 移除）→ 保存。
               #F-26：两级触发器前置图标（一级=店铺线描图标、二级=列表图标）+ chevron 展开指示，
               图标造型/颜色见 @/styles/mixins/_icons.scss（唯一真源，内联 SVG，不引静态资源）；
               #F-26-R1：输入区改用 min-height + 垂直内边距 + 显式 line-height 承载文本行，
               修掉 uni H5 内部 input height:100% 造成的内容框小于行框、汉字上下被裁。
               两个层级的 dropdown 共用同一实现 src/components/CategorySelectDropdown/index.vue（开发规则 §四：
               同一形式 ≥2 次必须封装），层级沿用 #F-23 实测结论（面板 z-index 10001 > 遮罩 10000 >
               共享 Modal .modal-overlay 9999），与 <Modal> 同级渲染以免被弹窗层级/裁剪影响。
  @Props visible: 弹窗可见性（v-model:visible）
  @Emits update:visible（关闭）/ saved（保存成功）/ skip（点击跳过：仅关闭，不写库）
  @See project/docs/后端技术方案.md §5.2 API-05 / API-07；api-py/app/api/v1/merchant.py:41/:75（商家登记）
-->
<template>
  <view class="category-picker-root">
  <Modal :visible="visible" :title="CATEGORY_PICKER_TITLE" width="1040rpx" @update:visible="handleVisibleChange">
    <view class="category-picker">
      <!-- ① 商家登记信息（弹窗最上方；与「商家信息登记」弹窗共用接口与数据，仅提交 dirty 字段） -->
      <view class="category-picker__field">
        <text class="category-picker__label">{{ JD_MERCHANT_ID_LABEL }}</text>
        <input
          ref="jdMerchantIdInputRef"
          class="category-picker__input"
          :value="jdMerchantId"
          :placeholder="JD_MERCHANT_ID_PLACEHOLDER"
          placeholder-class="category-picker__placeholder"
          :maxlength="JD_MERCHANT_ID_MAX_LENGTH"
          @input="onJdMerchantIdInput"
        />
      </view>

      <view class="category-picker__field">
        <text class="category-picker__label">{{ SHOP_NAME_LABEL }}</text>
        <input
          ref="shopNameInputRef"
          class="category-picker__input"
          :value="shopName"
          :placeholder="SHOP_NAME_PLACEHOLDER"
          placeholder-class="category-picker__placeholder"
          :maxlength="SHOP_NAME_MAX_LENGTH"
          @input="onShopNameInput"
        />
      </view>

      <!-- ② 一级类目（parent_id=0）：dropdown 单选 -->
      <view
        ref="topFieldRef"
        class="category-picker__picker"
        :class="{ 'category-picker__picker--filled': !!selectedTopCategoryName }"
        @tap="toggleTopDropdown"
      >
        <view class="category-picker__picker-icon category-picker__picker-icon--shop" />
        <text class="category-picker__picker-text">{{ selectedTopCategoryName || (loadingTop ? '加载中...' : CATEGORY_TOP_PLACEHOLDER) }}</text>
        <view class="category-picker__chevron" :class="{ 'category-picker__chevron--open': topDropdownOpen }" />
      </view>

      <!-- ③ 二级类目（parent_id<>0）：dropdown 多选（1-3，与一级同一套 dropdown 实现） -->
      <view
        v-if="selectedTopCategoryId"
        ref="subFieldRef"
        class="category-picker__picker"
        :class="{ 'category-picker__picker--filled': selected.length > 0 }"
        @tap="toggleSubDropdown"
      >
        <view class="category-picker__picker-icon category-picker__picker-icon--list" />
        <text class="category-picker__picker-text">{{ subSelectionLabel || (loadingSub ? '加载中...' : CATEGORY_SUB_PLACEHOLDER) }}</text>
        <view class="category-picker__chevron" :class="{ 'category-picker__chevron--open': subDropdownOpen }" />
      </view>

      <!-- ④ 已选清单：唯一主类目用单选结构，天然不可能出现两个 true -->
      <view v-if="selected.length > 0" class="category-picker__selected">
        <view v-for="item in selected" :key="item.categoryId" class="category-picker__selected-item">
          <view class="category-picker__selected-main">
            <text class="category-picker__selected-name">{{ item.name }}</text>
            <view class="category-picker__primary" @tap="setPrimary(item.categoryId)">
              <view class="category-picker__radio" :class="{ 'category-picker__radio--checked': item.isPrimary }" />
              <text class="category-picker__primary-text">主类目</text>
            </view>
          </view>
          <text class="category-picker__remove" @tap="removeCategory(item.categoryId)">移除</text>
        </view>
      </view>
    </view>

    <!-- 弹窗文案与按钮文案统一取 src/constants/category.ts（§8.1 第 1 条） -->
    <view class="category-picker__meta">
      <text class="category-picker__intro">{{ CATEGORY_DIALOG_INTRO }}</text>
      <text class="category-picker__hint">{{ CATEGORY_DIALOG_HINT }}</text>
      <text class="category-picker__count">已选 {{ selected.length }}/{{ MAX_SELECTED }}</text>
    </view>

    <view class="category-picker__actions">
      <view class="category-picker__btn category-picker__btn--secondary" @tap="handleSkip">
        <text class="category-picker__btn-text category-picker__btn-text--secondary">{{ CATEGORY_SKIP_TEXT }}</text>
      </view>
      <view
        class="category-picker__btn category-picker__btn--primary"
        :class="{ 'category-picker__btn--disabled': saving }"
        @tap="handleSave"
      >
        <text class="category-picker__btn-text">{{ saving ? CATEGORY_SAVING_TEXT : CATEGORY_SAVE_TEXT }}</text>
      </view>
    </view>
  </Modal>

  <!-- 两个层级的 dropdown 浮层：同一套实现、均与 <Modal> 同级；层级高于弹窗遮罩，且切换层级时相互收起 -->
  <CategorySelectDropdown
    :visible="topDropdownOpen"
    :options="topCategories"
    :selected-ids="topSelectedIds"
    :anchor="topAnchor"
    @close="closeTopDropdown"
    @pick="onPickTop"
  />
  <CategorySelectDropdown
    :visible="subDropdownOpen"
    :options="subCategories"
    :selected-ids="subSelectedIds"
    multiple
    :max-count="MAX_SELECTED"
    :anchor="subAnchor"
    @close="closeSubDropdown"
    @pick="onPickSub"
  />
  </view>
</template>

<script setup lang="ts">
/**
 * CategoryPicker 组件（阶段二经营类目选择与保存弹窗）
 * @description 候选类目来自 API-05；已保存类目回显与保存走 API-07；商家登记信息走 /api/merchant/registration
 *              （统一经 src/api/*，组件内不直接发起请求）。数量校验（1-3）、主类目唯一性与登记字段格式
 *              在前端做前置拦截（实时过滤 + 保存前再校验），错误文案复用真源/常量，不新造。
 */
import { ref, computed, watch } from 'vue';
import Modal from '@/components/Modal/index.vue';
import CategorySelectDropdown from '@/components/CategorySelectDropdown/index.vue';
import {
  CATEGORY_COUNT_ERROR_TEXT,
  CATEGORY_DIALOG_HINT,
  CATEGORY_DIALOG_INTRO,
  CATEGORY_PICKER_TITLE,
  CATEGORY_SAVE_TEXT,
  CATEGORY_SAVING_TEXT,
  CATEGORY_SKIP_TEXT,
  CATEGORY_SUB_PLACEHOLDER,
  CATEGORY_TOP_PLACEHOLDER,
} from '@/constants/category';
import {
  JD_MERCHANT_ID_INVALID_TEXT,
  JD_MERCHANT_ID_LABEL,
  JD_MERCHANT_ID_MAX_LENGTH,
  JD_MERCHANT_ID_PLACEHOLDER,
  SHOP_NAME_INVALID_TEXT,
  SHOP_NAME_LABEL,
  SHOP_NAME_MAX_LENGTH,
  SHOP_NAME_PLACEHOLDER,
} from '@/constants/merchant';
import { fetchMerchantRegistration, saveMerchantRegistration, type MerchantRegistration } from '@/api/merchant';
import {
  fetchCategoryList,
  fetchMerchantCategories,
  saveMerchantCategories,
  type CategoryNode,
  type MerchantCategoryItem,
  type SavedMerchantCategory,
} from '@/api/category';
import { filterChineseOnly, filterDigitsOnly, isValidJdMerchantId, isValidShopName } from '@/utils/validate';

interface Props {
  /** 弹窗可见性（v-model:visible） */
  visible: boolean;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  'update:visible': [value: boolean];
  /** 保存成功（宿主据此停止「首次进入自动弹窗」判定） */
  saved: [];
  /** 点击跳过：仅关闭弹窗，不写库、不报错、不写永久标记 */
  skip: [];
}>();

/** 保存成功反馈（真源：project/docs/后端技术方案.md §5.2 API-07「成功文案」行——该行即此文案的唯一真源） */
const SAVE_SUCCESS_TEXT = '经营类目已保存';

/** 数量上界/下界（与 API-07 参数校验一致） */
const MAX_SELECTED = 3;
const MIN_SELECTED = 1;

/** 已选经营类目 */
interface SelectedCategory {
  categoryId: string;
  name: string;
  isPrimary: boolean;
}

/* ---------- 商家登记信息（京麦商家ID / 店铺名称；与「商家信息登记」弹窗同一份数据） ---------- */

const jdMerchantId = ref('');
const shopName = ref('');
/** 打开弹窗时的初始值：用于「仅提交 dirty 字段」的差异判断 */
const initialJdMerchantId = ref('');
const initialShopName = ref('');
const jdMerchantIdInputRef = ref<unknown>(null);
const shopNameInputRef = ref<unknown>(null);

/* ---------- 类目 ---------- */

const topCategories = ref<CategoryNode[]>([]);
const subCategories = ref<CategoryNode[]>([]);
const selectedTopCategoryId = ref('');
const selected = ref<SelectedCategory[]>([]);
const loadingTop = ref(false);
const loadingSub = ref(false);
const saving = ref(false);

/** 两个层级的 dropdown 展开状态与锚点（两处共用同一套 dropdown 组件，仅 props 不同） */
const topDropdownOpen = ref(false);
const subDropdownOpen = ref(false);
const topAnchor = ref<{ left: number; top: number; width: number } | null>(null);
const subAnchor = ref<{ left: number; top: number; width: number } | null>(null);
const topFieldRef = ref<unknown>(null);
const subFieldRef = ref<unknown>(null);

/** 一级选中项 id（单选）；二级选中项 id（多选） */
const topSelectedIds = computed<string[]>(() => (selectedTopCategoryId.value ? [selectedTopCategoryId.value] : []));
const subSelectedIds = computed<string[]>(() => selected.value.map((item) => item.categoryId));

const selectedTopCategoryName = computed(() => {
  const hit = topCategories.value.find((item) => String(item.id) === selectedTopCategoryId.value);
  return hit ? hit.name : '';
});

/** 二级选择器摘要：已选名称（多选，未选则空串以展示占位） */
const subSelectionLabel = computed(() => selected.value.map((item) => item.name).join('、'));

/** 数量越界前置提示（真源文案，不发请求） */
function notifyCategoryCountError(): void {
  uni.showToast({ title: CATEGORY_COUNT_ERROR_TEXT, icon: 'none' });
}

/* ---------- dropdown 锚点实测（H5 用 ref 取真实 DOM；非 H5 回退 uni 选择器查询） ---------- */

/** uni-view ref 解出真实 DOM（H5 下 view 编译为节点；兼容 $el 包装） */
function resolveEl(refValue: unknown): HTMLElement | null {
  const v = refValue as { $el?: unknown } | HTMLElement | null;
  return ((v && (v as { $el?: HTMLElement }).$el) || (v as HTMLElement | null)) || null;
}

function measureAnchor(refValue: unknown, selector: string, target: { value: { left: number; top: number; width: number } | null }): void {
  const el = resolveEl(refValue);
  if (el && typeof el.getBoundingClientRect === 'function') {
    const box = el.getBoundingClientRect();
    target.value = { left: box.left, top: box.bottom, width: box.width };
    return;
  }
  uni
    .createSelectorQuery()
    .select(selector)
    .boundingClientRect((rect) => {
      const box = rect as { left: number; bottom: number; width: number } | null;
      if (box) target.value = { left: box.left, top: box.bottom, width: box.width };
    })
    .exec();
}

/** 收起一级浮层 */
function closeTopDropdown(): void {
  topDropdownOpen.value = false;
}

/** 收起二级浮层 */
function closeSubDropdown(): void {
  subDropdownOpen.value = false;
}

/** 开合一级浮层（与二级互斥：打开时收起另一个） */
function toggleTopDropdown(): void {
  if (topDropdownOpen.value) {
    closeTopDropdown();
    return;
  }
  closeSubDropdown();
  measureAnchor(topFieldRef.value, '.category-picker__picker', topAnchor);
  topDropdownOpen.value = true;
}

/** 开合二级浮层（与一级互斥） */
function toggleSubDropdown(): void {
  if (subDropdownOpen.value) {
    closeSubDropdown();
    return;
  }
  closeTopDropdown();
  measureAnchor(subFieldRef.value, '.category-picker__sub-picker', subAnchor);
  subDropdownOpen.value = true;
}

/** 一级选中（单选）：重置候选与已选（已选类目不属于新一级类目时不应保留）并收起浮层 */
function onPickTop(id: string): void {
  const hit = topCategories.value.find((item) => String(item.id) === id);
  if (!hit) return;
  selectedTopCategoryId.value = id;
  subCategories.value = [];
  selected.value = [];
  closeTopDropdown();
  void loadSubCategories(id);
}

/** 二级勾选（多选 1-3，唯一主类目由已选清单维护）：已选则移除；未选且达上界则按真源文案拒绝 */
function onPickSub(id: string): void {
  const hit = subCategories.value.find((item) => String(item.id) === id);
  if (!hit) return;
  if (isSelected(id)) {
    removeCategory(id);
    return;
  }
  if (selected.value.length >= MAX_SELECTED) {
    notifyCategoryCountError();
    return;
  }
  addCategory(hit);
}

/* ---------- 类目数据 ---------- */

/** 类目是否已选（id 统一按字符串比较，避免后端 int/string 形态差异） */
function isSelected(categoryId: unknown): boolean {
  return selected.value.some((item) => item.categoryId === String(categoryId));
}

/** 加载一级类目（API-05，不传 parent_id） */
async function loadTopCategories(): Promise<void> {
  loadingTop.value = true;
  try {
    topCategories.value = await fetchCategoryList();
  } catch (err) {
    // request 封装已按失败原因 toast，此处仅记录，避免重复提示
    console.warn('[经营类目] 一级类目加载失败', err);
  } finally {
    loadingTop.value = false;
  }
}

/** 加载某一级下的二级类目（API-05，带 parent_id） */
async function loadSubCategories(parentId: string): Promise<void> {
  loadingSub.value = true;
  try {
    subCategories.value = await fetchCategoryList(Number(parentId));
  } catch (err) {
    console.warn('[经营类目] 二级类目加载失败', err);
  } finally {
    loadingSub.value = false;
  }
}

/** 已保存类目在当前 API-05 列表中不存在（被停用/删除）时的降级名称 */
function missingCategoryLabel(categoryId: string): string {
  return `类目已下架(#${categoryId})`;
}

/**
 * 回显已保存经营类目（API-07 查询侧）
 * @description 查询侧只返回 { category_id, is_primary }，不含名称（名称唯一真源是 category 表，
 *              经 API-05 获取）。故用 API-05 逐个一级取二级建立 id → { 名称, 父类目 } 索引，
 *              命中全部已保存 id 即提前结束，避免无谓请求；未命中的项按降级文案展示并允许移除。
 */
async function restoreSavedCategories(): Promise<void> {
  let saved: SavedMerchantCategory[] = [];
  try {
    saved = await fetchMerchantCategories();
  } catch (err) {
    console.warn('[经营类目] 已保存类目查询失败', err);
    return;
  }
  if (!saved || saved.length === 0) return;

  const savedIds = saved.map((item) => String(item.category_id));
  const nameById = new Map<string, string>();
  const parentById = new Map<string, string>();
  const subCategoriesByParent = new Map<string, CategoryNode[]>();

  for (const top of topCategories.value) {
    if (savedIds.every((id) => nameById.has(id))) break;
    const parentId = String(top.id);
    try {
      const subs = await fetchCategoryList(Number(parentId));
      subCategoriesByParent.set(parentId, subs);
      for (const sub of subs) {
        nameById.set(String(sub.id), sub.name);
        parentById.set(String(sub.id), parentId);
      }
    } catch (err) {
      console.warn('[经营类目] 已保存类目名称解析失败', parentId, err);
    }
  }

  // 后端按 is_primary DESC, category_id ASC 排序，此处保持该顺序，主类目仍在首位
  selected.value = saved.map((item) => {
    const categoryId = String(item.category_id);
    return {
      categoryId,
      name: nameById.get(categoryId) || missingCategoryLabel(categoryId),
      isPrimary: !!item.is_primary,
    };
  });

  // 二级候选与已选清单一并锚定到「第一个能解析出父类目的已保存项」
  const anchor = selected.value.find((item) => parentById.has(item.categoryId));
  if (anchor) {
    const parentId = parentById.get(anchor.categoryId) as string;
    selectedTopCategoryId.value = parentId;
    subCategories.value = subCategoriesByParent.get(parentId) || [];
  }
}

/* ---------- 商家登记信息：实时过滤 + 保存前校验 + 仅 dirty 提交 ---------- */

/** 把过滤后的值回写到控件本身（实时拦截非法字符；仅 H5 有真实 DOM，其他端由绑定值驱动） */
function syncInputDisplay(refValue: unknown, value: string): void {
  const host = resolveEl(refValue);
  const input = host && typeof host.querySelector === 'function' ? (host.querySelector('input') as HTMLInputElement | null) : null;
  if (input && input.value !== value) input.value = value;
}

/** 京麦商家ID 输入：实时只保留数字（拒绝空格/符号/字母/汉字） */
function onJdMerchantIdInput(event: { detail: { value: string } }): void {
  const raw = event?.detail?.value ?? '';
  const cleaned = filterDigitsOnly(raw);
  jdMerchantId.value = cleaned;
  if (cleaned !== raw) syncInputDisplay(jdMerchantIdInputRef.value, cleaned);
}

/** 店铺名称输入：实时只保留汉字（拒绝空格/符号/数字/字母） */
function onShopNameInput(event: { detail: { value: string } }): void {
  const raw = event?.detail?.value ?? '';
  const cleaned = filterChineseOnly(raw);
  shopName.value = cleaned;
  if (cleaned !== raw) syncInputDisplay(shopNameInputRef.value, cleaned);
}

/** 保存前再校验一次（实时过滤之外的兜底）：非法即阻止提交并给出明确提示 */
function validateRegistrationInputs(): boolean {
  if (!isValidJdMerchantId(jdMerchantId.value)) {
    uni.showToast({ title: JD_MERCHANT_ID_INVALID_TEXT, icon: 'none' });
    return false;
  }
  if (!isValidShopName(shopName.value)) {
    uni.showToast({ title: SHOP_NAME_INVALID_TEXT, icon: 'none' });
    return false;
  }
  return true;
}

/** 仅 dirty 字段的登记补丁；都未变化则返回 null（不重复提交未变字段） */
function buildRegistrationPatch(): MerchantRegistration | null {
  const patch: MerchantRegistration = {};
  if (jdMerchantId.value !== initialJdMerchantId.value) patch.jd_merchant_id = jdMerchantId.value;
  if (shopName.value !== initialShopName.value) patch.shop_name = shopName.value;
  return Object.keys(patch).length > 0 ? patch : null;
}

/** 预填已登记信息（GET /api/merchant/registration；失败则保持空值，不阻塞类目选择） */
async function loadRegistration(): Promise<void> {
  try {
    const data = await fetchMerchantRegistration();
    jdMerchantId.value = data?.jd_merchant_id || '';
    shopName.value = data?.shop_name || '';
  } catch (err) {
    console.warn('[经营类目] 商家登记信息预填失败', err);
    jdMerchantId.value = '';
    shopName.value = '';
  }
  initialJdMerchantId.value = jdMerchantId.value;
  initialShopName.value = shopName.value;
}

/* ---------- 已选清单操作 ---------- */

/** 加入已选；默认第一个成为主类目（保证任意时刻恰有 1 个主类目） */
function addCategory(node: CategoryNode): void {
  const categoryId = String(node.id);
  const isFirst = selected.value.length === 0;
  selected.value = selected.value.concat({ categoryId, name: node.name, isPrimary: isFirst });
}

/** 移除已选；移除主类目时把主类目顺延给剩余第一个（避免出现零主类目） */
function removeCategory(categoryId: string): void {
  const removed = selected.value.find((item) => item.categoryId === categoryId);
  const rest = selected.value.filter((item) => item.categoryId !== categoryId);
  if (removed?.isPrimary && rest.length > 0) {
    rest[0] = { ...rest[0], isPrimary: true };
  }
  selected.value = rest;
}

/** 指定主类目（单选结构：先全部置 false，再置目标为 true） */
function setPrimary(categoryId: string): void {
  selected.value = selected.value.map((item) => ({
    ...item,
    isPrimary: item.categoryId === categoryId,
  }));
}

/* ---------- 弹窗开合与保存 ---------- */

/** 关闭弹窗（× / 遮罩 / ESC / 保存 / 跳过共用）：只改可见性，不写库 */
function closeDialog(): void {
  emit('update:visible', false);
}

/** 共享 Modal 的 visible 同步 */
function handleVisibleChange(visible: boolean): void {
  emit('update:visible', visible);
}

/** 跳过：仅关闭本次弹窗（不写库、不报错、不写永久标记；下次进入仍按未保存判定） */
function handleSkip(): void {
  emit('skip');
  closeDialog();
}

/**
 * 保存：先校验（登记字段格式 + 类目数量）→ 仅 dirty 的登记字段 PUT（失败即中止，弹窗保持打开）
 * → 再 POST 保存类目（失败同样保持弹窗打开）。任一步失败都不关窗、不静默吞错。
 */
async function handleSave(): Promise<void> {
  if (saving.value) return;
  if (!validateRegistrationInputs()) return;
  if (selected.value.length < MIN_SELECTED || selected.value.length > MAX_SELECTED) {
    notifyCategoryCountError();
    return;
  }
  const patch = buildRegistrationPatch();
  const payload: MerchantCategoryItem[] = selected.value.map((item) => ({
    category_id: Number(item.categoryId),
    is_primary: item.isPrimary,
  }));
  saving.value = true;
  try {
    if (patch) {
      await saveMerchantRegistration(patch);
      // 提交成功后同步初始值：避免重复提交与后续 dirty 误判
      initialJdMerchantId.value = jdMerchantId.value;
      initialShopName.value = shopName.value;
    }
    await saveMerchantCategories(payload);
    uni.showToast({ title: SAVE_SUCCESS_TEXT, icon: 'success' });
    emit('saved');
    closeDialog();
  } catch (err) {
    // 失败文案由 request 封装按后端 message / 网络异常提示（文案 owner 是后端与请求层），此处不重复提示
    console.warn('[经营类目] 保存失败（弹窗保持打开）', err);
  } finally {
    saving.value = false;
  }
}

/** 每次打开：并行预填登记信息与一级类目，再回显已保存类目；关闭时收起两个浮层 */
watch(
  () => props.visible,
  async (visible) => {
    if (!visible) {
      closeTopDropdown();
      closeSubDropdown();
      return;
    }
    await Promise.all([loadRegistration(), loadTopCategories()]);
    await restoreSavedCategories();
  },
  { immediate: true },
);
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';
@import '@/styles/mixins/_icons.scss';

/* 浮层与弹窗的共同父级：自身不参与布局（子元素均为 fixed 定位），
   只为让 dropdown 与 <Modal> 处于同一层级上下文，从而以 z-index 稳定压在弹窗之上 */
.category-picker-root {
  display: block;
}

/* 弹窗内选择区（沿用原面板的排版与 Token；外框/标题由共享 Modal 提供） */
.category-picker {
  /* 商家登记信息输入区（弹窗最上方） */
  &__field {
    margin-bottom: $up-space-3;
  }

  &__label {
    display: block;
    margin-bottom: $up-space-1;
    font-size: $up-font-size-caption;
    color: $u-content-color;
  }

  /* 输入框：文本行由 min-height + 垂直内边距承载（不写死 height）。
     uni H5 内部 .uni-input-input 的 height:100% 取自宿主内容框，若内容框小于行框，
     汉字上下会被裁；这里保证内容框 ≥ 行框（13px × 1.5 = 19.5px）。 */
  &__input {
    width: 100%;
    box-sizing: border-box;
    min-height: 88rpx;
    padding: $up-space-2 $up-space-3;
    background-color: $u-white;
    border: 1rpx solid $u-border-color;
    border-radius: $up-radius-sm;
    font-size: $up-font-size-body-sm;
    line-height: $up-line-height-normal;
    color: $u-main-color;
  }

  &__placeholder {
    color: $u-tips-color;
    font-size: $up-font-size-body-sm;
  }

  /* 一级/二级共用的选择器触发器（两处样式一致；与输入框、操作按钮同尺寸节奏） */
  &__picker {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: $up-space-2;
    box-sizing: border-box;
    min-height: 88rpx;
    padding: $up-space-2 $up-space-3;
    background-color: $u-white;
    border: 1rpx solid $u-border-color;
    border-radius: $up-radius-sm;
    font-size: $up-font-size-body-sm;
    /* 占位态：tips 色；已选态（--filled）：内容色 */
    color: $u-tips-color;

    &--filled {
      color: $u-main-color;
    }

    & + & {
      margin-top: $up-space-3;
    }
  }

  &__picker-text {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  /* 前置图标：一级=店铺、二级=列表，同笔宽同尺寸（图标造型/颜色见 _icons.scss 唯一真源） */
  &__picker-icon {
    @include stage2-icon(stage2-shop-icon($u-primary), $up-font-size-h3);

    &--list {
      background-image: stage2-list-icon($u-primary);
    }
  }

  /* 展开指示 chevron（替代原文本三角字符）：展开时旋转 180°，Token 缓动 */
  &__chevron {
    @include stage2-icon(stage2-chevron-icon($u-tips-color), $up-font-size-body);
    transition: transform $up-ease-fast;

    &--open {
      transform: rotate(180deg);
    }
  }

  &__selected {
    margin-top: $up-space-4;
    border-top: 1rpx solid $u-border-color;
  }

  &__selected-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: $up-space-3 0;
    border-bottom: 1rpx solid $u-border-color;
  }

  &__selected-main {
    display: flex;
    align-items: center;
    gap: $up-space-4;
    flex: 1;
    min-width: 0;
  }

  &__selected-name {
    font-size: $up-font-size-body-sm;
    color: $u-main-color;
    line-height: $up-line-height-tight;
  }

  &__primary {
    display: flex;
    align-items: center;
    gap: $up-space-1;
    flex-shrink: 0;
  }

  &__radio {
    width: 28rpx;
    height: 28rpx;
    border: 2rpx solid $u-border-color;
    border-radius: $up-radius-full;
    background-color: $u-white;

    &--checked {
      border-color: $u-primary;
      background-color: $u-primary;
      box-shadow: inset 0 0 0 4rpx $u-white;
    }
  }

  &__primary-text {
    font-size: $up-font-size-caption;
    color: $u-tips-color;

    .category-picker__radio--checked + & {
      color: $u-primary-dark;
    }
  }

  &__remove {
    flex-shrink: 0;
    margin-left: $up-space-4;
    font-size: $up-font-size-caption;
    color: $u-tips-color;
  }

  /* 说明 / 提示 / 已选计数 */
  &__meta {
    display: flex;
    flex-direction: column;
    gap: $up-space-2;
    margin-top: $up-space-4;
  }

  &__intro {
    font-size: $up-font-size-caption;
    color: $u-content-color;
    line-height: $up-line-height-normal;
  }

  &__hint {
    font-size: $up-font-size-caption;
    color: $u-tips-color;
    line-height: $up-line-height-normal;
  }

  &__count {
    font-size: $up-font-size-caption;
    color: $u-tips-color;
    font-variant-numeric: tabular-nums;
  }

  /* 操作区：跳过（次）/ 保存经营类目（主） */
  &__actions {
    display: flex;
    gap: $up-space-3;
    margin-top: $up-space-5;
  }

  &__btn {
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 1;
    box-sizing: border-box;
    min-height: 88rpx;
    padding: $up-space-3 0;
    border-radius: $up-radius-sm;
    text-align: center;
    transition: background-color $up-ease-fast;

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

      &:hover {
        background-color: $u-primary-dark;
      }

      &:active {
        background-color: $u-primary-dark;
      }
    }

    &--disabled {
      opacity: 0.6;
    }
  }

  &__btn-text {
    font-size: $up-font-size-body-sm;
    font-weight: 500;
    color: $u-white;

    &--secondary {
      color: $u-content-color;
    }
  }
}
</style>
