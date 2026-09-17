<!--
  @Component TaskCard
  @Version 1.3.0
  @Description 白色卡片任务项，支持完成态、展开详情、复选框交互、类目选择器和资费展示；
               详情区提供 #detail-extra 插槽（默认不渲染），供页面私有交互扩展。
  @slot detail-extra - 详情区扩展内容（展开时显示）
  @slot right-extra - 右侧附加操作（任意完成状态常显，如「查看图片示例」按钮）
-->
<template>
  <view
    ref="cardRef"
    :class="[
      'task-card',
      {
        'task-card--completed': task.completionStatus === 'completed',
        'task-card--expanded': expanded,
      },
    ]"
    :data-tour-anchor="anchor || undefined"
    @tap="handleCardTap"
    @touchstart="pressCard"
    @touchend="releaseCard"
    @touchcancel="releaseCard"
    @mousedown="pressCard"
    @mouseup="releaseCard"
    @mouseleave="releaseCard"
  >
    <view class="task-card__main">
      <!-- 左侧复选框 -->
      <view class="task-card__checkbox" @tap.stop>
        <Checkbox
          :model-value="task.completionStatus === 'completed'"
          :tick-delay="tickDelay"
          @update:model-value="handleToggle"
        />
      </view>

      <!-- 中间内容 -->
      <view class="task-card__content">
        <view class="task-card__header">
          <text
            :class="[
              'task-card__name',
              { 'task-card__name--completed': task.completionStatus === 'completed' },
            ]"
          >
            {{ task.title }}
          </text>
          <text v-if="task.tag" class="task-card__tag">{{ task.tag }}</text>
        </view>
        <text
          v-if="task.description"
          class="task-card__desc"
        >
          {{ task.description }}
        </text>
      </view>

      <!-- 右侧操作 -->
      <view class="task-card__right">
        <view v-if="task.completionStatus !== 'completed' && task.actionText" class="task-card__action" @tap.stop="handleAction">
          <text class="task-card__action-btn">{{ task.actionText }}</text>
        </view>
        <view v-else-if="task.completionStatus === 'completed'" class="task-card__badge">
          <Badge type="success" text="已完成" />
        </view>
        <!-- 右侧附加操作插槽（如「查看图片示例」），任意完成状态常显；父级需自行 @tap.stop 防触发展开 -->
        <slot name="right-extra" />
      </view>
    </view>

    <!-- 展开详情区域 -->
    <view v-show="expanded" class="task-card__detail">
      <view class="task-card__detail-inner">
        <!-- 类目选择器（仅在指定任务显示） -->
        <view
          v-if="showCategorySelector"
          class="category-selector"
          @tap.stop
          @touchstart.stop="stopCardPress"
          @mousedown.stop="stopCardPress"
          @touchend.stop="stopCardPress"
          @mouseup.stop="stopCardPress"
        >
          <view class="category-selector__label">选择类目</view>
          
          <!-- 一级类目 -->
          <view
            ref="categoryFieldRef"
            class="category-selector__picker"
            :class="{ 'category-selector__picker--filled': !!selectedCategory }"
            @tap.stop="toggleCategoryDropdown"
          >
            <view class="category-selector__picker-icon" />
            <text class="category-selector__picker-text">{{ selectedCategory || '请选择一级类目' }}</text>
            <view
              class="category-selector__chevron"
              :class="{ 'category-selector__chevron--open': activeField === 'category' }"
            />
          </view>
          
          <!-- 二级类目 -->
          <view v-if="selectedCategory && apiSubCategoryList.length > 0" class="category-selector__sub">
            <view
              ref="subCategoryFieldRef"
              class="category-selector__picker"
              :class="{ 'category-selector__picker--filled': !!selectedSubCategory }"
              @tap.stop="toggleSubCategoryDropdown"
            >
              <view class="category-selector__picker-icon category-selector__picker-icon--list" />
              <text class="category-selector__picker-text">{{ selectedSubCategory || '请选择二级类目' }}</text>
              <view
                class="category-selector__chevron"
                :class="{ 'category-selector__chevron--open': activeField === 'subCategory' }"
              />
            </view>
          </view>

          <!-- 类目要求展示 -->
          <view v-if="selectedCategory && selectedSubCategory && categoryRequirements.length > 0" class="category-requirements">
            <view class="category-requirements__title">入驻资质要求：</view>
            <view v-for="(req, idx) in categoryRequirements" :key="idx" class="category-requirements__item">
              <text class="category-requirements__dot">•</text>
              <text>{{ req }}</text>
            </view>
          </view>
        </view>

        <!-- 资费选择器（仅在指定任务显示） -->
        <view
          v-if="showFeeSelector"
          class="fee-selector"
          @tap.stop
          @touchstart.stop="stopCardPress"
          @mousedown.stop="stopCardPress"
          @touchend.stop="stopCardPress"
          @mouseup.stop="stopCardPress"
        >
          <view class="fee-selector__label">选择类目查看资费</view>
          
          <!-- 一级类目 -->
          <view
            ref="feeCategoryFieldRef"
            class="fee-selector__picker"
            :class="{ 'fee-selector__picker--filled': !!selectedFeeCategory }"
            @tap.stop="toggleFeeCategoryDropdown"
          >
            <view class="fee-selector__picker-icon" />
            <text class="fee-selector__picker-text">{{ selectedFeeCategory || '请选择一级类目' }}</text>
            <view
              class="fee-selector__chevron"
              :class="{ 'fee-selector__chevron--open': activeField === 'fee' }"
            />
          </view>
          
          <!-- 二级类目 -->
          <view v-if="selectedFeeCategory && apiSubCategoryList.length > 0" class="fee-selector__sub">
            <view
              ref="feeSubCategoryFieldRef"
              class="fee-selector__picker"
              :class="{ 'fee-selector__picker--filled': !!selectedFeeSubCategory }"
              @tap.stop="toggleFeeSubCategoryDropdown"
            >
              <view class="fee-selector__picker-icon" />
              <text class="fee-selector__picker-text">{{ selectedFeeSubCategory || '请选择二级类目' }}</text>
              <view
                class="fee-selector__chevron"
                :class="{ 'fee-selector__chevron--open': activeField === 'feeSubCategory' }"
              />
            </view>
          </view>

          <!-- 资费展示 -->
          <view v-if="selectedFeeCategory && selectedFeeSubCategory && feeData" class="fee-display">
            <view class="fee-display__title">资费详情</view>
            <view class="fee-display__item">
              <text class="fee-display__label">保证金（GMV＜5万）</text>
              <text class="fee-display__value">{{ feeData.deposit_gmv_lt_5w }} 元</text>
            </view>
            <view class="fee-display__item">
              <text class="fee-display__label">保证金（5万≤GMV＜10万）</text>
              <text class="fee-display__value">{{ feeData.deposit_gmv_5w_10w }} 元</text>
            </view>
            <view class="fee-display__item">
              <text class="fee-display__label">保证金（10万≤GMV＜30万）</text>
              <text class="fee-display__value">{{ feeData.deposit_gmv_10w_30w }} 元</text>
            </view>
            <view class="fee-display__item">
              <text class="fee-display__label">保证金（GMV≥30万）</text>
              <text class="fee-display__value">{{ feeData.deposit_gmv_gte_30w }} 元</text>
            </view>
            <view class="fee-display__item fee-display__item--highlight">
              <text class="fee-display__label">技术服务费率</text>
              <text class="fee-display__value">{{ feeData.operation_rate }}%</text>
            </view>
            <view class="fee-display__item">
              <text class="fee-display__label">交易服务费</text>
              <text class="fee-display__value">{{ feeData.transaction_rate }}%</text>
            </view>
          </view>
        </view>

        <!-- 详情文本 -->
        <text class="task-card__detail-text">{{ task.detail || '暂无详细说明' }}</text>

        <!-- 详情区扩展插槽（阶段二等页面私有交互，默认不渲染） -->
        <slot name="detail-extra" />
      </view>
    </view>

    <!-- 类目/资费选择浮层（全局共享组件 CategorySelectDropdown，单选）：
         浮层自身为 position: fixed（遮罩 10000 / 面板 10001），位置由触发器实测锚点传入。
         不变量（#F-27 实测结论）：浮层打开时 .task-card 的 transform 必须为 none —— 卡片一旦带
         transform（含 GSAP 按压复位后残留的 matrix(1,0,0,1,0,0)）就会成为 fixed 的包含块，
         浮层会被重新锚定到卡片坐标并被 .task-card 的 overflow: hidden 裁剪。
         保护点在 releaseCard 的 clearProps 与 openDropdown 的 set(clearProps)；
         禁止给 .task-card 或其祖先新增 transform / filter / will-change（会重新引入包含块）。

         外层 <view @tap.stop>：浮层与卡片同树，点浮层项/遮罩会在冒泡阶段触达卡片的 @tap="handleCardTap"
         导致卡片被误展开/折叠；此处统一阻断冒泡。原生 <picker> 无此问题（其弹层挂在 body 下），
         改为同树浮层后必须保留该阻断（#F-27 实测：缺少时会误折叠卡片）。 -->
    <view
      @tap.stop
      @touchstart.stop="stopCardPress"
      @mousedown.stop="stopCardPress"
      @touchend.stop="stopCardPress"
      @mouseup.stop="stopCardPress"
    >
      <CategorySelectDropdown
        :visible="activeField === 'category'"
        mask-mode="passthrough"
        :trigger-el="triggerElGetter('category')"
        :trigger-selector="DROPDOWN_TRIGGER_SELECTOR"
        :options="apiCategoryList"
        :selected-ids="selectedCategoryId ? [selectedCategoryId] : []"
        :anchor="dropdownAnchor"
        @close="closeDropdown"
        @pick="pickCategory"
      />
      <CategorySelectDropdown
        :visible="activeField === 'subCategory'"
        mask-mode="passthrough"
        :trigger-el="triggerElGetter('subCategory')"
        :trigger-selector="DROPDOWN_TRIGGER_SELECTOR"
        :options="apiSubCategoryList"
        :selected-ids="selectedSubCategoryId ? [selectedSubCategoryId] : []"
        :anchor="dropdownAnchor"
        @close="closeDropdown"
        @pick="pickSubCategory"
      />
      <CategorySelectDropdown
        :visible="activeField === 'fee'"
        mask-mode="passthrough"
        :trigger-el="triggerElGetter('fee')"
        :trigger-selector="DROPDOWN_TRIGGER_SELECTOR"
        :options="apiCategoryList"
        :selected-ids="selectedFeeCategoryId ? [selectedFeeCategoryId] : []"
        :anchor="dropdownAnchor"
        @close="closeDropdown"
        @pick="pickFeeCategory"
      />
      <CategorySelectDropdown
        :visible="activeField === 'feeSubCategory'"
        mask-mode="passthrough"
        :trigger-el="triggerElGetter('feeSubCategory')"
        :trigger-selector="DROPDOWN_TRIGGER_SELECTOR"
        :options="apiSubCategoryList"
        :selected-ids="selectedFeeSubCategoryId ? [selectedFeeSubCategoryId] : []"
        :anchor="dropdownAnchor"
        @close="closeDropdown"
        @pick="pickFeeSubCategory"
      />
    </view>
  </view>
