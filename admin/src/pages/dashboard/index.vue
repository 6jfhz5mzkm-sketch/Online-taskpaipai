<template>
  <div class="dashboard">
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>
            <span>阶段总数</span>
          </template>
          <div class="card-content">{{ stageCount }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>
            <span>一级任务总数</span>
          </template>
          <div class="card-content">{{ firstLevelTaskCount }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>
            <span>二级任务总数</span>
          </template>
          <div class="card-content">{{ secondLevelTaskCount }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <template #header>
            <span>管理员数量</span>
          </template>
          <div class="card-content">{{ accountCount }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="welcome-card" shadow="never">
      <template #header>
        <span>欢迎使用任务管理后台</span>
      </template>
      <div class="welcome-content">
        <p>本系统用于管理京东拍拍二手商家成长任务体系的任务配置。</p>
        <p>您可以在此配置一级/二级任务、处理商家反馈、查看经营数据，并管理后台账号。</p>
        <el-divider />
        <p><strong>快速开始：</strong></p>
        <ul class="quick-links">
          <li v-for="link in visibleQuickLinks" :key="link.path">
            <router-link :to="link.path" class="quick-link">
              前往「{{ link.label }}」{{ link.desc }}
              <el-icon class="quick-link-icon"><Right /></el-icon>
            </router-link>
          </li>
        </ul>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/store/modules/auth'
import { Right } from '@element-plus/icons-vue'
import { getStageList } from '@/api/stage'
import { getFirstLevelTaskList } from '@/api/first-level-task'
import { getSecondLevelTaskList } from '@/api/second-level-task'
import { getAccountList } from '@/api/account'
import {
  MERCHANT_LIST_QUICK_DESC,
  MERCHANT_LIST_TITLE,
  MERCHANT_PROGRESS_QUICK_DESC,
  MERCHANT_PROGRESS_TITLE,
} from '@/constants/merchant'

interface QuickLink {
  path: string
  label: string
  desc: string
  // 空 = 所有登录管理员可见；否则仅指定角色可见（与侧边栏权限一致）
  roles?: string[]
}

const authStore = useAuthStore()

const quickLinks: QuickLink[] = [
  { path: '/first-level-task', label: '一级任务管理', desc: '配置任务主题' },
  { path: '/second-level-task', label: '二级任务管理', desc: '配置具体任务' },
  { path: '/feedback', label: '反馈处理', desc: '处理商家反馈', roles: ['super_admin', 'admin'] },
  { path: '/merchant-list', label: MERCHANT_LIST_TITLE, desc: MERCHANT_LIST_QUICK_DESC },
  { path: '/merchant-progress', label: MERCHANT_PROGRESS_TITLE, desc: MERCHANT_PROGRESS_QUICK_DESC },
]

// 按当前管理员角色过滤入口（与 Layout 侧边栏权限口径一致）
const visibleQuickLinks = computed(() => {
  const role = authStore.adminInfo?.role
  return quickLinks.filter((link) => !link.roles || (role && link.roles.includes(role)))
})

const stageCount = ref(0)
const firstLevelTaskCount = ref(0)
const secondLevelTaskCount = ref(0)
const accountCount = ref(0)

onMounted(async () => {
  try {
    const [stageRes, firstRes, secondRes, accountRes] = await Promise.all([
      getStageList(),
      getFirstLevelTaskList(),
      getSecondLevelTaskList(),
      getAccountList(),
    ])
    stageCount.value = stageRes.data.length
    firstLevelTaskCount.value = firstRes.data.length
    secondLevelTaskCount.value = secondRes.data.length
    accountCount.value = accountRes.data.length
  } catch (error) {
    console.error('获取统计数据失败', error)
  }
})
</script>

<style scoped>
.dashboard {
  padding: 0;
}

.card-content {
  font-size: 32px;
  font-weight: 600;
  color: var(--el-color-primary);
  text-align: center;
  font-family: var(--font-family-number);
  line-height: 1.4;
}

.welcome-content strong {
  color: var(--el-text-color-primary);
}

.welcome-card {
  margin-top: 20px;
}

.welcome-content {
  color: var(--el-text-color-regular);
  line-height: 1.8;
}

.welcome-content .quick-links {
  list-style: none;
  padding-left: 0;
  margin: 0;
}

.welcome-content .quick-links li {
  margin-bottom: 8px;
}

.quick-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--el-color-primary);
  text-decoration: none;
  font-size: 14px;
  transition: color 0.2s ease;
  cursor: pointer;
}

.quick-link:hover {
  color: var(--el-color-primary-dark-2);
  text-decoration: underline;
  text-underline-offset: 4px;
}

.quick-link-icon {
  font-size: 12px;
}
</style>
