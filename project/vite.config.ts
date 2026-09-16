import { defineConfig } from 'vite';
import uni from '@dcloudio/vite-plugin-uni';
import { resolve } from 'path';

export default defineConfig({
  plugins: [uni()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        // F2-GSAP3：打包层强制 gsap 单例。函数式 manualChunks 将 gsap 包内全部模块
        // （gsap-core.js / CSSPlugin.js / index.js 入口）归入单一 'gsap' chunk，
        // 使 CSSPlugin 注册与 gsap core 同 chunk 单份；任何使用方（Stage2Sidebar 等）
        // 一律 import 该 chunk，杜绝 rollup 跨 chunk 复制未注册 gsap 实例导致的
        // "Invalid property ... Missing plugin?" 与动画失效。
        manualChunks(id) {
          if (id.includes('node_modules/gsap/')) return 'gsap';
          return undefined;
        },
      },
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: '',
        includePaths: ['src/styles'],
      },
    },
  },
  optimizeDeps: {
    exclude: ['@dcloudio/uni-h5'],
    // F2-GSAP8：gsap 预构建为单一依赖（dev 模式同样单例），避免 .vite/deps 优化入口
    // 与直连 node_modules 产生双份 CSSPlugin/gsap 实例；与 build manualChunks 叠加双保险。
    include: ['gsap'],
  },
});