</template>

<script setup lang="ts">
/**
 * TaskCard 组件
 * @description 白色卡片任务项，支持完成态样式切换、点击展开详情、复选框交互、类目选择器和资费展示。
 * @see Checkbox
 */
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { getGsap } from '@/utils/gsap'
const gsap = getGsap()
import Checkbox from '@/components/Checkbox/index.vue'
import CategorySelectDropdown from '@/components/CategorySelectDropdown/index.vue'
import { useDropdownStore } from '@/store'
import Badge from '@/components/Badge/index.vue'
import type { TaskInfo } from '@/types/task'
import { TaskStatus, resolveTaskActionType } from '@/constants/task'
import request from '@/api/request'
import { trackTaskExpand, trackTaskComplete, trackCategorySelect, trackEvent, EventType } from '@/utils/track'

interface Props {
  /** 任务数据 */
  task: TaskInfo
  /** 默认是否展示详情区域 */
  showDetail?: boolean
  /** 是否显示类目选择器（用于了解类目要求） */
  showCategorySelector?: boolean
  /** 是否显示资费选择器（用于查询类目资费） */
  showFeeSelector?: boolean
  /** 勾选动画延迟（毫秒），整组完成时轻微 stagger */
  tickDelay?: number
  /** 引导锚点标识（ProductTour 定位用），渲染为 data-tour-anchor 属性；空则不渲染 */
  anchor?: string
}

