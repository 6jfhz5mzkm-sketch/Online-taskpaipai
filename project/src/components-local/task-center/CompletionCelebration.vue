<!--
  @Component CompletionCelebration
  @Version 1.0.0
  @Description 阶段一完成「升华汇聚」动画：环境渐暗 → 卡片逐卡点亮 → 升华为光点 → 光点汇聚 → 徽章成形落定。
              图层：遮罩 z500 → 光点层 z501 → 徽章层 z502；仅 H5 使用；GSAP 时间线 + 位置参数。
-->
<template>
  <view v-if="visible" class="celebration">
    <!-- ① 环境渐暗 + 锁屏（fixed mask + body 禁滚） -->
    <view ref="maskRef" class="celebration__mask" @touchmove.stop.prevent @tap.stop.prevent />

    <!-- 光点层（每卡 1 个，非粒子） -->
    <view class="celebration__dots">
      <view
        v-for="d in dots"
        :key="d.id"
        :ref="(el) => setDotEl(d, el)"
        class="celebration__dot"
        :style="dotStyle(d)"
      />
    </view>

    <!-- 徽章层：SVG 圆环 + 对勾描边成形 -->
    <view
      ref="badgeRef"
      class="celebration__badge"
      :style="{ top: CONVERGE_Y_RATIO * 100 + '%' }"
    >
      <svg width="120" height="120" viewBox="0 0 120 120">
        <defs>
          <linearGradient id="celebration-badge-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#22C55E" />
            <stop offset="100%" stop-color="#86EFAC" />
          </linearGradient>
        </defs>
        <circle
          ref="ringRef"
          cx="60"
          cy="60"
          r="54"
          fill="none"
          stroke="url(#celebration-badge-gradient)"
          stroke-width="5"
          stroke-linecap="round"
          :stroke-dasharray="RING_LENGTH"
          :stroke-dashoffset="RING_LENGTH"
        />
        <path
          ref="checkRef"
          d="M 38 62 L 54 78 L 84 46"
          fill="none"
          stroke="#22C55E"
          stroke-width="7"
          stroke-linecap="round"
          stroke-linejoin="round"
          :stroke-dasharray="CHECK_LENGTH"
          :stroke-dashoffset="CHECK_LENGTH"
        />
      </svg>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, nextTick, onBeforeUnmount } from 'vue'
import { getGsap } from '@/utils/gsap'
const gsap = getGsap()

/** 动画参数常量（R25） */
const DIM_DURATION = 0.4 // 环境渐暗
const MASK_OPACITY = 0.7 // 遮罩最终透明度
const HIGHLIGHT_START = 0.2 // 点亮起始时间点
const CARD_STAGGER = 0.06 // 卡片错落间隔（s）
const HIGHLIGHT_DURATION = 0.35 // 点亮时长
const SHRINK_DURATION = 0.4 // 光点化时长
const FLY_DURATION = 0.8 // 光点飞行时长
const BADGE_STROKE = 0.6 // 圆环描边
const CHECK_STROKE = 0.5 // 对勾描边
const BADGE_POP = 0.45 // 徽章回弹
const CONVERGE_Y_RATIO = 0.28 // 汇聚点 y 比例
const DOT_SIZE = 12 // 光点直径基准（px），±2 随机
const DOT_SIZE_RANGE = 2
const RING_LENGTH = 340 // 圆环周长（≈2π*54）
const CHECK_LENGTH = 80 // 对勾路径长度上界
/** 点亮发光投影（主题绿） */
const GLOW = '0 0 12px rgba(34,197,94,0.55), 0 0 24px rgba(34,197,94,0.25)'

interface Dot {
  id: number
  x: number
  y: number
  size: number
}

const visible = ref(false)
const dots = ref<Dot[]>([])
const dotElMap: Record<number, HTMLElement | null> = {}
let idSeq = 0
let tl: ReturnType<typeof gsap.timeline> | null = null

const maskRef = ref<HTMLElement | null>(null)
const badgeRef = ref<HTMLElement | null>(null)
const ringRef = ref<SVGCircleElement | null>(null)
const checkRef = ref<SVGPathElement | null>(null)

function resolveEl(refValue: any): HTMLElement | null {
  return refValue?.$el ?? (refValue as HTMLElement | null)
}

