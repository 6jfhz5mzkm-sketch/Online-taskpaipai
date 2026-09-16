import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getFirstLevelTaskList, createFirstLevelTask, updateFirstLevelTask, deleteFirstLevelTask } from '@/api/first-level-task'
import { getSecondLevelTaskList, createSecondLevelTask, updateSecondLevelTask, deleteSecondLevelTask } from '@/api/second-level-task'
import type { FirstLevelTask, CreateFirstLevelTaskParams } from '@/api/first-level-task'
import type { SecondLevelTask, CreateSecondLevelTaskParams } from '@/api/second-level-task'
import { ElMessage } from 'element-plus'

export const useTaskStore = defineStore('task', () => {
  const firstLevelTasks = ref<FirstLevelTask[]>([])
  const secondLevelTasks = ref<SecondLevelTask[]>([])
  const loading = ref(false)

  // 获取一级任务列表
  async function fetchFirstLevelTasks(stageId?: string) {
    loading.value = true
    try {
      const res = await getFirstLevelTaskList(stageId)
      firstLevelTasks.value = res.data
    } catch (error) {
      console.error('获取一级任务列表失败', error)
    } finally {
      loading.value = false
    }
  }

  // 创建一级任务
  async function addFirstLevelTask(data: CreateFirstLevelTaskParams) {
    try {
      await createFirstLevelTask(data)
      ElMessage.success('创建成功')
      await fetchFirstLevelTasks()
    } catch (error) {
      ElMessage.error('创建失败')
      throw error
    }
  }

  // 更新一级任务
  async function modifyFirstLevelTask(id: number, data: Partial<CreateFirstLevelTaskParams>) {
    try {
      await updateFirstLevelTask(id, data)
      ElMessage.success('更新成功')
      await fetchFirstLevelTasks()
    } catch (error) {
      ElMessage.error('更新失败')
      throw error
    }
  }

  // 删除一级任务
  async function removeFirstLevelTask(id: number) {
    try {
      await deleteFirstLevelTask(id)
      ElMessage.success('删除成功')
      await fetchFirstLevelTasks()
    } catch (error) {
      ElMessage.error('删除失败')
      throw error
    }
  }

  // 获取二级任务列表
  async function fetchSecondLevelTasks(firstLevelTaskId?: string, stageId?: string) {
    loading.value = true
    try {
      const res = await getSecondLevelTaskList(firstLevelTaskId, stageId)
      secondLevelTasks.value = res.data
    } catch (error) {
      console.error('获取二级任务列表失败', error)
    } finally {
      loading.value = false
    }
  }

  // 创建二级任务
  async function addSecondLevelTask(data: CreateSecondLevelTaskParams) {
    try {
      await createSecondLevelTask(data)
      ElMessage.success('创建成功')
      await fetchSecondLevelTasks()
    } catch (error) {
      ElMessage.error('创建失败')
      throw error
    }
  }

  // 更新二级任务
  async function modifySecondLevelTask(id: number, data: Partial<CreateSecondLevelTaskParams>) {
    try {
      await updateSecondLevelTask(id, data)
      ElMessage.success('更新成功')
      await fetchSecondLevelTasks()
    } catch (error) {
      ElMessage.error('更新失败')
      throw error
    }
  }

  // 删除二级任务
  async function removeSecondLevelTask(id: number) {
    try {
      await deleteSecondLevelTask(id)
      ElMessage.success('删除成功')
      await fetchSecondLevelTasks()
    } catch (error) {
      ElMessage.error('删除失败')
      throw error
    }
  }

  return {
    firstLevelTasks,
    secondLevelTasks,
    loading,
    fetchFirstLevelTasks,
    addFirstLevelTask,
    modifyFirstLevelTask,
    removeFirstLevelTask,
    fetchSecondLevelTasks,
    addSecondLevelTask,
    modifySecondLevelTask,
    removeSecondLevelTask,
  }
})