const props = withDefaults(defineProps<Props>(), {
  showDetail: false,
  showCategorySelector: false,
  showFeeSelector: false,
  tickDelay: 0,
  anchor: '',
})

const emit = defineEmits<{
  /** 复选框状态切换时触发 */
  toggle: [taskId: string]
  /**
   * 操作按钮点击
   * @description #FE-28 契约变更：改为抛出**整个 task**（含 actionType / actionParam），
   *              由宿主按 actionType 分发行为；不再只传 taskId（避免宿主再按 taskId 硬编码）
   */
  action: [task: TaskInfo]
}>()

/** 详情展开状态 */
const expanded = ref(props.showDetail)

const cardRef = ref<HTMLElement | null>(null)
let cardEl: HTMLElement | null = null

onMounted(() => {
  cardEl = (cardRef.value as any)?.$el ?? (cardRef.value as HTMLElement | null)
})

onBeforeUnmount(() => {
  if (cardEl) gsap.killTweensOf(cardEl)
})

/** 按压中标记：只有真正按下过才允许回弹，避免鼠标移出卡片（mouseleave）凭空产生一次 scale:1 补间 */
let pressActive = false

/** 按压反馈：幅度 1/3（scale 0.9933 ≈ 原 2% 的 1/3）+ power2.out，duration/ease 不变 */
function pressCard() {
  if (!cardEl) return
  pressActive = true
  gsap.to(cardEl, { scale: 0.9933, duration: 0.12, ease: 'power2.out', overwrite: 'auto' })
}

function releaseCard() {
  if (!cardEl || !pressActive) return
  pressActive = false
  // clearProps: 'transform' —— 回弹结束后移除 inline transform。
  // 卡片只要带 transform（即使 scale 已回到 1，GSAP 仍会保留 matrix(1,0,0,1,0,0)）就会成为
  // position: fixed 的包含块，使类目/资费浮层被重新锚定并被 .task-card 的 overflow: hidden 裁剪（#F-27 实测）。
  gsap.to(cardEl, { scale: 1, duration: 0.2, ease: 'power2.out', overwrite: 'auto', clearProps: 'transform' })
}