function setDotEl(d: Dot, el: any) {
  dotElMap[d.id] = el?.$el ?? (el as HTMLElement | null)
}

function dotStyle(d: Dot) {
  return {
    width: d.size + 'px',
    height: d.size + 'px',
    // 初始定位用 transform（飞行只动 transform/opacity）
    transform: `translate(${d.x}px, ${d.y}px)`,
    opacity: '0',
  }
}

function rand(min: number, max: number): number {
  return min + Math.random() * (max - min)
}

/** 播放升华汇聚动画：结束后保持卡片与整组内容隐藏并回调（恢复由页面在弹窗关闭时处理） */
async function play(
  cards: Array<HTMLElement | null>,
  groups: Array<{ el: HTMLElement | null; cardCount: number }>,
  onDone: () => void,
) {
  stop()
  visible.value = true
  lockInteraction(true)

  // 实时坐标：getBoundingClientRect 为视口坐标，fixed 光点层直接使用（含滚动位置）
  const rects = cards
    .filter((el): el is HTMLElement => !!el)
    .map((el) => {
      const r = el.getBoundingClientRect()
      return { el, cx: r.left + r.width / 2, cy: r.top + r.height / 2 }
    })
  const groupEls = groups.map((g) => g.el).filter((el): el is HTMLElement => !!el)

  if (rects.length === 0) {
    lockInteraction(false)
    visible.value = false
    onDone()
    return
  }

  dots.value = rects.map((c) => ({
    id: ++idSeq,
    x: c.cx,
    y: c.cy,
    size: DOT_SIZE + (Math.random() * 2 - 1) * DOT_SIZE_RANGE,
  }))
  // Vue 渲染异步：等光点 DOM 与 ref 收集完成后再建时间线
  await nextTick()

  const maskEl = resolveEl(maskRef.value)
  const badgeEl = resolveEl(badgeRef.value)
  const ringEl = ringRef.value
  const checkEl = checkRef.value
  const dotEls = dots.value.map((d) => dotElMap[d.id])

  tl = gsap.timeline({
    onComplete: () => {
      // 卡片与整组内容（标题/支线）完全隐藏（避免弹窗背景露出任务）
      rects.forEach((c) => gsap.set(c.el, { opacity: 0 }))
      groupEls.forEach((g) => gsap.set(g, { opacity: 0 }))
      // 清理光点 DOM 与锁屏，避免内存残留
      dots.value = []
      visible.value = false
      lockInteraction(false)
      tl = null
      onDone()
    },
  })

  // ① 环境渐暗
  if (maskEl) {
    tl.fromTo(maskEl, { opacity: 0 }, { opacity: MASK_OPACITY, duration: DIM_DURATION, ease: 'power1.inOut' }, 0)
  }

  // ② 逐卡点亮（亮度 + 发光投影，0.06s 错开）
  rects.forEach((c, ci) => {
    const at = HIGHLIGHT_START + ci * CARD_STAGGER
    tl.fromTo(
      c.el,
      { scale: 1, filter: 'brightness(1)', boxShadow: '0 0 0px rgba(34,197,94,0)' },
      {
        scale: 1.04,
        filter: 'brightness(1.12)',
        boxShadow: GLOW,
        duration: HIGHLIGHT_DURATION,
        ease: 'power2.out',
        overwrite: 'auto',
      },
      at,
    )
  })

  // ③ 光点化：卡片缩小 + 圆角化，同时中心光点淡入
  rects.forEach((c, ci) => {
    const dot = dotEls[ci]
    const at = HIGHLIGHT_START + ci * CARD_STAGGER + 0.2
    tl.to(
      c.el,
      {
        scale: 0.18,
        opacity: 0,
        borderRadius: '50%',
        duration: SHRINK_DURATION,
        ease: 'power2.inOut',
        overwrite: 'auto',
      },
      at,
    )
    if (dot) {
      tl.fromTo(dot, { opacity: 0, scale: 0.6 }, { opacity: 1, scale: 1, duration: 0.25, ease: 'power1.out' }, at)
    }
  })

  // 整组内容（一级任务标题/支线任务，即组容器）随该组最后一张卡光点化同步淡出，避免标题/支线残留
  let cursor = 0
  groups.forEach((g) => {
    const gEl = g.el
    const count = Math.max(g.cardCount, 0)
    if (gEl && count > 0) {
      const lastIdx = cursor + count - 1
      const at = Math.max(HIGHLIGHT_START, HIGHLIGHT_START + lastIdx * CARD_STAGGER + 0.2 + SHRINK_DURATION - 0.15)
      tl.to(gEl, { opacity: 0, duration: 0.25, ease: 'power1.out', overwrite: 'auto' }, at)
    }
    cursor += count
  })

  // ④ 光点汇聚：全部同时沿二次贝塞尔弧线飞向汇聚点（渐小渐淡）
  const flyStart = HIGHLIGHT_START + (rects.length - 1) * CARD_STAGGER + 0.2 + SHRINK_DURATION
  const targetX = (typeof window !== 'undefined' ? window.innerWidth : 375) / 2
  const targetY = (typeof window !== 'undefined' ? window.innerHeight : 667) * CONVERGE_Y_RATIO
  rects.forEach((c, ci) => {
    const dot = dotEls[ci]
    if (!dot) return
    const ctrlY = Math.min(c.cy, targetY) - 80
    const startX = c.cx
    const startY = c.cy
    tl.to(
      { p: 0 },
      {
        p: 1,
        duration: FLY_DURATION,
        ease: 'power2.inOut',
        onUpdate: function () {
          const p = (this.targets()[0] as { p: number }).p
          const x = (1 - p) * (1 - p) * startX + 2 * (1 - p) * p * ((startX + targetX) / 2) + p * p * targetX
          const y = (1 - p) * (1 - p) * startY + 2 * (1 - p) * p * ctrlY + p * p * targetY
          gsap.set(dot, { x, y, scale: 1 - 0.6 * p, opacity: 1 - p })
        },
        onComplete: () => gsap.set(dot, { opacity: 0 }),
      },
      flyStart,
    )
  })

  // ⑤ 徽章成形（圆环描边 → 对勾描边）⑥ 落定（back.out 回弹）
  const ringStart = flyStart + 0.4
  if (badgeEl) {
    tl.set(badgeEl, { opacity: 1, scale: 1.08 }, ringStart)
    tl.to(badgeEl, { scale: 1, duration: BADGE_POP, ease: 'back.out(1.7)' }, ringStart + BADGE_STROKE - 0.1)
  }
  if (ringEl) {
    tl.to(ringEl, { strokeDashoffset: 0, duration: BADGE_STROKE, ease: 'power1.inOut' }, ringStart)
  }
  if (checkEl) {
    tl.to(checkEl, { strokeDashoffset: 0, duration: CHECK_STROKE, ease: 'power1.inOut' }, ringStart + BADGE_STROKE - 0.1)
  }
}

