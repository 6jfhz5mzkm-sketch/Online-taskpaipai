import { createSSRApp } from 'vue';
import { createPinia } from 'pinia';
import uviewPlus from 'uview-plus';
// F2-GSAP2：gsap 统一入口（显式注册 CSSPlugin），app 启动即完成注册，动画组件共享同一实例
import '@/utils/gsap';
import App from './App.vue';

export function createApp() {
  const app = createSSRApp(App);
  const pinia = createPinia();

  app.use(pinia);
  app.use(uviewPlus);

  return { app };
}