/** 当前展开的浮层字段（''=全部收起）；由全局 dropdown store 派生，保证跨卡片同一时刻至多一个展开 */
type DropdownField = '' | 'category' | 'subCategory' | 'fee' | 'feeSubCategory'
const dropdownStore = useDropdownStore()
/** 本卡片实例的浮层 key 前缀（唯一真源在 store，组件不另存可见性副本） */
const dropdownKeyPrefix = `${props.task.taskId}::`
const dropdownKeyOf = (field: Exclude<DropdownField, ''>) => dropdownKeyPrefix + field
const activeField = computed<DropdownField>(() => {
  const key = dropdownStore.activeKey
  return key.startsWith(dropdownKeyPrefix) ? (key.slice(dropdownKeyPrefix.length) as DropdownField) : ''
})

/** 浮层锚点（触发器实测矩形：left / 下沿 top / width，单位 px） */
const dropdownAnchor = ref<{ left: number; top: number; width: number } | null>(null)

/** 触发器 ref：H5 下取真实 DOM 实测锚点（非 H5 回退 uni 选择器查询） */
const categoryFieldRef = ref<unknown>(null)
const subCategoryFieldRef = ref<unknown>(null)
const feeCategoryFieldRef = ref<unknown>(null)
const feeSubCategoryFieldRef = ref<unknown>(null)

/** uni-view ref 解出真实 DOM（H5 下 view 编译为节点；兼容 $el 包装） */
function resolveTriggerEl(refValue: unknown): HTMLElement | null {
  const v = refValue as { $el?: unknown } | HTMLElement | null
  return ((v && (v as { $el?: HTMLElement }).$el) || (v as HTMLElement | null)) || null
}

/** 实测触发器矩形作为浮层锚点（与阶段二 CategoryPicker 同一口径：left / bottom / width） */
function measureAnchor(refValue: unknown, selector: string): void {
  const el = resolveTriggerEl(refValue)
  if (el && typeof el.getBoundingClientRect === 'function') {
    const box = el.getBoundingClientRect()
    dropdownAnchor.value = { left: box.left, top: box.bottom, width: box.width }
    return
  }
  uni
    .createSelectorQuery()
    .select(selector)
    .boundingClientRect((rect) => {
      const box = rect as { left: number; bottom: number; width: number } | null
      if (box) dropdownAnchor.value = { left: box.left, top: box.bottom, width: box.width }
    })
    .exec()
}

/** 下拉触发器选择器（传给浮层 passthrough：命中它＝「其它触发器」，必须放行以保留一次点击关旧开新） */
const DROPDOWN_TRIGGER_SELECTOR = '.category-selector__picker, .fee-selector__picker'

/** 触发器元素取值器：浮层 passthrough 模式据此区分「点自身触发器（交给它 toggle）」与「点外部」 */
function triggerElGetter(field: Exclude<DropdownField, ''>) {
  const refMap = {
    category: categoryFieldRef,
    subCategory: subCategoryFieldRef,
    fee: feeCategoryFieldRef,
    feeSubCategory: feeSubCategoryFieldRef,
  } as const
  return () => resolveTriggerEl(refMap[field].value)
}

/** 收起浮层（遮罩点击或选中后由宿主收起）：直接改 store 唯一真源 */
function closeDropdown(): void {
  dropdownStore.close()
}

/**
 * 下拉交互期间阻断卡片按压：只挂 `.stop` 修饰符，无业务逻辑。
 * 触发器 / 面板项 / 遮罩都位于同一子树，若不断开 touchstart·mousedown（以及 touchend·mouseup 的回弹），
 * 卡片的 pressCard/releaseCard 会照常执行 → 卡片带 transform → 浮层（fixed）被重新锚定为卡片的包含块、
 * 遮罩被裁到卡片盒内：表现为「选不中 / 点外不收起」（#F-28 实测）。
 */
function stopCardPress(): void {
  /* 仅阻断冒泡 */
}

/**
 * 打开浮层前的硬前提：卡片 transform 必须为 none（#F-27 实测结论）。
 * transform 会让 .task-card 成为 position: fixed 的包含块，浮层被重新锚定到卡片坐标并被 overflow: hidden 裁剪。
 * 此处结束按压回弹动画并清除 transform，保证「浮层打开的那一刻」卡片已无 transform ——
 * 否则回弹动画的 200ms 内浮层仍停留在错误位置（点击触发器时 touchend/mouseup 先于 tap 触发）。
 */
function openDropdown(field: Exclude<DropdownField, ''>, refValue: unknown, selector: string): void {
  if (cardEl) {
    gsap.killTweensOf(cardEl)
    gsap.set(cardEl, { scale: 1, clearProps: 'transform' })
  }
  measureAnchor(refValue, selector)
  dropdownStore.open(dropdownKeyOf(field))
}

