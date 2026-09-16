<!--
  @Component IcpFooter
  @description 商家端页脚备案信息（工信部要求）：展示 ICP 备案号并链接至工信部备案系统（新窗口打开）。
               样式全部取自设计规范 Token（§3.6 caption 字号 / §3.7 间距 / §3.8 圆角 / §3.10 过渡），
               居中单行、不参与定位，移动端与 PC 均不溢出、不遮挡内容。
  @slot 无
  @example
  <IcpFooter />
-->
<template>
  <view class="icp-footer">
    <text class="icp-footer__link" @tap="openRecordSite">{{ ICP_RECORD_NUMBER }}</text>
  </view>
</template>

<script setup lang="ts">
/**
 * IcpFooter 组件（备案信息页脚）
 * @description 备案号与工信部链接的唯一来源（站点级常量，仅本组件消费，不做额外抽象）。
 */
/** ICP 备案号（来源：工信部备案系统，站点唯一备案号） */
const ICP_RECORD_NUMBER = '鲁ICP备2026053438号-1';
/** 工信部备案系统地址（备案号须链接至此） */
const ICP_RECORD_SITE = 'https://beian.miit.gov.cn/';

/** 新窗口打开工信部备案系统（H5 用 window.open，与项目既有外链打开方式一致；noopener 防反向标签劫持） */
function openRecordSite(): void {
  if (typeof window === 'undefined') return;
  window.open(ICP_RECORD_SITE, '_blank', 'noopener');
}
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.icp-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: $up-space-4 $up-space-5;

  &__link {
    font-size: $up-font-size-caption;
    line-height: $up-line-height-normal;
    color: $u-tips-color;
    text-align: center;
    transition: color $up-ease-fast;

    &:hover {
      color: $u-primary;
    }

    &:active {
      color: $u-primary;
    }
  }
}
</style>
