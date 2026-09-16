<!-- 一级任务管理：按大阶段分组展示（阶段一/阶段二，组内按 sortOrder 排序） -->
<template>
  <div class="first-level-task-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>一级任务管理</span>
          <el-button type="primary" @click="handleAdd">
            <el-icon><Plus /></el-icon>
            新增一级任务
          </el-button>
        </div>
      </template>

      <!-- 分组一：阶段一（phaseNum=1） -->
      <div class="phase-group">
        <div class="phase-title">
          <el-tag type="primary" effect="light">{{ phase1.title }}</el-tag>
          <span class="phase-count">{{ phase1.tasks.length }} 个任务</span>
        </div>
        <el-table :data="phase1.tasks" v-loading="loading" stripe>
          <el-table-column prop="taskId" label="任务ID" width="120" />
          <el-table-column prop="title" label="任务标题" />
          <el-table-column prop="stageId" label="所属阶段" width="150">
            <template #default="{ row }">{{ getStageTitle(row.stageId) }}</template>
          </el-table-column>
          <el-table-column prop="buttonText" label="按钮文案" width="120" />
          <el-table-column prop="sortOrder" label="排序" width="80" />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.status === 1 ? 'success' : 'danger'">
                {{ row.status === 1 ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
              <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 分组二：阶段二（phaseNum=2） -->
      <div class="phase-group">
        <div class="phase-title">
          <el-tag type="success" effect="light">{{ phase2.title }}</el-tag>
          <span class="phase-count">{{ phase2.tasks.length }} 个任务</span>
        </div>
        <el-table :data="phase2.tasks" v-loading="loading" stripe>
          <el-table-column prop="taskId" label="任务ID" width="120" />
          <el-table-column prop="title" label="任务标题" />
          <el-table-column prop="stageId" label="所属阶段" width="150">
            <template #default="{ row }">{{ getStageTitle(row.stageId) }}</template>
          </el-table-column>
          <el-table-column prop="buttonText" label="按钮文案" width="120" />
          <el-table-column prop="sortOrder" label="排序" width="80" />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="row.status === 1 ? 'success' : 'danger'">
                {{ row.status === 1 ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button type="primary" link @click="handleEdit(row)">编辑</el-button>
              <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <el-alert
        v-if="unknownTasks.length > 0"
        type="warning"
        :closable="false"
        show-icon
        :title="`有 ${unknownTasks.length} 个任务未匹配到阶段配置（stageId 不在阶段列表中），未纳入分组展示`"
      />
    </el-card>

    <!-- 新增/编辑弹窗（两级：先选大阶段，再选具体阶段） -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑一级任务' : '新增一级任务'"
      width="520px"
      :close-on-click-modal="false"
      @closed="formRef?.clearValidate()"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="任务ID" prop="taskId">
          <el-input v-model="form.taskId" :disabled="isEdit" placeholder="如 T1.1 / T2.1" />
        </el-form-item>
        <el-form-item label="所属大阶段" prop="phaseNum">
          <el-radio-group v-model="form.phaseNum" @change="handlePhaseChange">
            <el-radio :value="1">阶段一</el-radio>
            <el-radio :value="2">阶段二</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="所属阶段" prop="stageId">
          <el-select
            v-model="form.stageId"
            placeholder="请选择所属大阶段下的阶段"
            style="width: 100%"
            :disabled="!form.phaseNum"
          >
            <el-option-group
              v-for="group in filteredStages"
              :key="group.label"
              :label="group.label"
            >
              <el-option
                v-for="stage in group.stages"
                :key="stage.stageId"
                :label="`${stage.stageNum}. ${stage.title}`"
                :value="stage.stageId"
              />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="任务标题" prop="title">
          <el-input v-model="form.title" placeholder="如 模式选择与认知" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="按钮文案">
          <el-input v-model="form.buttonText" placeholder="如 我已了解" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sortOrder" :min="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useTaskStore } from '@/store/modules/task'
import { useStageStore } from '@/store/modules/stage'
import { ElMessageBox } from 'element-plus'
import type { FirstLevelTask } from '@/api/first-level-task'
import type { Stage } from '@/api/stage'

interface PhaseGroup {
  title: string
  tasks: FirstLevelTask[]
}

const taskStore = useTaskStore()
const stageStore = useStageStore()
const formRef = ref<FormInstance>()
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const editId = ref<number>(0)

const form = reactive({
  taskId: '',
  phaseNum: 1,
  stageId: '',
  title: '',
  description: '',
  buttonText: '',
  sortOrder: 0,
})

const rules: FormRules = {
  taskId: [{ required: true, message: '请输入任务ID', trigger: 'blur' }],
  phaseNum: [{ required: true, message: '请选择所属大阶段', trigger: 'change' }],
  stageId: [{ required: true, message: '请选择所属阶段', trigger: 'change' }],
  title: [{ required: true, message: '请输入任务标题', trigger: 'blur' }],
}

const loading = computed(() => taskStore.loading || stageStore.loading)

// 阶段列表按大阶段分组（供下拉两级选择）
const stagesByPhase = (phaseNum: number) =>
  stageStore.stages
    .filter((s) => s.phaseNum === phaseNum)
    .sort((a, b) => a.stageNum - b.stageNum)

const filteredStages = computed(() => {
  const groups: { label: string; stages: Stage[] }[] = []
  const g1 = stagesByPhase(1)
  const g2 = stagesByPhase(2)
  if (g1.length > 0) groups.push({ label: '阶段一（入驻准备）', stages: g1 })
  if (g2.length > 0) groups.push({ label: '阶段二（开店搭建）', stages: g2 })
  return groups
})

// 展示用分组：任务按 stageId → phaseNum 归组，组内按 sortOrder 升序
const makePhaseGroup = (phaseNum: number): PhaseGroup => {
  const stageIds = new Set(stagesByPhase(phaseNum).map((s) => s.stageId))
  const tasks = taskStore.firstLevelTasks
    .filter((t) => stageIds.has(t.stageId))
    .sort((a, b) => a.sortOrder - b.sortOrder)
  const firstStage = stagesByPhase(phaseNum)[0]
  const phaseName = phaseNum === 1 ? '阶段一' : '阶段二'
  const subTitle = firstStage ? firstStage.title : ''
  return { title: subTitle ? `${phaseName} · ${subTitle}` : phaseName, tasks }
}

const phase1 = computed<PhaseGroup>(() => makePhaseGroup(1))
const phase2 = computed<PhaseGroup>(() => makePhaseGroup(2))

// 未匹配到阶段配置的任务（stageId 不在阶段列表中），提示运营
const unknownTasks = computed(() => {
  const known = new Set(stageStore.stages.map((s) => s.stageId))
  return taskStore.firstLevelTasks.filter((t) => !known.has(t.stageId))
})

const getStageTitle = (stageId: string) => {
  const s = stageStore.stages.find((item) => item.stageId === stageId)
  return s ? s.title : stageId
}

// 切换大阶段时清空已选阶段
const handlePhaseChange = () => {
  form.stageId = ''
}

onMounted(async () => {
  await Promise.all([stageStore.fetchStages(), taskStore.fetchFirstLevelTasks()])
})

const handleAdd = () => {
  isEdit.value = false
  editId.value = 0
  form.taskId = ''
  form.phaseNum = 1
  form.stageId = ''
  form.title = ''
  form.description = ''
  form.buttonText = ''
  form.sortOrder = 0
  dialogVisible.value = true
}

const handleEdit = (row: FirstLevelTask) => {
  isEdit.value = true
  editId.value = row.id
  form.taskId = row.taskId
  const stage = stageStore.stages.find((s) => s.stageId === row.stageId)
  form.phaseNum = stage?.phaseNum || 1
  form.stageId = row.stageId
  form.title = row.title
  form.description = row.description
  form.buttonText = row.buttonText
  form.sortOrder = row.sortOrder
  dialogVisible.value = true
}

const handleDelete = async (row: FirstLevelTask) => {
  await ElMessageBox.confirm('确定删除该一级任务吗？', '提示', {
    type: 'warning',
  })
  await taskStore.removeFirstLevelTask(row.id)
}

const handleSubmit = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    submitting.value = true
    try {
      const payload = {
        taskId: form.taskId,
        stageId: form.stageId,
        title: form.title,
        description: form.description,
        buttonText: form.buttonText,
        sortOrder: form.sortOrder,
      }
      if (isEdit.value) {
        await taskStore.modifyFirstLevelTask(editId.value, payload)
      } else {
        await taskStore.addFirstLevelTask(payload)
      }
      dialogVisible.value = false
    } catch (error) {
      console.error('操作失败', error)
    } finally {
      submitting.value = false
    }
  })
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.phase-group {
  margin-bottom: 16px;
}

.phase-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.phase-count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
