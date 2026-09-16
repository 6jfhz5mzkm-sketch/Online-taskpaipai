import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as loginApi, getProfile } from '@/api/auth'
import type { LoginParams } from '@/api/auth'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('admin_token') || '')
  const adminInfo = ref<any>(null)

  // 登录
  async function login(params: LoginParams) {
    const res = await loginApi(params)
    token.value = res.data.token
    adminInfo.value = res.data.admin
    localStorage.setItem('admin_token', res.data.token)
    localStorage.setItem('admin_info', JSON.stringify(res.data.admin))
    router.push('/dashboard')
  }

  // 退出登录
  function logout() {
    token.value = ''
    adminInfo.value = null
    localStorage.removeItem('admin_token')
    localStorage.removeItem('admin_info')
    router.push('/login')
  }

  // 获取管理员信息
  async function fetchProfile() {
    try {
      const res = await getProfile()
      adminInfo.value = res.data
      localStorage.setItem('admin_info', JSON.stringify(res.data))
    } catch (error) {
      console.error('获取管理员信息失败', error)
    }
  }

  // 初始化
  function init() {
    const savedInfo = localStorage.getItem('admin_info')
    if (savedInfo) {
      adminInfo.value = JSON.parse(savedInfo)
    }
  }

  return { token, adminInfo, login, logout, fetchProfile, init }
})