/** 一级类目浮层开合 */
function toggleCategoryDropdown(): void {
  if (activeField.value === 'category') {
    closeDropdown()
    return
  }
  openDropdown('category', categoryFieldRef.value, '.category-selector__picker')
}

/** 二级类目浮层开合 */
function toggleSubCategoryDropdown(): void {
  if (activeField.value === 'subCategory') {
    closeDropdown()
    return
  }
  openDropdown('subCategory', subCategoryFieldRef.value, '.category-selector__sub .category-selector__picker')
}

/** 资费一级类目浮层开合 */
function toggleFeeCategoryDropdown(): void {
  if (activeField.value === 'fee') {
    closeDropdown()
    return
  }
  openDropdown('fee', feeCategoryFieldRef.value, '.fee-selector__picker')
}

/** 资费二级类目浮层开合 */
function toggleFeeSubCategoryDropdown(): void {
  if (activeField.value === 'feeSubCategory') {
    closeDropdown()
    return
  }
  openDropdown('feeSubCategory', feeSubCategoryFieldRef.value, '.fee-selector__sub .fee-selector__picker')
}

/** 加载状态 */
const loadingCategories = ref(false)
const loadingSubCategories = ref(false)

/** API 数据 */
const apiCategoryList = ref<Array<{id: string, name: string}>>([])
const apiSubCategoryList = ref<Array<{id: string, name: string}>>([])
const apiFeeData = ref<any>(null)

/** ID 映射（类目选择器和资费选择器共用） */
const categoryMap = ref<Map<string, string>>(new Map())
const subCategoryMap = ref<Map<string, string>>(new Map())

/** 选中的一级类目 */
const selectedCategory = ref('')

/** 选中的二级类目 */
const selectedSubCategory = ref('')

/** 选中的一级资费类目 */
const selectedFeeCategory = ref('')

/** 选中的二级资费类目 */
const selectedFeeSubCategory = ref('')

/** 已选一级类目 id（浮层选中态用；名称→id 映射见 loadCategories） */
const selectedCategoryId = computed(() => categoryMap.value.get(selectedCategory.value) ?? '')

/** 已选二级类目 id（浮层选中态用；名称→id 映射见 loadSubCategories） */
const selectedSubCategoryId = computed(() => subCategoryMap.value.get(selectedSubCategory.value) ?? '')


/** 类目要求 */
const categoryRequirements = ref<string[]>([])
const loadingRequirements = ref(false)

// 通用资质要求（所有类目通用）
const generalRequirements = [
  '【基础资质要求】',
  '1. 身份信息：联系人手机号、姓名、电子邮箱；法人身份证正反面清晰原件照片，有效期需与营业执照一致',
  '2. 主体信息：企业营业执照（个体工商户不符合），注册资金不限',
  '3. 银行账户：需为企业对公账户',
  '',
  '注意：禁止上传复印件，需实拍；保证身份证在有效期内；个体工商户/个人独资禁止入驻'
]

// 监听类目变化，加载资质要求
watch([selectedCategory, selectedSubCategory], async () => {
  if (selectedCategory.value && selectedSubCategory.value) {
    loadingRequirements.value = true
    try {
      // 获取类目 ID
      const catId = categoryMap.value.get(selectedCategory.value)
      if (catId) {
        // 调用 API 获取类目资质要求
        const res = await request.get(`/api/category/requirement/${catId}`)
        if (res.code === 0 && res.data) {
          // API 成功，构建完整的资质要求列表
          const req = res.data
          const items: string[] = []
          
          // 添加基础资质要求（所有类目通用）
          items.push('【基础资质要求】')
          items.push('1. 身份信息：联系人手机号、姓名、电子邮箱；法人身份证正反面清晰原件照片，有效期需与营业执照一致')
          items.push('2. 主体信息：企业营业执照（个体工商户不符合），注册资金不限')
          items.push('3. 银行账户：需为企业对公账户')
          items.push('')
          
          // 添加类目专属要求
          items.push('【类目专属要求】')
          items.push(`店铺类型：${req.shopType}`)
          items.push(`店铺名规范：${req.shopNameRule}`)
          
          if (req.requirements?.items) {
            req.requirements.items.forEach((item: any) => {
              const required = item.required ? '（必须）' : '（可选）'
              items.push(`${item.label}${required}：${item.description}`)
            })
          }
          
          if (req.requirements?.special_notes) {
            items.push('')
            items.push(`特殊说明：${req.requirements.special_notes}`)
          }
          
          if (req.requirements?.forbidden_items) {
            items.push(`禁止事项：${req.requirements.forbidden_items.join('、')}`)
          }
          
          categoryRequirements.value = items
        } else {
          // API 无专属要求，显示通用资质要求
          categoryRequirements.value = generalRequirements
        }
      } else {
        categoryRequirements.value = generalRequirements
      }
    } catch (err) {
      console.error('加载类目资质要求失败:', err)
      categoryRequirements.value = generalRequirements
    } finally {
      loadingRequirements.value = false
    }
  } else {
    categoryRequirements.value = []
  }
})

