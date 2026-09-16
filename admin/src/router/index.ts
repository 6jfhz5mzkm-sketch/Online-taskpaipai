import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { ElMessage } from 'element-plus'
import { AI_CONFIG_MENU_TEXT, AI_CONFIG_ROLE_DENIED_TEXT } from '@/constants/ai-config'
import { MERCHANT_LIST_TITLE, MERCHANT_PROGRESS_TITLE } from '@/constants/merchant'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/login/index.vue'),
    meta: { title: '登录', requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/components/Layout/index.vue'),
    redirect: '/dashboard',
    meta: { requiresAuth: true },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/pages/dashboard/index.vue'),
        meta: { title: '仪表盘' },
      },
      {
        path: 'first-level-task',
        name: 'FirstLevelTask',
        component: () => import('@/pages/first-level-task/index.vue'),
        meta: { title: '一级任务管理' },
      },
      {
        path: 'second-level-task',
        name: 'SecondLevelTask',
        component: () => import('@/pages/second-level-task/index.vue'),
        meta: { title: '二级任务管理' },
      },
      {
        path: 'second-level-task/edit/:id?',
        name: 'SecondLevelTaskEdit',
        component: () => import('@/pages/second-level-task/edit.vue'),
        meta: { title: '编辑二级任务' },
      },
      {
        path: 'feedback',
        name: 'Feedback',
        component: () => import('@/pages/feedback/index.vue'),
        meta: { title: '反馈处理' },
      },
      {
        path: 'merchant-list',
        name: 'MerchantList',
        component: () => import('@/pages/merchant-list/index.vue'),
        meta: { title: MERCHANT_LIST_TITLE },
      },
      {
        path: 'merchant-progress',
        name: 'MerchantProgress',
        component: () => import('@/pages/merchant-progress/index.vue'),
        meta: { title: MERCHANT_PROGRESS_TITLE },
      },
      {
        path: 'data-stats',
        name: 'DataStats',
        component: () => import('@/pages/data-stats/index.vue'),
        meta: { title: '数据统计' },
      },
      {
        path: 'account',
        name: 'Account',
        component: () => import('@/pages/account/index.vue'),
        meta: { title: '账号管理' },
      },
      {
        // 仅 super_admin：菜单隐藏 + 本守卫拦截直连 URL；后端 403 才是唯一可信边界
        path: 'ai-config',
        name: 'AiConfig',
        component: () => import('@/pages/ai-config/index.vue'),
        meta: { title: AI_CONFIG_MENU_TEXT, requiresRole: 'super_admin' },
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/pages/profile/index.vue'),
        meta: { title: '个人中心' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

/** 当前登录管理员角色（取自登录时落库的 admin_info；未登录返回空串） */
const readAdminRole = (): string => {
  try {
    const info = JSON.parse(localStorage.getItem('admin_info') || '{}') as { role?: string }
    return info.role || ''
  } catch {
    return ''
  }
}

// 路由守卫
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('admin_token')
  const requiredRole = to.meta.requiresRole as string | undefined

  if (to.meta.requiresAuth !== false && !token) {
    next('/login')
    return
  }
  if (to.path === '/login' && token) {
    next('/dashboard')
    return
  }
  // 角色守卫：菜单隐藏不算安全，直连 URL 同样拦截（唯一可信边界仍是后端 403）
  if (requiredRole && readAdminRole() !== requiredRole) {
    ElMessage.error(AI_CONFIG_ROLE_DENIED_TEXT)
    next('/dashboard')
    return
  }
  next()
})

export default router
