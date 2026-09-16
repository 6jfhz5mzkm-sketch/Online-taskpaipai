<template>
  <div class="merchant-list-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>{{ MERCHANT_LIST_TITLE }}</span>
        </div>
      </template>

      <!-- 筛选区：关键词（回车或「查询」触发）+ 阶段 + 状态 -->
      <div class="filter-bar">
        <el-input
          v-model="query.keyword"
          class="filter-bar__keyword"
          :placeholder="MERCHANT_LIST_KEYWORD_PLACEHOLDER"
          clearable
          @keyup.enter="handleSearch"
        />
        <el-select v-model="query.stage" class="filter-bar__select">
          <el-option :label="MERCHANT_LIST_ALL_OPTION_LABEL" value="" />
          <el-option v-for="s in MERCHANT_STAGE_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-select v-model="query.status" class="filter-bar__select">
          <el-option :label="MERCHANT_LIST_ALL_OPTION_LABEL" value="" />
          <el-option v-for="s in MERCHANT_STATUS_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-button type="primary" @click="handleSearch">
          <el-icon><Search /></el-icon>
          {{ MERCHANT_LIST_SEARCH_TEXT }}
        </el-button>
        <el-button @click="handleReset">{{ MERCHANT_LIST_RESET_TEXT }}</el-button>
      </div>

      <el-alert
        v-if="loadFailed"
        class="load-failed"
        type="error"
        :closable="false"
        :title="MERCHANT_LIST_FAILED_TEXT"
      />

      <!-- 整行可点 + 操作列入口：两种习惯都覆盖（点击后跳「商家进度」页并自动打开该商家抽屉） -->
      <el-table :data="rows" v-loading="loading" stripe class="merchant-table" @row-click="handleRowClick">
        <el-table-column prop="merchant_id" :label="COL.merchantId" width="240" show-overflow-tooltip />
        <el-table-column :label="COL.nickname" width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ textOrPlaceholder(row.nickname) }}</template>
        </el-table-column>
        <el-table-column :label="COL.jdMerchantId" width="150">
          <template #default="{ row }">{{ registrationText(row.jd_merchant_id) }}</template>
        </el-table-column>
        <el-table-column :label="COL.shopName" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ registrationText(row.shop_name) }}</template>
        </el-table-column>
        <el-table-column :label="COL.currentStage" width="120">
          <template #default="{ row }">{{ stageText(row.current_stage) }}</template>
        </el-table-column>
        <el-table-column :label="COL.status" width="100">
          <template #default="{ row }">{{ statusText(row.status) }}</template>
        </el-table-column>
        <el-table-column :label="COL.lastLoginAt" width="170">
          <template #default="{ row }">{{ formatTime(row.last_login_at) }}</template>
        </el-table-column>
        <el-table-column :label="COL.createdAt" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column :label="COL.action" width="110" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click.stop="goProgressDetail(row.merchant_id)">
              {{ MERCHANT_DETAIL_ENTRY_TEXT }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!loading && !loadFailed && rows.length === 0" class="empty-tip">
        {{ MERCHANT_LIST_EMPTY_TEXT }}
      </div>

      <!-- 分页：与后端 page/page_size 对齐（page_size 上界 100） -->
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[...MERCHANT_LIST_PAGE_SIZES]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSearch"
          @current-change="handleSearch"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { getAdminMerchantList } from '@/api/merchant'
import type { AdminMerchantItem, AdminMerchantQuery, AdminMerchantStage, AdminMerchantStatus } from '@/api/merchant'
import {
  MERCHANT_DETAIL_ENTRY_TEXT,
  MERCHANT_INFO_UNREGISTERED_TEXT,
  MERCHANT_LIST_ALL_OPTION_LABEL,
  MERCHANT_LIST_COLUMN_LABELS,
  MERCHANT_LIST_DEFAULT_PAGE_SIZE,
  MERCHANT_LIST_EMPTY_TEXT,
  MERCHANT_LIST_FAILED_TEXT,
  MERCHANT_LIST_KEYWORD_PLACEHOLDER,
  MERCHANT_LIST_PAGE_SIZES,
  MERCHANT_LIST_RESET_TEXT,
  MERCHANT_LIST_SEARCH_TEXT,
  MERCHANT_LIST_TITLE,
  MERCHANT_LIST_VALUE_PLACEHOLDER,
  MERCHANT_STAGE_LABELS,
  MERCHANT_STAGE_OPTIONS,
  MERCHANT_STATUS_LABELS,
  MERCHANT_STATUS_OPTIONS,
} from '@/constants/merchant'

const COL = MERCHANT_LIST_COLUMN_LABELS
const router = useRouter()

const loading = ref(false)
const loadFailed = ref(false)
const rows = ref<AdminMerchantItem[]>([])
const total = ref(0)

/** 筛选条件：空串 = 不传该参数；阶段/状态为后端枚举，非法值会被后端 400 拒绝 */
const query = reactive({
  keyword: '',
  stage: '' as '' | AdminMerchantStage,
  status: '' as '' | AdminMerchantStatus,
  page: 1,
  page_size: MERCHANT_LIST_DEFAULT_PAGE_SIZE,
})

/** 普通文本列：空值统一占位 */
const textOrPlaceholder = (value?: string | null) => (value && value.trim() ? value : MERCHANT_LIST_VALUE_PLACEHOLDER)

/** 登记类字段（京麦商家ID / 店铺名）：未登记用既有文案，与商家进度页登记信息区一致 */
const registrationText = (value?: string | null) => (value && value.trim() ? value : MERCHANT_INFO_UNREGISTERED_TEXT)

/** 阶段：映射中文标签；未登记取值回退原值，不隐藏 */
const stageText = (value?: string | null) =>
  value ? MERCHANT_STAGE_LABELS[value] ?? value : MERCHANT_LIST_VALUE_PLACEHOLDER

/**
 * 状态：中文标签映射。
 * 当前后端投影未返回 status（见 api 层注释），故按空值占位展示；#PB-24 落地后自动生效。
 */
const statusText = (value?: number | null) => {
  if (value === null || value === undefined) return MERCHANT_LIST_VALUE_PLACEHOLDER
  return MERCHANT_STATUS_LABELS[String(value)] ?? String(value)
}

const formatTime = (value?: string | null) => {
  if (!value) return MERCHANT_LIST_VALUE_PLACEHOLDER
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return MERCHANT_LIST_VALUE_PLACEHOLDER
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const fetchList = async () => {
  loading.value = true
  loadFailed.value = false
  try {
    const params: AdminMerchantQuery = { page: query.page, page_size: query.page_size }
    const keyword = query.keyword.trim()
    if (keyword) params.keyword = keyword
    if (query.stage) params.stage = query.stage
    if (query.status) params.status = query.status
    const res = await getAdminMerchantList(params)
    rows.value = res.data?.list ?? []
    total.value = res.data?.total ?? 0
  } catch (error) {
    // 错误提示由 request 拦截器按后端 message 统一展示，这里只记日志并给出页面级错误态
    loadFailed.value = true
    rows.value = []
    total.value = 0
    console.error('获取商家清单失败', error)
  } finally {
    loading.value = false
  }
}

/** 查询：回到第 1 页再拉取 */
const handleSearch = () => {
  query.page = 1
  fetchList()
}

const handleReset = () => {
  query.keyword = ''
  query.stage = ''
  query.status = ''
  query.page = 1
  fetchList()
}

/**
 * 详情入口：跳「商家进度」页并把 merchantId 交给该页（抽屉是单个商家详情的唯一入口，
 * 本页不复制抽屉；进度页负责读 query 并自动开抽屉）。
 */
const goProgressDetail = (merchantId: string) => {
  router.push({ path: '/merchant-progress', query: { merchantId } })
}

/** 整行可点：与操作列按钮同一去路 */
const handleRowClick = (row: AdminMerchantItem) => {
  goProgressDetail(row.merchant_id)
}

onMounted(fetchList)
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filter-bar {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.filter-bar__keyword {
  width: 280px;
}

.filter-bar__select {
  width: 150px;
}

.load-failed {
  margin-bottom: 16px;
}

/* 整行可点：手型光标 + 提示可点（hover 背景色沿用 Element Plus 默认行 hover） */
.merchant-table :deep(.el-table__row) {
  cursor: pointer;
}

.pagination-wrap {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.empty-tip {
  text-align: center;
  color: var(--el-text-color-secondary);
  padding: 24px 0;
  font-size: 13px;
}
</style>