/** 锁屏：fixed 遮罩拦截点击 + body 禁滚（H5） */
function lockInteraction(locked: boolean) {
  if (typeof document !== 'undefined') {
    document.body.style.overflow = locked ? 'hidden' : ''
  }
}

function stop() {
  if (tl) {
    tl.kill()
    tl = null
  }
  const targets: Array<HTMLElement> = []
  Object.values(dotElMap).forEach((el) => {
    if (el) targets.push(el)
  })
  if (targets.length) gsap.killTweensOf(targets)
  dots.value = []
  visible.value = false
  lockInteraction(false)
}

onBeforeUnmount(() => stop())

defineExpose({ play, stop })
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.celebration {
  &__mask {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    left: 0;
    z-index: 500;
    background-color: #000;
  }

  &__dots {
    position: fixed;
    top: 0;
    right: 0;
    bottom: 0;
    left: 0;
    z-index: 501;
    pointer-events: none;
    overflow: hidden;
  }

  &__dot {
    position: absolute;
    border-radius: $up-radius-full;
    /* 主题绿径向渐变 + 多层光晕 */
    background: radial-gradient(circle, #ffffff 0%, #22c55e 40%, #16a34a 100%);
    box-shadow:
      0 0 12px rgba(34, 197, 94, 0.9),
      0 0 24px rgba(34, 197, 94, 0.5),
      0 0 40px rgba(34, 197, 94, 0.3);
  }

  &__badge {
    position: fixed;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 502;
    opacity: 0;
    pointer-events: none;
  }
}
</style>
