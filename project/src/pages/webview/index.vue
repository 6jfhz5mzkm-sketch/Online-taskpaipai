<template>
  <view class="webview-page">
    <!-- 有链接：渲染 web-view -->
    <web-view v-if="url" :src="url" />

    <!-- 无链接：空态兜底 + 返回 -->
    <view v-else class="webview-empty">
      <EmptyState type="error" text="未找到链接地址" sub-text="链接参数缺失或已失效" action-text="返回上一页" @action="goBack" />
    </view>
  </view>
</template>

<script setup lang="ts">
/**
 * WebView 页面
 * @description 用于打开外部链接（如入驻网址、飞书表单）；链接缺失时提供空态兜底与返回操作。
 */
import { ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import EmptyState from '@/components/EmptyState/index.vue'

const url = ref('')

onLoad((options) => {
  if (options?.url) {
    url.value = decodeURIComponent(options.url)
  }
})

function goBack(): void {
  uni.navigateBack({
    fail: () => {
      uni.reLaunch({ url: '/pages/index/index' })
    },
  })
}
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.webview-page {
  min-height: 100vh;
  background-color: $u-bg-color;
}

.webview-empty {
  min-height: 80vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: $up-space-8;
}
</style>
