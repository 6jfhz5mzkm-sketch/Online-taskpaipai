<template>
  <div class="edit-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>{{ isEdit ? '编辑二级任务' : '新增二级任务' }}</span>
          <el-button @click="router.back()">返回</el-button>
        </div>
      </template>

      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px" v-loading="loading">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="任务ID" prop="taskId">
              <el-input v-model="form.taskId" :disabled="isEdit" placeholder="如 T1.1.1" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属一级任务" prop="firstLevelTaskId">
              <el-select v-model="form.firstLevelTaskId" placeholder="请选择一级任务">
                <el-option
                  v-for="task in taskStore.firstLevelTasks"
                  :key="task.taskId"
                  :label="task.title"
                  :value="task.taskId"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="所属阶段" prop="stageId">
              <el-select v-model="form.stageId" placeholder="请选择阶段">
                <el-option
                  v-for="stage in stageStore.stages"
                  :key="stage.stageId"
                  :label="stage.title"
                  :value="stage.stageId"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="任务标题" prop="title">
              <el-input v-model="form.title" placeholder="如 了解POP模式" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="任务描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="任务类型" prop="type">
              <el-select v-model="form.type" placeholder="请选择类型">
                <el-option v-for="item in typeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="完成方式" prop="completionType">
              <el-select v-model="form.completionType" placeholder="请选择完成方式">
                <el-option
                  v-for="item in completionTypeOptions"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="操作按钮文案">
              <el-input v-model="form.actionText" placeholder="如 去看看" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="操作按钮链接">
              <el-input v-model="form.actionUrl" placeholder="https://..." />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 行为类型 / 行为参数（#AF-20；契约真源 project/docs/后端技术方案.md §8.3.9） -->
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item :label="ACTION_TYPE_FIELD_LABEL" prop="actionType">
              <el-select v-model="form.actionType" @change="handleActionTypeChange">
                <el-option
                  v-for="item in ACTION_TYPE_OPTIONS"
                  :key="item.value"
                  :label="item.label"
                  :value="item.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="ACTION_PARAM_FIELD_LABEL" prop="actionParam">
              <el-input v-model="form.actionParam" :disabled="!actionParamEditable" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="标签">
              <el-input v-model="form.tag" placeholder="如 引导 / 上传 / 必做" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="默认已完成">
              <el-switch
                v-model="form.defaultCompleted"
                :active-value="1"
                :inactive-value="0"
                active-text="是（存量商家按已完成计入）"
                inactive-text="否"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="任务详情">
          <el-input v-model="form.detail" type="textarea" :rows="8" placeholder="支持Markdown格式" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
          <el-button @click="router.back()">取消</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { useTaskStore } from '@/store/modules/task'
import { useStageStore } from '@/store/modules/stage'
import { getSecondLevelTaskDetail } from '@/api/second-level-task'
import type { CreateSecondLevelTaskParams } from '@/api/second-level-task'
import type { SelectOption } from '@/constants/second-level-task'
import { ElMessage } from 'element-plus'
import {
  ACTION_PAIR_VALIDATION_MESSAGE,
  COMPLETION_TYPE_OPTIONS,
  TASK_TYPE_OPTIONS,
  ACTION_PARAM_FIELD_LABEL,
  ACTION_PARAM_REQUIRED_TYPES,
  ACTION_TYPE_DEFAULT,
  ACTION_TYPE_FIELD_LABEL,
  ACTION_TYPE_LABELS,
  ACTION_TYPE_OPTIONS,
} from '@/constants/second-level-task'

const route = useRoute()
const router = useRouter()
const taskStore = useTaskStore()
const stageStore = useStageStore()
const formRef = ref<FormInstance>()
const loading = ref(false)
const submitting = ref(false)
const isEdit = ref(false)

const form = reactive({
  taskId: '',
  firstLevelTaskId: '',
  stageId: '',
  title: '',
  description: '',
  detail: '',
  type: 'guide',
  completionType: 'click_read',
  actionText: '',
  actionUrl: '',
  actionType: ACTION_TYPE_DEFAULT,
  actionParam: '',
  tag: '',
  defaultCompleted: 0,
  sortOrder: 0,
})

/**
 * 下拉项 + 「库内未知值」兜底：库里若出现下拉之外的取值，追加一项「原值」选项，
 * 保证如实显示原值（不静默改成默认值）且提交时原值不丢（#AF-21 范围 3）。
 */