/** 资费已选一级类目 id（资费复用同一份类目数据与同一套映射） */
const selectedFeeCategoryId = computed(() => categoryMap.value.get(selectedFeeCategory.value) ?? '')

/** 资费已选二级类目 id */
const selectedFeeSubCategoryId = computed(() => subCategoryMap.value.get(selectedFeeSubCategory.value) ?? '')

/** 资费数据 */
const feeData = computed(() => apiFeeData.value)

/** 点击卡片切换展开 */
function handleCardTap(): void {
  const next = !expanded.value;
  expanded.value = next;
  // 埋点：展开/收起任务详情
  if (next) {
    trackTaskExpand(props.task.taskId);
  } else {
    trackEvent(EventType.TASK_COLLAPSE, { taskKey: props.task.taskId });
  }
}

/** 复选框切换事件转发 */
function handleToggle(): void {
    // 埋点：记录任务完成/取消完成
    const newStatus = props.task.completionStatus === 'completed' ? 'pending' : 'completed';
    if (newStatus === 'completed') {
      trackTaskComplete(props.task.taskId, props.task.stageId);
    } else {
      trackEvent(EventType.TASK_UNCOMPLETE, {
        taskKey: props.task.taskId,
        stageKey: props.task.stageId,
      });
    }
    emit('toggle', props.task.taskId)
  }
/** 一级类目选中（浮层回传 id，替代原 <picker> 的 index 口径）：重置二级并加载二级候选 */
function pickCategory(id: string) {
  const hit = apiCategoryList.value.find(item => String(item.id) === id)
  if (!hit) return
  selectedCategory.value = hit.name
  selectedSubCategory.value = ''
  // 埋点：记录类目选择
  trackCategorySelect(hit.name, props.task.taskId);
  closeDropdown()
  // 从 API 获取二级类目
  loadSubCategories(String(hit.id))
}

/** 二级类目选中（浮层回传 id） */
function pickSubCategory(id: string) {
  const hit = apiSubCategoryList.value.find(item => String(item.id) === id)
  if (!hit) return
  selectedSubCategory.value = hit.name
  closeDropdown()
  // 埋点：记录二级类目选择
  trackEvent(EventType.SUBCATEGORY_SELECT, {
    taskKey: props.task.taskId,
    meta: { category_name: hit.name },
  });
}

/** 资费一级类目选中（浮层回传 id）：重置二级与资费数据并加载二级候选 */
function pickFeeCategory(id: string) {
  const hit = apiCategoryList.value.find(item => String(item.id) === id)
  if (!hit) return
  selectedFeeCategory.value = hit.name
  selectedFeeSubCategory.value = ''
  apiFeeData.value = null
  closeDropdown()
  // 从 API 获取二级类目
  loadSubCategories(String(hit.id))
}

/** 资费二级类目选中（浮层回传 id）：沿用原口径以二级类目 id 查询资费详情 */
function pickFeeSubCategory(id: string) {
  const hit = apiSubCategoryList.value.find(item => String(item.id) === id)
  if (!hit) return
  selectedFeeSubCategory.value = hit.name
  closeDropdown()
  // 从 API 获取资费详情
  loadFeeDetail(String(hit.id))
}

/** 加载一级类目（从 API） */
async function loadCategories() {
  loadingCategories.value = true
  try {
    const res = await request.get('/api/category/list')
    if (res.code === 0 && res.data) {
      apiCategoryList.value = res.data
      // 构建 name -> id 映射
      const map = new Map<string, string>()
      res.data.forEach((item: any) => { map.set(item.name, item.id) })
      categoryMap.value = map
    }
  } catch (err) {
    console.error('加载类目失败:', err)
  } finally {
    loadingCategories.value = false
  }
}

/** 加载二级类目（从 API） */
async function loadSubCategories(parentId: string) {
  loadingSubCategories.value = true
  try {
    const res = await request.get(`/api/category/list?parent_id=${parentId}`)
    if (res.code === 0 && res.data) {
      apiSubCategoryList.value = res.data
      const map = new Map<string, string>()
      res.data.forEach((item: any) => { map.set(item.name, item.id) })
      subCategoryMap.value = map
    }
  } catch (err) {
    console.error('加载二级类目失败:', err)
  } finally {
    loadingSubCategories.value = false
  }
}

/** 加载资费一级类目（复用 loadCategories） */
const loadFeeCategories = loadCategories

/** 加载资费二级类目（复用 loadSubCategories） */
const loadFeeSubCategories = loadSubCategories

