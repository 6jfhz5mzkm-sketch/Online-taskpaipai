<template>
  <div class="second-level-task-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>二级任务管理</span>
          <div class="header-right">
            <el-select v-model="filterFirstLevelTaskId" placeholder="筛选一级任务" clearable @change="handleFilter">
              <el-option
                v-for="task in taskStore.firstLevelTasks"
                :key="task.taskId"
                :label="task.title"
                :value="task.taskId"
              />
            </el-select>
            <el-button type="primary" @click="handleAdd">
              <el-icon><Plus /></el-icon>
              新增二级任务
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="taskStore.secondLevelTasks" v-loading="taskStore.loading" stripe>
        <el-table-column prop="taskId" label="任务ID" width="120" />
        <el-table-column prop="title" label="任务标题" />
        <el-table-column prop="firstLevelTaskId" label="所属一级任务" width="140" />
        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getTypeTag(row.type)">{{ getTypeLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="completionType" label="完成方式" width="120">
          <template #default="{ row }">
            {{ getCompletionTypeLabel(row.completionType) }}
          </template>
        </el-table-column>
        <!-- 行为类型只读展示（#AF-20；none 用占位，data_* 附带参数便于核对「哪个表单/哪种上传」） -->
        <el-table-column :label="ACTION_TYPE_COLUMN_LABEL" width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <template v-if="row.actionType && row.actionType !== 'none'">
              {{ actionTypeText(row) }}
            </template>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="tag" label="标签" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.tag" size="small" type="info">{{ row.tag }}</el-tag>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="defaultCompleted" label="默认完成" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.defaultCompleted === 1" size="small" type="warning">默认完成</el-tag>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="sortOrder" label="排序" width="80" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'">
              {{ row.status === 1 ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-button type="info" link @click="handleDetail(row)">详情</el-button>
            <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Plus } from '@element-plus/icons-vue'
import { useTaskStore } from '@/store/modules/task'
import { ElMessageBox } from 'element-plus'
import type { SecondLevelTask } from '@/api/second-level-task'
import {
  ACTION_TYPE_COLUMN_LABEL,
  ACTION_TYPE_LABELS,
  COMPLETION_TYPE_LABELS,
  TASK_TYPE_LABELS,
} from '@/constants/second-level-task'

const taskStore = useTaskStore()
const router = useRouter()
const filterFirstLevelTaskId = ref('')

onMounted(() => {
  taskStore.fetchFirstLevelTasks()
  taskStore.fetchSecondLevelTasks()
})

const handleFilter = () => {
  taskStore.fetchSecondLevelTasks(filterFirstLevelTaskId.value || undefined)
}

const handleAdd = () => {
  router.push('/second-level-task/edit')
}

const handleEdit = (row: SecondLevelTask) => {
  router.push(`/second-level-task/edit/${row.id}`)
}

const handleDetail = (row: SecondLevelTask) => {
  router.push(`/second-level-task/edit/${row.id}`)
}

const handleDelete = async (row: SecondLevelTask) => {
  await ElMessageBox.confirm('确定删除该二级任务吗？', '提示', {
    type: 'warning',
  })
  await taskStore.removeSecondLevelTask(row.id)
}

const getTypeTag = (type: string) => {
  const map: Record<string, string> = {
    mandatory: 'danger',
    suggested: 'warning',
    guide: 'success',
  }
  return map[type] || 'info'
}

/** 任务类型文案：与编辑页共用同一份常量（#AF-21）；未知取值如实显示原值，不隐藏、不静默改默认 */
const getTypeLabel = (type: string) => TASK_TYPE_LABELS[type] ?? type

/** 行为类型只读文案：none 由模板占位；data_* 附带参数；未知取值回退原值（不隐藏） */
const actionTypeText = (row: SecondLevelTask) => {
  const label = ACTION_TYPE_LABELS[row.actionType] ?? row.actionType
  return row.actionParam ? `${label}（${row.actionParam}）` : label
}

/** 完成方式文案：与编辑页共用同一份常量（#AF-21）；未知取值如实显示原值 */
const getCompletionTypeLabel = (type: string) => COMPLETION_TYPE_LABELS[type] ?? type
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-right {
  display: flex;
  gap: 12px;
}

.muted {
  color: var(--el-text-color-secondary);
}
</style>
