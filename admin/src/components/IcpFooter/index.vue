<template>
  <div class="icp-footer">
    <a
      class="icp-footer-link"
      href="https://beian.miit.gov.cn/"
      target="_blank"
      rel="noopener noreferrer"
    >
      鲁ICP备2026053438号-1
    </a>
  </div>
</template>

<script setup lang="ts">
// ICP 备案号页脚（工信部要求）：全局布局与登录页共用，备案信息只在本组件维护
</script>

<style scoped>
.icp-footer {
  padding: 8px 0;
  text-align: center;
  font-size: 12px;
  line-height: 20px;
  color: var(--el-text-color-secondary);
}

.icp-footer-link {
  color: var(--el-text-color-secondary);
  text-decoration: none;
}

.icp-footer-link:hover {
  color: var(--el-color-primary);
  text-decoration: underline;
}
</style>
