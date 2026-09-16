<template>
  <div class="feedback-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>反馈处理</span>
        </div>
      </template>

      <!-- 筛选区 -->
      <div class="filter-bar">
        <el-select v-model="query.status" placeholder="状态筛选" clearable style="width: 150px" @change="handleSearch">
          <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-select v-model="query.category" placeholder="分类筛选" clearable style="width: 150px" @change="handleSearch">
          <el-option v-for="c in categoryOptions" :key="c" :label="c" :value="c" />
        </el-select>
        <el-button type="primary" @click="handleSearch">
          <el-icon><Search /></el-icon>
          查询
        </el-button>
        <el-button @click="handleReset">重置</el-button>
      </div>

      <el-table :data="feedbackList" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="merchantId" label="商家ID" width="140" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="110">
          <template #default="{ row }">
            <el-tag :type="getCategoryTag(row.category)">{{ row.category }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="反馈内容" min-width="200" show-overflow-tooltip />
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="getStatusTag(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="adminReply" label="管理员回复" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.adminReply">{{ row.adminReply }}</span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="提交时间" width="170">
          <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleHandle(row)">处理</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页：与后端 page/page_size 对齐 -->
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.page_size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSearch"
          @current-change="handleSearch"
        />
      </div>
    </el-card>

    <!-- 处理反馈弹窗 -->
    <el-dialog v-model="handleVisible" title="处理反馈" width="560px" :close-on-click-modal="false">
      <el-form ref="handleFormRef" :model="handleForm" :rules="handleRules" label-width="90px">
        <el-form-item label="反馈内容">
          <div class="feedback-content">{{ currentFeedback?.content }}</div>
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="handleForm.status" style="width: 200px">
            <el-option v-for="s in statusOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="管理员回复" prop="adminReply">
          <el-input
            v-model="handleForm.adminReply"
            type="textarea"
            :rows="4"
            maxlength="1000"
            show-word-limit
            placeholder="填写给商家的回复内容"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="handleVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getFeedbackList, handleFeedback, FEEDBACK_CATEGORIES, FEEDBACK_STATUSES } from '@/api/feedback'
import type { Feedback } from '@/api/feedback'

const loading = ref(false)
const submitting = ref(false)
const feedbackList = ref<Feedback[]>([])
const total = ref(0)
const handleVisible = ref(false)
const handleFormRef = ref<FormInstance>()
const currentFeedback = ref<Feedback | null>(null)

// 状态选项由后端枚举派生，避免硬编码漂移
const STATUS_LABELS: Record<string, string> = {
  pending: '待处理',
  processing: '处理中',
  resolved: '已解决',
}
const statusOptions = FEEDBACK_STATUSES.map((s) => ({ value: s, label: STATUS_LABELS[s] || s }))
const categoryOptions = [...FEEDBACK_CATEGORIES]

const query = reactive({
  status: '',
  category: '',
  page: 1,
  page_size: 20,
})

const handleForm = reactive({
  status: 'pending',
  adminReply: '',
})

const handleRules: FormRules = {
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
}

onMounted(() => {
  fetchList()
})

const fetchList = async () => {
  loading.value = true
  try {
    const params: Record<string, string | number> = { page: query.page, page_size: query.page_size }
    if (query.status) params.status = query.status
    if (query.category) params.category = query.category
    const res = await getFeedbackList(params)
    feedbackList.value = res.data.list || []
    total.value = res.data.total || 0
  } catch (error) {
    console.error('获取反馈列表失败', error)
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  query.page = 1
  fetchList()
}

const handleReset = () => {
  query.status = ''
  query.category = ''
  handleSearch()
}

const handleHandle = (row: Feedback) => {
  currentFeedback.value = row
  handleForm.status = row.status || 'pending'
  handleForm.adminReply = row.adminReply || ''
  handleVisible.value = true
}

const handleSubmit = async () => {
  if (!handleFormRef.value || !currentFeedback.value) return

  await handleFormRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      await handleFeedback(currentFeedback.value!.id, {
        status: handleForm.status,
        adminReply: handleForm.adminReply,
      })
      ElMessage.success('处理成功')
      handleVisible.value = false
      fetchList()
    } catch (error) {
      console.error('处理反馈失败', error)
    } finally {
      submitting.value = false
    }
  })
}

const getStatusLabel = (status: string) => {
  return STATUS_LABELS[status] || status
}

// 分类 Tag 多色（规范：蓝/橙/红/灰）
const getCategoryTag = (category: string) => {
  const map: Record<string, string> = {
    '功能建议': 'primary',
    '使用问题': 'warning',
    '任务异常': 'danger',
    '其他': 'info',
  }
  return map[category] || 'info'
}

const getStatusTag = (status: string) => {
  const map: Record<string, string> = { pending: 'warning', processing: 'primary', resolved: 'success' }
  return map[status] || 'info'
}

const formatTime = (t: string) => {
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

.filter-bar {
  display: flex;
  gap: 16px;
  margin-bottom: 16px;
}

.pagination-wrap {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.feedback-content {
  width: 100%;
  padding: 8px 16px;
  background-color: #f5f7fa;
  border-radius: 4px;
  color: var(--el-text-color-regular);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 120px;
  overflow-y: auto;
}

.muted {
  color: var(--el-text-color-secondary);
}
</style>
