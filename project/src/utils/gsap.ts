/**
 * GSAP 统一入口（F2-GSAP2 / F2-GSAP4）
 * @description 曾出现 CSSPlugin 注册不生效（"Invalid property ... Missing plugin?"）导致动画失效，
 *              疑因 uni-app 打包产生多份 gsap-core 实例 / 注册未达执行实例。
 *              此模块强制 **window 全局单例**：首个执行方把 gsap 挂 window.__GSAP__，
 *              此后所有组件 import { gsap } from '@/utils/gsap' 都取同一实例，
 *              并确保该实例注册 CSSPlugin（registerPlugin 幂等）。
 */
// F2-GSAP7：CSSPlugin 一律从 'gsap' 根入口导入 —— gsap index.js 自动注册用的就是该份
//（index.js 内 import { CSSPlugin } from "./CSSPlugin.js" 并 registerPlugin），与 window.__GSAP__
// 注册来源同模块实例，杜绝 'gsap/CSSPlugin' 直引在打包中产生不同副本导致注册无效。
import { gsap as gsapModule, CSSPlugin } from 'gsap';

declare global {
  interface Window {
    /** 全局唯一已注册 CSSPlugin 的 gsap 实例（F2-GSAP4） */
    __GSAP__?: typeof gsapModule;
  }
}

const hasWindow = typeof window !== 'undefined';
if (hasWindow) {
  window.__GSAP__ = window.__GSAP__ || gsapModule;
}
const gsap = (hasWindow && window.__GSAP__) || gsapModule;
gsap.registerPlugin(CSSPlugin);

/**
 * 运行时取全局单例（F2-GSAP5）：本模块即便被打包成多份副本，各副本 import 到的 gsap 可能不同实例；
 * 组件一律通过此访问器在实例化时取值 —— 函数体恒读 window.__GSAP__，保证消费同一已注册实例。
 */
export const getGsap = (): typeof gsapModule =>
  (typeof window !== 'undefined' && window.__GSAP__) || gsapModule;

// 统一导出 CSSPlugin（与 window.__GSAP__ 自动注册同源），组件补注册一律用此份
export { gsap, CSSPlugin };
