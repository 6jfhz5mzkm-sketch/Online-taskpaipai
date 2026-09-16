import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getStageList, createStage, updateStage, deleteStage } from '@/api/stage'
import type { Stage, CreateStageParams } from '@/api/stage'
import { ElMessage } from 'element-plus'

export const useStageStore = defineStore('stage', () => {
  const stages = ref<Stage[]>([])
  const loading = ref(false)

  // 获取阶段列表
  async function fetchStages() {
    loading.value = true
    try {
      const res = await getStageList()
      stages.value = res.data
    } catch (error) {
      console.error('获取阶段列表失败', error)
    } finally {
      loading.value = false
    }
  }

  // 创建阶段
  async function addStage(data: CreateStageParams) {
    try {
      await createStage(data)
      ElMessage.success('创建成功')
      await fetchStages()
    } catch (error) {
      ElMessage.error('创建失败')
      throw error
    }
  }

  // 更新阶段
  async function modifyStage(id: number, data: Partial<CreateStageParams>) {
    try {
      await updateStage(id, data)
      ElMessage.success('更新成功')
      await fetchStages()
    } catch (error) {
      ElMessage.error('更新失败')
      throw error
    }
  }

  // 删除阶段
  async function removeStage(id: number) {
    try {
      await deleteStage(id)
      ElMessage.success('删除成功')
      await fetchStages()
    } catch (error) {
      ElMessage.error('删除失败')
      throw error
    }
  }

  return { stages, loading, fetchStages, addStage, modifyStage, removeStage }
})
