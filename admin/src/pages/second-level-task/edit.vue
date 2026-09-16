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
                <el-option label="必做" value="mandatory" />
                <el-option label="建议" value="suggested" />
                <el-option label="引导" value="guide" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="完成方式" prop="completionType">
              <el-select v-model="form.completionType" placeholder="请选择完成方式">
                <el-option label="点击已读" value="click_read" />
                <el-option label="手动提交" value="manual_submit" />
                <el-option label="系统检测（兼容旧任务）" value="system_check" />
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
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'
import { useTaskStore } from '@/store/modules/task'
import { useStageStore } from '@/store/modules/stage'
import { getSecondLevelTaskDetail } from '@/api/second-level-task'
import { ElMessage } from 'element-plus'

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
  tag: '',
  defaultCompleted: 0,
  sortOrder: 0,
})

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

const handleSubmit = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    
    submitting.value = true
    try {
      if (isEdit.value) {
        await taskStore.modifySecondLevelTask(Number(route.params.id), form)
      } else {
        await taskStore.addSecondLevelTask(form)
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