/** 加载资费详情（从 API） */
async function loadFeeDetail(categoryId: string) {
  try {
    const res = await request.get(`/api/fee/detail?category_id=${categoryId}`)
    if (res.code === 0 && res.data) {
      apiFeeData.value = res.data
    }
  } catch (err) {
    console.error('加载资费详情失败:', err)
  }
}
/** 组件挂载时加载类目数据（两个选择器共用同一份类目数据，只加载一次） */
onMounted(() => {
  if (props.showCategorySelector || props.showFeeSelector) {
    loadCategories()
  }
})

/** 处理操作按钮点击 */
function handleAction() {
  const actionType = resolveTaskActionType(props.task.actionType);
  // 埋点：记录按钮点击
  trackEvent(EventType.ACTION_CLICK, {
    taskKey: props.task.taskId,
    meta: {
      action_text: props.task.actionText,
      action_type: actionType,
      action_url: props.task.actionUrl || '',
    },
  });

  // 总控裁决（2026-09-16）：actionType 优先于 actionUrl ——
  // actionType 是「这个任务需要哪种交互」的协议声明，actionUrl 只是参数/兜底；
  // 若先看 actionUrl，带外链的 data_* 任务会永远走外链、页内交互到不了。
  if (actionType !== 'none') {
    emit('action', props.task)
    return
  }

  if (props.task.actionUrl) {
    // actionType=none 时才把 actionUrl 当作「打开外链」兜底
    window.open(props.task.actionUrl, '_blank')
    return
  }

  emit('action', props.task)
}
</script>

<style lang="scss" scoped>
@import "@/styles/tokens/_index.scss";
@import '@/styles/mixins/_icons.scss';