const withUnknownOption = (options: readonly SelectOption[], value: string): SelectOption[] =>
  value && !options.some((item) => item.value === value) ? [...options, { value, label: value }] : [...options]

const typeOptions = computed(() => withUnknownOption(TASK_TYPE_OPTIONS, form.type))
const completionTypeOptions = computed(() => withUnknownOption(COMPLETION_TYPE_OPTIONS, form.completionType))

/** 仅 data_form / data_upload 可编辑「行为参数」（与后端 §8.3.9 参数规则同口径） */
const actionParamEditable = computed(() => ACTION_PARAM_REQUIRED_TYPES.includes(form.actionType))

/** 切到非 data_* 行为：自动清空参数并禁用输入（避免「其余行为必须为空」被后端 400） */
const handleActionTypeChange = (value: string) => {
  if (!ACTION_PARAM_REQUIRED_TYPES.includes(value)) {
    form.actionParam = ''
  }
}

const rules: FormRules = {
  taskId: [{ required: true, message: '请输入任务ID', trigger: 'blur' }],
  firstLevelTaskId: [{ required: true, message: '请选择一级任务', trigger: 'change' }],
  stageId: [{ required: true, message: '请选择阶段', trigger: 'change' }],
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  completionType: [{ required: true, message: '请选择完成方式', trigger: 'change' }],
}

onMounted(async () => {
  await stageStore.fetchStages()
  await taskStore.fetchFirstLevelTasks()
  
  const id = route.params.id
  if (id) {
    isEdit.value = true
    loading.value = true
    try {
      const res = await getSecondLevelTaskDetail(Number(id))
      const data = res.data
      form.taskId = data.taskId
      form.firstLevelTaskId = data.firstLevelTaskId
      form.stageId = data.stageId
      form.title = data.title
      form.description = data.description
      form.detail = data.detail
      form.type = data.type
      form.completionType = data.completionType
      form.actionText = data.actionText
      form.actionUrl = data.actionUrl
      // 降级：actionType 缺失/为空/未知取值一律按 none 处理（留 console.warn 便于排查，不新增用户可见文案）
      const rawActionType = data.actionType
      if (rawActionType && !ACTION_TYPE_LABELS[rawActionType]) {
        console.warn('未知 actionType，按 none 处理：', rawActionType)
      }
      const actionType = rawActionType && ACTION_TYPE_LABELS[rawActionType] ? rawActionType : ACTION_TYPE_DEFAULT
      form.actionType = actionType
      form.actionParam = ACTION_PARAM_REQUIRED_TYPES.includes(actionType) ? data.actionParam ?? '' : ''
      form.tag = data.tag
      form.defaultCompleted = data.defaultCompleted || 0
      form.sortOrder = data.sortOrder
    } catch (error) {
      ElMessage.error('获取任务详情失败')
      router.back()
    } finally {
      loading.value = false
    }
  }
})

/**
 * 提交前本地校验（与后端 §8.3.9 参数规则同口径，减少无效请求）：
 * data_form / data_upload 必须带非空参数；其余 8 个行为必须为空。
 * 提示复用后端统一校验出口原文（不新增同义句）。
 */
const validateActionPair = (): boolean => {
  const param = form.actionParam.trim()
  const required = ACTION_PARAM_REQUIRED_TYPES.includes(form.actionType)
  if (required === Boolean(param)) return true
  ElMessage.warning(ACTION_PAIR_VALIDATION_MESSAGE)
  return false
}

/** 提交体：非 data_* 行为显式送 actionParam = null（后端要求「必须为空」，空串不算清空语义） */
const buildSubmitPayload = (): Partial<CreateSecondLevelTaskParams> => ({
  ...form,
  actionParam: actionParamEditable.value ? form.actionParam.trim() : null,
})

const handleSubmit = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    
    if (!validateActionPair()) return

    const payload = buildSubmitPayload()
    submitting.value = true
    try {
      if (isEdit.value) {
        await taskStore.modifySecondLevelTask(Number(route.params.id), payload)
      } else {
        await taskStore.addSecondLevelTask(payload as CreateSecondLevelTaskParams)
      }
      ElMessage.success('保存成功')
      router.back()
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
</style>
