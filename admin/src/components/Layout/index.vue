<template>
  <el-container class="layout-container">
    <!-- 侧边栏 -->
    <el-aside width="200px" class="layout-aside">
      <div class="logo">
        <h2>任务管理后台</h2>
      </div>
      <el-menu
        :default-active="route.path"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#2C8FF5"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataBoard /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/first-level-task">
          <el-icon><List /></el-icon>
          <span>一级任务管理</span>
        </el-menu-item>
        <el-menu-item index="/second-level-task">
          <el-icon><Document /></el-icon>
          <span>二级任务管理</span>
        </el-menu-item>
        <el-menu-item index="/feedback" v-if="canManageFeedback">
          <el-icon><ChatDotRound /></el-icon>
          <span>反馈处理</span>
        </el-menu-item>
        <el-menu-item index="/merchant-list">
          <el-icon><Shop /></el-icon>
          <span>{{ MERCHANT_LIST_TITLE }}</span>
        </el-menu-item>
        <el-menu-item index="/merchant-progress">
          <el-icon><Shop /></el-icon>
          <span>{{ MERCHANT_PROGRESS_TITLE }}</span>
        </el-menu-item>
        <el-menu-item index="/data-stats">
          <el-icon><TrendCharts /></el-icon>
          <span>数据统计</span>
        </el-menu-item>
        <el-menu-item index="/account">
          <el-icon><User /></el-icon>
          <span>账号管理</span>
        </el-menu-item>
        <el-menu-item v-if="isSuperAdmin" index="/ai-config">
          <el-icon><Setting /></el-icon>
          <span>{{ AI_CONFIG_MENU_TEXT }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 主内容区 -->
    <el-container>
      <!-- 顶部栏 -->
      <el-header class="layout-header">
        <div class="header-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="route.meta.title">{{ route.meta.title }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <el-dropdown @command="handleCommand">
            <span class="el-dropdown-link">
              {{ authStore.adminInfo?.realName || authStore.adminInfo?.username || '管理员' }}
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                <el-dropdown-item command="logout" divided>{{ LOGOUT_ENTRY_TEXT }}</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 内容区 -->
      <el-main class="layout-main">
        <router-view />
      </el-main>

      <!-- 页脚：ICP 备案信息（工信部要求） -->
      <el-footer height="auto" class="layout-footer">
        <IcpFooter />
      </el-footer>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store/modules/auth'
import { DataBoard, List, Document, User, ArrowDown, ChatDotRound, Shop, TrendCharts, Setting } from '@element-plus/icons-vue'
import { AI_CONFIG_MENU_TEXT } from '@/constants/ai-config'
import { MERCHANT_LIST_TITLE, MERCHANT_PROGRESS_TITLE } from '@/constants/merchant'
import IcpFooter from '@/components/IcpFooter/index.vue'
import { ElMessageBox } from 'element-plus'
import {
  LOGOUT_ENTRY_TEXT,
  LOGOUT_CONFIRM_TITLE,
  LOGOUT_CONFIRM_MESSAGE,
  LOGOUT_CONFIRM_CANCEL_TEXT,
  LOGOUT_CONFIRM_OK_TEXT,
} from '@/constants/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

// 初始化
authStore.init()

// 反馈处理入口仅 super_admin/admin 可见（后端 @Roles('super_admin','admin')）
const canManageFeedback = computed(() => {
  const role = authStore.adminInfo?.role
  return role === 'super_admin' || role === 'admin'
})

// AI 配置入口仅 super_admin 可见（后端 require_roles("super_admin")；路由侧另有守卫拦直连）
const isSuperAdmin = computed(() => authStore.adminInfo?.role === 'super_admin')

const handleCommand = async (command: string) => {
  if (command === 'profile') {
    router.push('/profile')
    return
  }
  if (command === 'logout') {
    try {
      // 二次确认：取消 / 关闭 / ESC 均抛错，此时保持登录态不退出
      await ElMessageBox.confirm(LOGOUT_CONFIRM_MESSAGE, LOGOUT_CONFIRM_TITLE, {
        confirmButtonText: LOGOUT_CONFIRM_OK_TEXT,
        cancelButtonText: LOGOUT_CONFIRM_CANCEL_TEXT,
        type: 'warning',
      })
    } catch {
      return
    }
    authStore.logout()
  }
}
</script>

<style scoped>
.layout-container {
  height: 100vh;
}

.layout-aside {
  background-color: #304156;
  overflow-y: auto;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-bottom: 1px solid #3d4a5a;
}

.logo h2 {
  color: #fff;
  font-size: 16px;
  margin: 0;
}

.layout-header {
  background-color: #fff;
  border-bottom: 1px solid #e6e6e6;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}

.header-right {
  display: flex;
  align-items: center;
}

.el-dropdown-link {
  cursor: pointer;
  display: flex;
  align-items: center;
  color: var(--el-text-color-regular);
}

.layout-main {
  background-color: #f5f7fa;
  padding: 20px;
}

.layout-footer {
  padding: 0;
  background-color: var(--el-fill-color-blank);
  border-top: 1px solid var(--el-border-color-light);
}
</style>