/* 覆盖 uni-app 默认 button 样式 */
uni-button,
button {
  line-height: 1.4 !important;
  font-size: inherit !important;
  padding: 0 !important;
  margin: 0 !important;
  background-color: transparent !important;
  border: none !important;
  border-radius: 0 !important;
  &::after {
    display: none !important;
  }
}
.task-card {
  background-color: $u-white;
  border: 1rpx solid $u-border-color;
  border-radius: $up-radius-lg;
  margin-bottom: $up-radius-lg;
  /* 只过渡 hover 相关属性；本卡片的 transform 完全由 GSAP 按压动画驱动（无 CSS 规则改变它），
     一旦在 transition 列表里，clearProps 移除 inline transform 时浏览器会把 matrix(1,0,0,1,0,0) → none
     当作可过渡变化，计算值在过渡期内仍是 matrix —— 卡片因而仍是 fixed 的包含块，
     浮层打开瞬间被错误锚定（#F-27 实测：375 触摸路径浮层 top 由 452 变 717、命中 task-card__main）。 */
  transition: box-shadow $up-ease-normal, border-color $up-ease-normal;
  overflow: hidden;

  /* H5 hover：轻上浮 + 柔和阴影增强（卡片微动效） */
  &:hover {
    box-shadow: $up-shadow-md;
    border-color: $u-primary;
  }

  &--completed {
    background-color: $u-success-light;
    border-color: $u-success-dark;
  }

  &__main {
    display: flex;
    align-items: flex-start;
    padding: $up-space-5;
    gap: $up-space-4;
  }

  &__checkbox {
    flex-shrink: 0;
    position: relative;
    z-index: 1;
    /* 扩大勾选点击区域：padding 覆盖视觉范围，负 margin 抵消布局偏移 */
    padding: $up-space-3;
    margin: calc(4rpx - #{$up-space-3}) calc(#{$up-space-3} * -1) calc(#{$up-space-3} * -1);
  }

  &__content {
    flex: 1;
    min-width: 0;
  }

  &__header {
    display: flex;
    align-items: center;
    gap: $up-space-2;
    margin-bottom: $up-space-1;
  }

  &__name {
    font-size: $up-font-size-body;
    font-weight: 500;
    color: $u-main-color;
    line-height: 1.5;

    &--completed {
      color: $u-tips-color;
      text-decoration: line-through;
    }
  }

  &__tag {
    font-size: $up-font-size-mini;
    padding: 2rpx 16rpx;
    border-radius: $up-radius-full;
    background-color: $u-primary-light;
    color: $u-primary-dark;
    font-weight: 500;
  }

  &__desc {
    font-size: $up-font-size-caption;
    color: $u-tips-color;
    line-height: 1.5;
  }

  &__right {
    flex-shrink: 0;
    display: flex;
    align-items: center;
  }

  &__action-btn {
    font-size: $up-font-size-caption;
    color: $u-white;
    background-color: $u-primary;
    border: none;
    border-radius: $up-radius-sm;
    padding: 10rpx 24rpx;
    line-height: 1.4;
  }

  &__action-text {
    font-size: $up-font-size-caption;
    color: $u-tips-color;
  }

  &__detail {
    padding: 0 $up-space-5 $up-space-5;
    border-top: 1rpx solid $u-border-color;
  }

  &__detail-inner {
    padding: $up-space-4;
    background-color: $u-bg-color;
    border-radius: $up-radius-md;
    margin-top: $up-space-3;
  }

  &__detail-text {
    font-size: $up-font-size-caption;
    color: $u-content-color;
    line-height: 1.8;
  }
}

/* 类目选择器 */
.category-selector {
  margin-bottom: $up-space-4;

  &__label {
    font-size: $up-font-size-caption;
    color: $u-tips-color;
    margin-bottom: $up-space-2;
  }

  /* 触发器（与阶段二 CategoryPicker 同一视觉语言，取值一律 Token）：
     占位态 tips 色 / 已选态（--filled）内容色；chevron 展开时旋转 180° */
  &__picker {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: $up-space-2;
    box-sizing: border-box;
    padding: $up-space-3 $up-space-4;
    background-color: $u-white;
    border: 1rpx solid $u-border-color;
    border-radius: $up-radius-sm;
    font-size: $up-font-size-body-sm;
    color: $u-tips-color;
    min-height: 72rpx;

    &--filled {
      color: $u-main-color;
    }
  }

  /* 前置图标：一级=店铺、二级=列表（同笔宽同尺寸，图标造型/颜色见 _icons.scss 唯一真源） */
  &__picker-icon {
    @include stage2-icon(stage2-shop-icon($u-primary), $up-font-size-h3);

    &--list {
      background-image: stage2-list-icon($u-primary);
    }
  }

  &__picker-text {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  &__chevron {
    @include stage2-icon(stage2-chevron-icon($u-tips-color), $up-font-size-body);
    transition: transform $up-ease-fast;

    &--open {
      transform: rotate(180deg);
    }
  }

  &__sub {
    margin-top: $up-space-3;
  }
}

/* 类目要求展示 */
.category-requirements {
  margin-top: $up-space-4;
  padding: $up-space-3;
  background-color: $u-white;
  border-radius: $up-radius-sm;
  border: 1rpx solid $u-border-color;

  &__title {
    font-size: $up-font-size-caption;
    font-weight: 500;
    color: $u-main-color;
    margin-bottom: $up-space-2;
  }

  &__item {
    display: flex;
    align-items: flex-start;
    gap: $up-space-2;
    font-size: $up-font-size-caption;
    color: $u-content-color;
    line-height: 1.6;
    margin-bottom: $up-space-1;
  }

  &__dot {
    color: $u-primary;
    flex-shrink: 0;
  }
}

/* 资费选择器 */
.fee-selector {
  margin-bottom: $up-space-4;

  &__label {
    font-size: $up-font-size-caption;
    color: $u-tips-color;
    margin-bottom: $up-space-2;
  }

  /* 触发器（与阶段二 CategoryPicker 同一视觉语言，取值一律 Token）：
     占位态 tips 色 / 已选态（--filled）内容色；chevron 展开时旋转 180° */
  &__picker {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: $up-space-2;
    box-sizing: border-box;
    padding: $up-space-3 $up-space-4;
    background-color: $u-white;
    border: 1rpx solid $u-border-color;
    border-radius: $up-radius-sm;
    font-size: $up-font-size-body-sm;
    color: $u-tips-color;
    min-height: 72rpx;

    &--filled {
      color: $u-main-color;
    }
  }

  /* 前置图标：资费选定「列表/明细」图标（与二级类目同族同笔宽，图标造型/颜色见 _icons.scss 唯一真源）——
     资费区域产出保证金与费率档位的明细清单，「列表/明细」语义最贴近 */
  &__picker-icon {
    @include stage2-icon(stage2-list-icon($u-primary), $up-font-size-h3);
  }

  &__picker-text {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  &__chevron {
    @include stage2-icon(stage2-chevron-icon($u-tips-color), $up-font-size-body);
    transition: transform $up-ease-fast;

    &--open {
      transform: rotate(180deg);
    }
  }

  &__sub {
    margin-top: $up-space-3;
  }
}

/* 资费展示 */
.fee-display {
  margin-top: $up-space-4;
  padding: $up-space-4;
  background-color: $u-white;
  border-radius: $up-radius-md;
  border: 1rpx solid $u-border-color;

  &__title {
    font-size: $up-font-size-body-sm;
    font-weight: 600;
    color: $u-main-color;
    margin-bottom: $up-space-3;
    padding-bottom: $up-space-2;
    border-bottom: 1rpx solid $u-border-color;
  }

  &__item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: $up-space-2 0;
    border-bottom: 1rpx solid $u-border-color;

    &:last-child {
      border-bottom: none;
    }

    &--highlight {
      background-color: $u-primary-light;
      margin: $up-space-2 calc(#{$up-space-4} * -1);
      padding: $up-space-3 $up-space-4;
      border-radius: $up-radius-sm;
      border-bottom: none;
    }
  }

  &__label {
    font-size: $up-font-size-caption;
    color: $u-content-color;
  }

  &__value {
    font-size: $up-font-size-body-sm;
    font-weight: 600;
    color: $u-main-color;

    .fee-display__item--highlight & {
      color: $u-primary-dark;
    }
  }
}
</style>




