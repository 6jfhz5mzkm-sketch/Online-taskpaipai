
// 配置加载：读取 automation/.env，缺失则回退 backend/.env.local
import dotenv from 'dotenv';
import { existsSync } from 'fs';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AUTO_DIR = path.resolve(__dirname, '..');

// 优先 automation/.env，其次 backend/.env.local
for (const p of [path.join(AUTO_DIR, '.env'), path.join(AUTO_DIR, '..', 'backend', '.env.local')]) {
  if (existsSync(p)) dotenv.config({ path: p });
}

const num = (v, d) => (v === undefined || v === '' ? d : Number(v));

// ---- DB 口令兜底守卫（#OPS-48；口径对齐 api-py app/core/config.py::validate_startup_settings）----
// 动机：本工具按月在生产库上运行。旧行为在 automation/.env 缺失或键名写错时会**静默**用公开 dev
// 兜底口令去连生产库；api-py 对同类兜底有启动期 fail-fast，自动化侧此前没有 ⇒ 口径不一致。
// 口径：兜底值本身保留（本地开发可用），但**生产形态一旦走到兜底即 fail-fast**；判定集中在纯函数。
export const DEV_FALLBACK_DB_PASS = 'root123';
const LOCAL_DB_HOSTS = new Set(['127.0.0.1', 'localhost', '::1']);

// 纯函数（可单测；不建连接、无副作用）：入参 = 解析后的 db 配置 + 是否显式提供了口令
//   返回 { ok: true, warning? } → 通过（warning 为「本地开发用兜底值」的显著提醒）
//        { ok: false, reason } → 拒绝（reason 为可读中文原因）
export function guardDbPass({ host, database, password, passProvided }) {
  const target = String(database || '') + '@' + String(host || '');
  const usingFallback = !passProvided || password === DEV_FALLBACK_DB_PASS;
  const isProdLike = String(database || '').endsWith('_prod') || !LOCAL_DB_HOSTS.has(String(host || ''));
  if (isProdLike && usingFallback) {
    return {
      ok: false,
      target,
      isProdLike,
      usingFallback,
      reason:
        '数据库目标为生产形态(' + target + ')，但 DB_PASS 为空或仍是公开 dev 兜底值：' +
        '禁止用兜底口令连接生产库。请在 automation/.env 配置真实 DB_PASS' +
        '(服务器位置 <SERVER_ROOT>/automation/.env，权限 600)，或用环境变量 DB_PASS=... 传入。',
    };
  }
  if (usingFallback) {
    return {
      ok: true,
      target,
      isProdLike,
      usingFallback,
      warning:
        'DB_PASS 未显式配置，正在使用公开 dev 兜底口令连接本机开发库(' + target + ')；' +
        '仅限本地开发，生产环境必须配置真实口令。',
    };
  }
  return { ok: true, target, isProdLike, usingFallback };
}

const rawDbPass = process.env.DB_PASS || '';

export const config = {
  env: process.env.NODE_ENV || 'development',
  db: {
    host: process.env.DB_HOST || '127.0.0.1',
    port: num(process.env.DB_PORT, 3306),
    user: process.env.DB_USER || 'root',
    // 未显式提供口令时才落兜底值（与旧式 process.env.DB_PASS || 'root123' 逐字段一致）
    password: rawDbPass !== '' ? rawDbPass : DEV_FALLBACK_DB_PASS,
    database: process.env.DB_NAME || 'merchant_task',
  },
  rule: {
    url: process.env.FEE_RULE_URL || 'https://learn-jdm.jd.com/knowledge/rule/detail?ruleId=1323517376196349952',
  },
  feishu: {
    appId: process.env.FEISHU_APP_ID || '',
    appSecret: process.env.FEISHU_APP_SECRET || '',
    // 接收方 open_id（管理层/指定人员）＝通知对象
    adminOpenId: process.env.FEISHU_ADMIN_OPEN_ID || '',
    apiBase: process.env.FEISHU_API_BASE || 'https://open.feishu.cn',
  },
  scrape: {
    // 无头浏览器：优先系统自带 Chrome/Edge（channel），可被环境变量覆盖
    executablePath: process.env.FEE_SCRAPE_BROWSER_PATH || '',
    headless: true,
    timeoutMs: num(process.env.FEE_SCRAPE_TIMEOUT_MS, 120000),
  },
  run: {
    // 默认 dry-run 只比对+通知，不改库；--apply 时才写库
    apply: false,
  },
};

// ---- 装载期执行守卫（fail-fast；纯函数 guardDbPass 已导出，可单独单测）----
const dbGuard = guardDbPass({
  host: config.db.host,
  database: config.db.database,
  password: config.db.password,
  passProvided: rawDbPass !== '',
});
if (!dbGuard.ok) {
  console.error('!! 拒绝启动：' + dbGuard.reason);
  process.exit(1);
}
if (dbGuard.warning) {
  console.warn('!! [warn] ' + dbGuard.warning);
}
