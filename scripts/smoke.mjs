// scripts/smoke.mjs — 统一冒烟探活（商家端 H5 + 后端健康）
// 依据：商家端 H5 dev/预览监听 5173（project/serve.js 服务 dist/build/h5，SPA fallback）；后端为 api-py（uvicorn --port 8000），健康路由 = /health（不带 /api 前缀）。
// 接口级探活由测试 Agent 的专项验收承担；本脚本只探"全流程可达"。
// 目标 URL 可用环境变量覆盖，默认取实际监听。
import { setTimeout as sleep } from 'node:timers/promises';

const h5Url = process.env.SMOKE_H5_URL || 'http://localhost:5173/';
const apiUrl = process.env.SMOKE_API_URL || `http://localhost:${process.env.PORT || 8000}/health`;

const targets = [
  ['h5 商家端', h5Url],
  ['api 后端健康', apiUrl],
];

await sleep(Number(process.env.SMOKE_WAIT_MS || 2000));

let fail = 0;
for (const [name, url] of targets) {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(Number(process.env.SMOKE_TIMEOUT_MS || 5000)) });
    console.log(`${res.status} ${url}  [${name}]`);
    if (res.status !== 200) { console.error(`  非 200 → ${name} 未通过`); fail++; }
  } catch (e) {
    console.error(`ERR  ${url}  [${name}] ${e.message}`);
    fail++;
  }
}
if (fail) { console.error(`冒烟失败：${fail} 个目标不可达`); process.exit(1); }
console.log('冒烟 OK：全流程可达');
