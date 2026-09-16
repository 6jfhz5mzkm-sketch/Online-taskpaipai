<!--
  @Component StageHeader
  @Version 1.0.0
  @Description 阶段标题头部组件，包含阶段编号圆圈、标题和完成按钮。
-->
<template>
  <view class="stage-header">
    <view class="stage-header__num">
      <text class="stage-header__num-text">{{ stageNum }}</text>
    </view>
    <text class="stage-header__title">{{ title }}</text>
    <view class="stage-header__action" @tap.stop="handleComplete">
      <text
        ref="btnRef"
        class="stage-header__btn"
        :class="{ 'stage-header__btn--completed': completed }"
      >
        {{ completed ? '✓ ' + buttonText : buttonText }}
      </text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { getGsap } from '@/utils/gsap'
const gsap = getGsap()

interface Props {
  stageNum: number
  title: string
  buttonText: string
  /** 一级任务组是否已全部完成（完成态显示单个对勾 + 原文案，取消态无对勾） */
  completed?: boolean
}
withDefaults(defineProps<Props>(), {
  completed: false,
})
const emit = defineEmits<{ complete: [] }>()

const btnRef = ref<HTMLElement | null>(null)
let btnEl: HTMLElement | null = null

onMounted(() => {
  btnEl = (btnRef.value as any)?.$el ?? (btnRef.value as HTMLElement | null)
})

onBeforeUnmount(() => {
  if (btnEl) gsap.killTweensOf(btnEl)
})

/** 点击反馈：fromTo 弹跳，overwrite auto 处理连点，无定时器 */
function handleComplete(): void {
  if (btnEl) {
    gsap.fromTo(
      btnEl,
      { scale: 1 },
      {
        scale: 1.08,
        duration: 0.18,
        yoyo: true,
        repeat: 1,
        ease: 'back.out(1.7)',
        overwrite: 'auto',
      },
    )
  }
  emit('complete')
}
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.stage-header {
  display: flex;
  align-items: center;
  padding: $up-space-4 $up-space-5;

  &__num {
    width: 56rpx; height: 56rpx; border-radius: 50%;
    background-color: $u-main-color;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
  }
  &__num-text { color: #fff; font-size: 28rpx; font-weight: 600; }
  &__title { margin-left: $up-space-3; font-size: $up-font-size-h2; font-weight: 600; color: $u-main-color; flex: 1; }
  &__action { margin-left: auto; flex-shrink: 0; }
  &__btn {
    padding: $up-space-2 $up-space-5; font-size: 26rpx;
    color: $u-main-color; background: $u-white; border: 1rpx solid $u-main-color;
    border-radius: $up-radius-md;
    transition: all $up-ease-normal;

    &--completed {
      background: $u-primary;
      border-color: $u-primary;
      color: $u-white;
    }
  }
  &__action:active &__btn { background: $u-main-color; color: #fff; }
}
</style>
