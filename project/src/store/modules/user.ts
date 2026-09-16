/**
 * 用户状态管理
 */
import { defineStore } from 'pinia';
import { ref } from 'vue';
import type { UserInfo } from '@/types/user';

export const useUserStore = defineStore('user', () => {
  const userInfo = ref<UserInfo | null>(null);
  const token = ref('');

  const setUserInfo = (info: UserInfo) => {
    userInfo.value = info;
  };

  const setToken = (t: string) => {
    token.value = t;
    uni.setStorageSync('token', t);
  };

  const logout = () => {
    userInfo.value = null;
    token.value = '';
    uni.removeStorageSync('token');
  };

  const initToken = () => {
    token.value = uni.getStorageSync('token') || '';
  };

  return { userInfo, token, setUserInfo, setToken, logout, initToken };
});
