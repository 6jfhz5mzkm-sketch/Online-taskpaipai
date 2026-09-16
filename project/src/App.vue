<script setup lang="ts">
import { onLaunch, onShow, onHide } from '@dcloudio/uni-app';

onLaunch(() => {
  console.log('App Launch');
});

onShow(() => {
  console.log('App Show');
});

onHide(() => {
  console.log('App Hide');
});
</script>

<style lang="scss">
@import './styles/tokens/index';

/* ============================================================
   全局 CSS Variables（小程序/H5 端生效）
   与 uni.scss 中的 SCSS 变量保持一致
   ============================================================ */
:root,
page,
body {
  /* ---- uview-plus 颜色变量覆盖 ---- */
  --up-primary:            #{$u-primary};
  --up-primary-dark:       #{$u-primary-dark};
  --up-primary-disabled:   #{$u-primary-disabled};
  --up-primary-light:      #{$u-primary-light};

  --up-success:            #{$u-success};
  --up-success-dark:       #{$u-success-dark};
  --up-success-disabled:   #{$u-success-disabled};
  --up-success-light:      #{$u-success-light};

  --up-warning:            #{$u-warning};
  --up-warning-dark:       #{$u-warning-dark};
  --up-warning-disabled:   #{$u-warning-disabled};
  --up-warning-light:      #{$u-warning-light};

  --up-error:              #{$u-error};
  --up-error-dark:         #{$u-error-dark};
  --up-error-disabled:     #{$u-error-disabled};
  --up-error-light:        #{$u-error-light};

  --up-info:               #{$u-info};
  --up-info-dark:          #{$u-info-dark};
  --up-info-disabled:      #{$u-info-disabled};
  --up-info-light:         #{$u-info-light};

  --up-main-color:         #{$u-main-color};
  --up-content-color:      #{$u-content-color};
  --up-tips-color:         #{$u-tips-color};
  --up-light-color:        #{$u-light-color};
  --up-border-color:       #{$u-border-color};
  --up-bg-color:           #{$u-bg-color};
  --up-disabled-color:     #{$u-disabled-color};

  --up-page-bg-color:      #{$u-bg-color};
  --up-card-bg-color:      #FFFFFF;
  --up-hover-bg-color:     #{$u-primary-light};

  /* ---- 扩展变量 ---- */
  --up-font-size-display:  #{$up-font-size-display};
  --up-font-size-h1:       #{$up-font-size-h1};
  --up-font-size-h2:       #{$up-font-size-h2};
  --up-font-size-h3:       #{$up-font-size-h3};
  --up-font-size-body:     #{$up-font-size-body};
  --up-font-size-caption:  #{$up-font-size-caption};
  --up-font-size-mini:     #{$up-font-size-mini};

  --up-space-1: #{$up-space-1};
  --up-space-2: #{$up-space-2};
  --up-space-3: #{$up-space-3};
  --up-space-4: #{$up-space-4};
  --up-space-5: #{$up-space-5};
  --up-space-6: #{$up-space-6};
  --up-space-8: #{$up-space-8};

  --up-radius-xs: #{$up-radius-xs};
  --up-radius-sm: #{$up-radius-sm};
  --up-radius-md: #{$up-radius-md};
  --up-radius-lg: #{$up-radius-lg};
  --up-radius-xl: #{$up-radius-xl};

  --up-shadow-sm: #{$up-shadow-sm};
  --up-shadow-md: #{$up-shadow-md};
  --up-shadow-lg: #{$up-shadow-lg};
}

@import './styles/global.scss';
</style>
