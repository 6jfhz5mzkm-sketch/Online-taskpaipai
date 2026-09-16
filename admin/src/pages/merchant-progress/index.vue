<template>
  <div class="merchant-progress-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>商家管理</span>
          <el-button :loading="loading" @click="fetchMerchants">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <!-- 商家列表（由任务进度聚合） -->
      <el-table :data="merchantRows" v-loading="loading" stripe>
        <el-table-column prop="merchantId" label="商家ID" width="220">
          <template #default="{ row }">
            <el-link type="primary" :underline="false" @click="viewDetail(row.merchantId)">{{ row.merchantId }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="total" label="任务总数" width="120" />
        <el-table-column prop="completed" label="已完成" width="120">
          <template #default="{ row }">
            <el-tag :type="row.completed > 0 ? 'success' : 'info'">{{ row.completed }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="完成率" width="180">
          <template #default="{ row }">
            <el-progress
              :percentage="row.total ? Math.round((row.completed / row.total) * 100) : 0"
              :stroke-width="10"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="220" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="viewDetail(row.merchantId)">{{ MERCHANT_DETAIL_ENTRY_TEXT }}</el-button>
            <el-button
              v-if="canUnlock"
              type="warning"
              link
              :loading="unlockingId === row.merchantId"
              @click="handleUnlock(row.merchantId)"
            >一键解锁阶段一</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 进度详情抽屉 -->
    <el-drawer v-model="drawerVisible" :title="`商家进度详情：${currentMerchantId}`" size="820px">
      <!-- 商家登记信息（复用 API-17 主表列表按 merchantId 取回） -->
      <el-descriptions :title="MERCHANT_INFO_TITLE" :column="1" border size="small" class="merchant-info">
        <el-descriptions-item :label="MERCHANT_INFO_JD_ID_LABEL">
          {{ infoFieldText(merchantInfo?.jd_merchant_id) }}
        </el-descriptions-item>
        <el-descriptions-item :label="MERCHANT_INFO_SHOP_NAME_LABEL">
          {{ infoFieldText(merchantInfo?.shop_name) }}
        </el-descriptions-item>
      </el-descriptions>

      <el-table :data="detailRows" v-loading="detailLoading" size="small" stripe>
        <el-table-column prop="taskId" label="任务ID" width="110" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'completed' ? 'success' : 'info'">
              {{ row.status === 'completed' ? '已完成' : '未完成' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="完成时间" min-width="170">
          <template #default="{ row }">{{ formatTime(row.completedAt) }}</template>
        </el-table-column>
      </el-table>
      <div v-if="!detailLoading && detailRows.length === 0" class="empty-tip">{{ MERCHANT_PROGRESS_EMPTY_DETAIL_TEXT }}</div>

      <!-- 同店账号（1 个京麦商家ID ↔ N 个商家账号；**只共享进度**；设计单 §6.1 位置硬约束：登记信息之下、任务进度表之后） -->
      <div class="binding-section">
        <div class="binding-section__header">
          <span class="binding-section__title">{{ MERCHANT_BINDING_TITLE }}</span>
          <el-tooltip
            :disabled="!bindingDisabled"
            :content="MERCHANT_BINDING_UNREGISTERED_TOOLTIP_TEXT"
            placement="top"
          >
            <span class="binding-section__bind-wrap">
              <el-button type="primary" size="small" :disabled="bindingDisabled" @click="openBindDialog">
                {{ MERCHANT_BINDING_BIND_TEXT }}
              </el-button>
            </span>
          </el-tooltip>
        </div>

        <el-alert
          v-if="bindingDisabled"
          class="binding-section__hint"
          type="info"
          :closable="false"
          :title="MERCHANT_BINDING_UNREGISTERED_TEXT"
        />
        <el-alert
          v-else-if="bindingsFailed"
          class="binding-section__hint"
          type="error"
          :closable="false"
          :title="MERCHANT_BINDING_FAILED_TEXT"
        />

        <!-- 加载失败时只呈现错误提示，不叠加空表（避免「加载失败 + No Data」自相矛盾） -->
        <el-table v-else :data="bindingMembers" v-loading="bindingsLoading" size="small" stripe>
          <el-table-column :label="BINDING_COL.merchantId" min-width="190" show-overflow-tooltip>
            <template #default="{ row }">
              {{ row.merchant_id }}
              <el-tag v-if="row.is_self" class="binding-self-tag" size="small" type="info" effect="plain">
                {{ MERCHANT_BINDING_SELF_TAG_TEXT }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="BINDING_COL.nickname" width="130" show-overflow-tooltip>
            <template #default="{ row }">{{ textOrPlaceholder(row.nickname) }}</template>
          </el-table-column>
          <el-table-column :label="BINDING_COL.status" width="90">
            <template #default="{ row }">{{ statusText(row.status) }}</template>
          </el-table-column>
          <el-table-column :label="BINDING_COL.boundAt" width="150">
            <template #default="{ row }">{{ formatTime(row.bound_at) }}</template>
          </el-table-column>
          <el-table-column :label="BINDING_COL.boundBy" width="110">
            <template #default="{ row }">{{ textOrPlaceholder(row.bound_by) }}</template>
          </el-table-column>
          <el-table-column :label="BINDING_COL.action" width="80" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="!row.is_self"
                type="danger"
                link
                :loading="unbindingId === row.merchant_id"
                @click="handleUnbind(row)"
              >{{ MERCHANT_BINDING_UNBIND_TEXT }}</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-if="!bindingsLoading && !bindingsFailed && bindingMembers.length === 0" class="empty-tip">
          {{ MERCHANT_BINDING_EMPTY_TEXT }}
        </div>
      </div>
    </el-drawer>

    <!-- 绑定账号弹窗：候选只展示 商家ID / 昵称 / 状态（绝不展示手机号） -->
    <el-dialog
      v-model="bindDialogVisible"
      :title="MERCHANT_BINDING_DIALOG_TITLE"
      width="620px"
      :close-on-click-modal="false"
    >
      <div class="bind-search">
        <el-input
          v-model="bindKeyword"
          :placeholder="MERCHANT_BINDING_SEARCH_PLACEHOLDER"
          clearable
          @keyup.enter="handleCandidateSearch"
        />
        <el-button type="primary" :loading="candidateLoading" @click="handleCandidateSearch">
          {{ MERCHANT_BINDING_SEARCH_TEXT }}
        </el-button>
      </div>

      <el-table
        :data="candidateRows"
        v-loading="candidateLoading"
        size="small"
        highlight-current-row
        @current-change="handleCandidateSelect"
      >
        <el-table-column prop="merchant_id" :label="CANDIDATE_COL.merchantId" min-width="200" show-overflow-tooltip />
        <el-table-column :label="CANDIDATE_COL.nickname" width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ textOrPlaceholder(row.nickname) }}</template>
        </el-table-column>
        <el-table-column :label="CANDIDATE_COL.status" width="90">
          <template #default="{ row }">{{ statusText(row.status) }}</template>
        </el-table-column>
      </el-table>
      <div v-if="!candidateLoading && candidateRows.length === 0" class="empty-tip">
        {{ MERCHANT_BINDING_CANDIDATE_EMPTY_TEXT }}
      </div>

      <template #footer>
        <el-button @click="bindDialogVisible = false">{{ MERCHANT_BINDING_CANCEL_TEXT }}</el-button>
        <el-button type="primary" :loading="binding" @click="handleBindConfirm">
          {{ MERCHANT_BINDING_BIND_TEXT }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getMerchantProgressList, getMerchantProgressDetail, unlockMerchantPhase1 } from '@/api/task-progress'
import type { MerchantProgressItem } from '@/api/task-progress'
import {
  bindMerchantMember,
  getAdminMerchantList,
  getMerchantBindings,
  releaseMerchantMember,
} from '@/api/merchant'
import type { AdminMerchantItem, AdminMerchantQuery, MerchantBindingMember } from '@/api/merchant'
import {
  MERCHANT_INFO_FAILED_TEXT,
  MERCHANT_INFO_JD_ID_LABEL,
  MERCHANT_INFO_LOADING_TEXT,
  MERCHANT_INFO_QUERY_PAGE_SIZE,
  MERCHANT_INFO_SHOP_NAME_LABEL,
  MERCHANT_INFO_TITLE,
  MERCHANT_INFO_UNREGISTERED_TEXT,
  MERCHANT_BINDING_CANCEL_TEXT,
  MERCHANT_BINDING_CANDIDATE_COLUMN_LABELS,
  MERCHANT_BINDING_CANDIDATE_EMPTY_TEXT,
  MERCHANT_BINDING_CANDIDATE_PAGE_SIZE,
  MERCHANT_BINDING_COLUMN_LABELS,
  MERCHANT_BINDING_CONFIRM_MESSAGE,
  MERCHANT_BINDING_CONFIRM_OK_TEXT,
  MERCHANT_BINDING_CONFIRM_TITLE,
  MERCHANT_BINDING_DIALOG_TITLE,
  MERCHANT_BINDING_BIND_TEXT,
  MERCHANT_BINDING_EMPTY_TEXT,
  MERCHANT_BINDING_FAILED_TEXT,
  MERCHANT_BINDING_SEARCH_PLACEHOLDER,
  MERCHANT_BINDING_SEARCH_TEXT,
  MERCHANT_BINDING_SELECTED_REQUIRED_TEXT,
  MERCHANT_BINDING_SELF_TAG_TEXT,
  MERCHANT_BINDING_TITLE,
  MERCHANT_BINDING_UNBIND_CONFIRM_MESSAGE,
  MERCHANT_BINDING_UNBIND_CONFIRM_MESSAGE_TWO_MEMBERS,
  MERCHANT_BINDING_UNBIND_CONFIRM_OK_TEXT,
  MERCHANT_BINDING_UNBIND_CONFIRM_TITLE,
  MERCHANT_BINDING_UNBIND_TEXT,
  MERCHANT_BINDING_UNREGISTERED_TEXT,
  MERCHANT_BINDING_UNREGISTERED_TOOLTIP_TEXT,
  MERCHANT_DETAIL_ENTRY_TEXT,
  MERCHANT_LIST_EMPTY_TEXT,
  MERCHANT_LIST_VALUE_PLACEHOLDER,
  MERCHANT_PROGRESS_EMPTY_DETAIL_TEXT,
  MERCHANT_STATUS_LABELS,
} from '@/constants/merchant'
import { useAuthStore } from '@/store/modules/auth'

interface MerchantRow {
  merchantId: string
  total: number
  completed: number
}

const BINDING_COL = MERCHANT_BINDING_COLUMN_LABELS
const CANDIDATE_COL = MERCHANT_BINDING_CANDIDATE_COLUMN_LABELS

const authStore = useAuthStore()
const route = useRoute()
const loading = ref(false)
const merchantRows = ref<MerchantRow[]>([])

const drawerVisible = ref(false)
const detailLoading = ref(false)
const detailRows = ref<MerchantProgressItem[]>([])
const currentMerchantId = ref('')

// 商家登记信息（京麦商家ID / 店铺名称，来自 API-17 主表列表）
const merchantInfo = ref<AdminMerchantItem | null>(null)
const merchantInfoLoading = ref(false)
const merchantInfoFailed = ref(false)

// 同店账号绑定（API-22）
const bindingMembers = ref<MerchantBindingMember[]>([])
const bindingsLoading = ref(false)
const bindingsFailed = ref(false)
const bindDialogVisible = ref(false)
const bindKeyword = ref('')
const candidateRows = ref<AdminMerchantItem[]>([])
const candidateLoading = ref(false)
const selectedCandidate = ref<AdminMerchantItem | null>(null)
const binding = ref(false)
const unbindingId = ref('')

const unlockingId = ref('')

/**
 * 绑定入口是否禁用：以抽屉内已展示的「京麦商家ID」（API-17 登记信息）为准 ——
 * 未登记时禁用并给 tooltip，避免运营点了才被后端 400 拒绝。
 */
const bindingDisabled = computed(() => !merchantInfo.value?.jd_merchant_id)

// 一键解锁仅 super_admin / admin 可用（与后端 @Roles('super_admin','admin') 对齐）
const canUnlock = computed(() => {
  const role = authStore.adminInfo?.role
  return role === 'super_admin' || role === 'admin'
})

onMounted(async () => {
  // 先取回进度列表：query.merchantId 是否可打开以该列表为准
  await fetchMerchants()
  openDrawerFromQuery()
})

const fetchMerchants = async () => {
  loading.value = true
  try {
    const res = await getMerchantProgressList()
    const rows = res.data || []
    // 按 merchantId 聚合
    const map = new Map<string, MerchantRow>()
    for (const item of rows) {
      const row = map.get(item.merchantId)
      if (row) {
        row.total += 1
        if (item.status === 'completed') row.completed += 1
      } else {
        map.set(item.merchantId, {
          merchantId: item.merchantId,
          total: 1,
          completed: item.status === 'completed' ? 1 : 0,
        })
      }
    }
    merchantRows.value = Array.from(map.values()).sort((a, b) => a.merchantId.localeCompare(b.merchantId))
  } catch (error) {
    console.error('获取商家进度列表失败', error)
  } finally {
    loading.value = false
  }
}

/** 打开详情抽屉：进度明细与商家登记信息各自独立加载（并行，互不阻塞） */
const viewDetail = (merchantId: string) => {
  currentMerchantId.value = merchantId
  drawerVisible.value = true
  detailRows.value = []
  merchantInfo.value = null
  merchantInfoFailed.value = false
  bindingMembers.value = []
  bindingsFailed.value = false
  loadProgressDetail(merchantId)
  loadMerchantInfo(merchantId)
  loadBindings(merchantId)
}

/** 该商家在主表里是否存在（复用 API-17 列表的 keyword 精确检索；不新增接口） */
const merchantExists = async (merchantId: string): Promise<boolean> => {
  try {
    const res = await getAdminMerchantList({ keyword: merchantId, page_size: MERCHANT_INFO_QUERY_PAGE_SIZE })
    return (res.data?.list ?? []).some((item) => item.merchant_id === merchantId)
  } catch (error) {
    console.error('校验商家是否存在失败', error)
    return false
  }
}

/**
 * 从「商家清单」跳转而来时自动打开该商家抽屉（读 route.query.merchantId）。
 * 判定依据是「该商家是否存在」，不是「进度列表里是否有行」——新注册商家通常还没有任务进度行，
 * 而绑定同店账号只能在该抽屉里做，故只要商家存在就必须开抽屉（进度区为空时展示既有空态）。
 * - 不带 query：行为与改动前完全一致（只展示进度聚合列表）；
 * - 带 query 且商家存在（进度列表命中，或主表 keyword 检索命中）：直接开抽屉；
 * - 带 query 但商家不存在：明确提示，不打开抽屉、不留在半开状态。
 */
const openDrawerFromQuery = async () => {
  const target = typeof route.query.merchantId === 'string' ? route.query.merchantId : ''
  if (!target) return
  if (merchantRows.value.some((row) => row.merchantId === target) || (await merchantExists(target))) {
    viewDetail(target)
    return
  }
  ElMessage.warning(MERCHANT_LIST_EMPTY_TEXT)
}

/** 取回同店账号绑定成员（API-22）；未绑定时后端仅返回自身一行 */
const loadBindings = async (merchantId: string) => {
  bindingsLoading.value = true
  bindingsFailed.value = false
  try {
    const res = await getMerchantBindings(merchantId)
    bindingMembers.value = res.data?.members ?? []
  } catch (error) {
    // 错误提示由 request 拦截器按后端 message 统一展示，这里只记日志并给出区块级错误态
    bindingsFailed.value = true
    bindingMembers.value = []
    console.error('获取同店账号绑定失败', error)
  } finally {
    bindingsLoading.value = false
  }
}

/** 打开绑定弹窗：清空关键字与选中项，并先拉一页候选（空关键字 = 列表首页） */
const openBindDialog = () => {
  bindKeyword.value = ''
  selectedCandidate.value = null
  candidateRows.value = []
  bindDialogVisible.value = true
  handleCandidateSearch()
}

/** 候选搜索：复用 API-17 列表接口；剔除当前商家自身（绑定自身必被后端 400 拒绝） */
const handleCandidateSearch = async () => {
  candidateLoading.value = true
  selectedCandidate.value = null
  try {
    const params: AdminMerchantQuery = { page_size: MERCHANT_BINDING_CANDIDATE_PAGE_SIZE }
    const keyword = bindKeyword.value.trim()
    if (keyword) params.keyword = keyword
    const res = await getAdminMerchantList(params)
    candidateRows.value = (res.data?.list ?? []).filter((item) => item.merchant_id !== currentMerchantId.value)
  } catch (error) {
    candidateRows.value = []
    console.error('搜索待绑定账号失败', error)
  } finally {
    candidateLoading.value = false
  }
}

const handleCandidateSelect = (row: AdminMerchantItem | null) => {
  selectedCandidate.value = row
}

/** 绑定：二次确认（文案见设计单 §6.2）→ POST；成功/失败均用后端 message 展示 */
const handleBindConfirm = async () => {
  const target = selectedCandidate.value
  if (!target) {
    ElMessage.warning(MERCHANT_BINDING_SELECTED_REQUIRED_TEXT)
    return
  }
  try {
    await ElMessageBox.confirm(MERCHANT_BINDING_CONFIRM_MESSAGE, MERCHANT_BINDING_CONFIRM_TITLE, {
      confirmButtonText: MERCHANT_BINDING_CONFIRM_OK_TEXT,
      cancelButtonText: MERCHANT_BINDING_CANCEL_TEXT,
      type: 'warning',
    })
  } catch {
    return
  }
  binding.value = true
  try {
    const res = await bindMerchantMember(currentMerchantId.value, target.merchant_id)
    bindDialogVisible.value = false
    ElMessage.success(res.message)
    await loadBindings(currentMerchantId.value)
  } catch (error) {
    // 失败 message（如「该账号已绑定到其它商家」）由 request 拦截器按后端原文展示
    console.error('绑定账号失败', error)
  } finally {
    binding.value = false
  }
}

/** 解绑：二次确认 → DELETE；成功后刷新成员表。
 *  文案分两档（#PB-37-E 语义）：组内仅 2 个账号 ⇒ 解绑任一方即整体解除；>= 3 个账号 ⇒ 组仍在、其余账号继续共享。 */
const handleUnbind = async (row: MerchantBindingMember) => {
  const confirmMessage =
    bindingMembers.value.length <= 2
      ? MERCHANT_BINDING_UNBIND_CONFIRM_MESSAGE_TWO_MEMBERS
      : MERCHANT_BINDING_UNBIND_CONFIRM_MESSAGE
  try {
    await ElMessageBox.confirm(confirmMessage, MERCHANT_BINDING_UNBIND_CONFIRM_TITLE, {
      confirmButtonText: MERCHANT_BINDING_UNBIND_CONFIRM_OK_TEXT,
      cancelButtonText: MERCHANT_BINDING_CANCEL_TEXT,
      type: 'warning',
    })
  } catch {
    return
  }
  unbindingId.value = row.merchant_id
  try {
    const res = await releaseMerchantMember(currentMerchantId.value, row.merchant_id)
    ElMessage.success(res.message)
    await loadBindings(currentMerchantId.value)
  } catch (error) {
    console.error('解绑账号失败', error)
  } finally {
    unbindingId.value = ''
  }
}

/** 普通文本列：空值统一占位（与商家清单页同口径） */
const textOrPlaceholder = (value?: string | null): string =>
  value && value.trim() ? value : MERCHANT_LIST_VALUE_PLACEHOLDER

/** 状态列：merchant.status 数值 → 中文标签（复用商家清单页同一映射） */
const statusText = (value?: number | null): string => {
  if (value === null || value === undefined) return MERCHANT_LIST_VALUE_PLACEHOLDER
  return MERCHANT_STATUS_LABELS[String(value)] ?? String(value)
}

const loadProgressDetail = async (merchantId: string) => {
  detailLoading.value = true
  try {
    const res = await getMerchantProgressDetail(merchantId)
    detailRows.value = res.data || []
  } catch (error) {
    console.error('获取商家进度详情失败', error)
  } finally {
    detailLoading.value = false
  }
}

/**
 * 取回商家登记信息：复用 API-17 主表列表（不改动本页既有的 progress 取数口径）。
 * keyword 为 merchant_id/nickname 的 LIKE 模糊匹配 → 必须在返回集合中按 merchant_id 精确命中。
 */
const loadMerchantInfo = async (merchantId: string) => {
  merchantInfoLoading.value = true
  merchantInfoFailed.value = false
  try {
    const res = await getAdminMerchantList({ keyword: merchantId, page_size: MERCHANT_INFO_QUERY_PAGE_SIZE })
    merchantInfo.value = (res.data?.list || []).find((item) => item.merchant_id === merchantId) ?? null
  } catch (error) {
    merchantInfoFailed.value = true
    console.error('获取商家登记信息失败', error)
  } finally {
    merchantInfoLoading.value = false
  }
}

/** 登记信息展示：加载中→加载态；取数失败→失败态；null/空串→未登记（不显示 null、不隐藏该行） */
const infoFieldText = (value: string | null | undefined): string => {
  if (merchantInfoLoading.value) return MERCHANT_INFO_LOADING_TEXT
  if (merchantInfoFailed.value) return MERCHANT_INFO_FAILED_TEXT
  return value && value.trim() ? value : MERCHANT_INFO_UNREGISTERED_TEXT
}

const handleUnlock = async (merchantId: string) => {
  await ElMessageBox.confirm(`确定一键解锁商家「${merchantId}」的阶段一吗？解锁后阶段二永久开放。`, '提示', {
    type: 'warning',
  })
  unlockingId.value = merchantId
  try {
    await unlockMerchantPhase1(merchantId)
    ElMessage.success('解锁成功')
  } catch (error) {
    console.error('解锁失败', error)
  } finally {
    unlockingId.value = ''
  }
}

const formatTime = (t: string | null) => {
  if (!t) return '—'
  const d = new Date(t)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.merchant-info {
  margin-bottom: 16px;
}

.binding-section {
  margin-top: 24px;
}

.binding-section__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.binding-section__title {
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.binding-section__bind-wrap {
  display: inline-flex;
}

.binding-section__hint {
  margin-bottom: 12px;
}

.binding-self-tag {
  margin-left: 8px;
}

.bind-search {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.empty-tip {
  text-align: center;
  color: var(--el-text-color-secondary);
  padding: 24px 0;
  font-size: 13px;
}
</style>
