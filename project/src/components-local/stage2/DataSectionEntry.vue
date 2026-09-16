<!--
  @Component DataSectionEntry
  @Version 1.0.0
  @Description 数据分析专区入口行（stage2 页面私有组件，用于侧边栏专区）：PNG 图标 + 入口文案 + 操作按钮
               单行布局（flex 单行、文案 ellipsis 截断、按钮 flex-shrink 不溢出），按钮分主/次（variant），
               图标经 iconSrc 传入 static 图片路径（uni-app <image> 渲染），样式全部取自设计 Token
               （§3.3 按钮 / §3.5 hover / §3.6 字号 / §3.7 间距 / §3.8 圆角 / §3.10 过渡）。
-->
<template>
  <view class="entry" @tap="emit('click')">
    <image class="entry__icon" :class="iconClass" :src="iconSrc" mode="aspectFit" />
    <text class="entry__label">{{ label }}</text>
    <view class="entry__btn" :class="'entry__btn--' + variant">
      <text class="entry__btn-text">{{ buttonText }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue';

/**
 * DataSectionEntry - 数据分析专区入口行
 * @description 侧边栏数据分析专区单条入口：PNG 图标 + 文案 + 操作按钮 flex 单行布局；
 *              图标通过 iconSrc 传入 static 图片路径（<image mode="aspectFit"> 渲染，默认 40rpx，
 *              iconSize 可调档位（44/48/56rpx）与行高协调）；
 *              窄容器下文案 ellipsis 截断、按钮不溢出；按钮按 §3.3 主/次按钮配色
 *
 * @example
 * <DataSectionEntry icon-src="/static/images/data-center-upload.png" label="店铺数据上传" button-text="上传" variant="primary" @click="goDataUpload" />
 */
interface Props {
  /** 行内图标图片路径（uni-app static 资源，如 /static/images/xxx.png） */
  iconSrc: string;
  /** 入口文案 */
  label: string;
  /** 操作按钮文字 */
  buttonText: string;
  /** 按钮类型：primary 主按钮（§3.3 绿底白字）| secondary 次按钮（§3.3 白底绿字绿边） */
  variant?: 'primary' | 'secondary';
  /** 入口图标尺寸档位（rpx）：默认 40；差异化放大时传 44（如「店铺数据上传」入口），
   *  对应 .entry__icon--{size} 静态档位 class（scoped SCSS 静态编译 rpx，H5 端可靠转换） */
  iconSize?: 40 | 44 | 48 | 56;
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'primary',
  iconSize: 40,
});

/** 图标尺寸档位 class：默认 40rpx 走 .entry__icon 基础样式（不加额外 class），非默认档追加 --{size} 类 */
const iconClass = computed(() => (props.iconSize === 40 ? '' : `entry__icon--${props.iconSize}`));

const emit = defineEmits<{ click: [] }>();
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

/* 入口行：flex 单行布局（图标固定宽 + 文案 flex:1 截断 + 按钮 flex-shrink:0 不溢出），
   hover/active 浅绿反馈（§3.5 侧边栏 hover 色），背景过渡 $up-ease-normal */
.entry {
  display: flex;
  align-items: center;
  padding: $up-space-2 $up-space-3;
  border-radius: $up-radius-sm;
  transition: background-color $up-ease-normal;

  & + & {
    margin-top: $up-space-2;
  }

  &:hover,
  &:active {
    background-color: $u-primary-light;
  }

  /* 入口图标：PNG 图片（aspectFit 等比显示不变形），默认 40rpx 与侧边栏行高协调，
     固定尺寸不参与收缩；差异化放大走下方 --{size} 静态档位 class（如 --44） */
  &__icon {
    flex-shrink: 0;
    width: 40rpx;
    height: 40rpx;
    margin-right: $up-space-2;
  }

  /* 图标尺寸档位：iconSize prop 选择（40 默认走基础样式，44/48/56 走档位），静态 rpx 编译可靠转换 */
  @each $size in (44, 48, 56) {
    &__icon--#{$size} {
      width: #{$size}rpx;
      height: #{$size}rpx;
    }
  }

  /* 入口文案：flex:1 + min-width:0 + ellipsis，窄容器下截断不换行、不挤占按钮 */
  &__label {
    flex: 1;
    min-width: 0;
    font-size: $up-font-size-body-sm;
    color: $u-content-color;
    line-height: 1.4;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* 操作按钮：§3.3 主/次按钮配色 + §3.8 圆角 + §3.10 过渡；flex-shrink:0 保证不溢出 */
  &__btn {
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 96rpx;
    height: 56rpx;
    margin-left: $up-space-3;
    padding: 0 $up-space-3;
    border-radius: $up-radius-sm;
    transition: background-color $up-ease-normal, border-color $up-ease-normal, color $up-ease-normal;
    flex-shrink: 0;

    /* 主按钮：§3.3 绿底白字，active 深绿 */
    &--primary {
      background-color: $u-primary;
      border: 1rpx solid $u-primary;

      .entry__btn-text {
        color: $u-white;
        font-weight: 600;
      }

      &:active {
        background-color: $u-primary-dark;
        border-color: $u-primary-dark;
      }
    }

    /* 次按钮：§3.3 白底绿字绿边，active 浅绿底 */
    &--secondary {
      background-color: $u-white;
      border: 1rpx solid $u-primary;

      .entry__btn-text {
        color: $u-primary;
        font-weight: 500;
      }

      &:active {
        background-color: $u-primary-light;
      }
    }
  }

  &__btn-text {
    font-size: $up-font-size-caption;
    line-height: 1.4;
  }
}
</style>
