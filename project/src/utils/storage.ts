/**
 * 本地存储封装
 */

export const storage = {
  get<T = any>(key: string): T | null {
    try {
      const value = uni.getStorageSync(key);
      return value ? (JSON.parse(value) as T) : null;
    } catch {
      return null;
    }
  },

  set(key: string, value: any): void {
    try {
      uni.setStorageSync(key, JSON.stringify(value));
    } catch (e) {
      console.error('Storage set error:', e);
    }
  },

  remove(key: string): void {
    try {
      uni.removeStorageSync(key);
    } catch (e) {
      console.error('Storage remove error:', e);
    }
  },

  clear(): void {
    try {
      uni.clearStorageSync();
    } catch (e) {
      console.error('Storage clear error:', e);
    }
  },
};
