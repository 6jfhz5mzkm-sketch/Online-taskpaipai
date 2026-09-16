#!/usr/bin/env bash
set -euo pipefail
# ============================================================
# 拍拍二手资费同步自动化 · 部署机一键安装
# 用法：上传 automation/ 目录到服务器后，在 automation/ 目录内执行：
#   bash setup-server.sh
# 目标：阿里云轻量 Alibaba Cloud Linux 4 · Node>=20 · MySQL 8 · 可出网
# ============================================================

SELF_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SELF_DIR"
NPM_REGISTRY="${NPM_REGISTRY:-https://registry.npmmirror.com}"
BACKEND_ENV="${BACKEND_ENV:-<SERVER_ROOT>/backend/.env.production}"

echo "==> [1/5] 安装 Node 依赖（阿里镜像）"
npm install --omit=dev --registry="$NPM_REGISTRY"

echo "==> [2/5] 安装 Playwright Chromium（国内镜像下载）"
export PLAYWRIGHT_DOWNLOAD_HOST="${PLAYWRIGHT_DOWNLOAD_HOST:-https://npmmirror.com/mirrors/playwright}"
if ! npx playwright install --with-deps chromium; then
  echo "    --with-deps 失败（可能缺 sudo），尝试仅装浏览器"
  npx playwright install chromium
fi

echo "==> [3/5] 生成/校验 automation/.env"
get(){ grep -E "^$1=" "$BACKEND_ENV" 2>/dev/null | head -1 | cut -d= -f2-; }
# 读取已存在的 automation/.env（本目录）中的键；无该文件或键不存在时返回空（不触发 set -e）
get_local(){ grep -E "^$1=" .env 2>/dev/null | head -1 | cut -d= -f2- || true; }

DB_HOST="${DB_HOST:-$(get DB_HOST)}"
DB_PORT="${DB_PORT:-$(get DB_PORT)}"
DB_USER="${DB_USER:-$(get DB_USER)}"
DB_PASS="${DB_PASS:-$(get DB_PASS)}"
DB_NAME="${DB_NAME:-$(get DB_NAME)}"
FEISHU_APP_ID="${FEISHU_APP_ID:-$(get FEISHU_APP_ID)}"
FEISHU_APP_SECRET="${FEISHU_APP_SECRET:-$(get FEISHU_APP_SECRET)}"
# 接收人 open_id（内部标识，属敏感形态）：**本脚本不提供任何内置默认值**（2026-09-16 硬化，#OPS-47）。
#   取数顺序：① 环境变量 FEISHU_ADMIN_OPEN_ID ② 已存在的 automation/.env 中的同名项。
#   值只应存在于服务器 automation/.env（600）；禁止写进仓库/文档/日志。
FEISHU_ADMIN_OPEN_ID="${FEISHU_ADMIN_OPEN_ID:-$(get_local FEISHU_ADMIN_OPEN_ID)}"
NOTIFY_CONFIGURED=1
if [ -z "$FEISHU_ADMIN_OPEN_ID" ]; then
  NOTIFY_CONFIGURED=0
  echo "!! [3/5] 未提供 FEISHU_ADMIN_OPEN_ID —— 本脚本不再使用任何内置默认值，该步骤改为「显式跳过」。"
  echo "   影响：资费同步（抓取/比对/更新/报告）照常执行，但**飞书内部通知会被跳过**"
  echo "         （src/notify.js 会打印「未配置 FEISHU_ADMIN_OPEN_ID，跳过推送」并返回 sent=false）。"
  echo "   如何配置（二选一）："
  echo "     1) 写入 automation/.env：FEISHU_ADMIN_OPEN_ID=<内部接收人 open_id>"
  echo "        （服务器位置 <SERVER_ROOT>/automation/.env，权限 600；可先用本脚本生成 .env，再补写该行并重跑本脚本校验）"
  echo "     2) 本次临时传入：FEISHU_ADMIN_OPEN_ID=xxx bash setup-server.sh"
  echo "   注意：该值属内部标识，只放服务器 .env，禁止提交进仓库、写入文档或日志。"
fi
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_NAME="${DB_NAME:-merchant_task_prod}"

if [ -z "$DB_USER" ] || [ -z "$DB_PASS" ]; then
  echo "!! 未能从 $BACKEND_ENV 读到 DB_USER/DB_PASS，请用环境变量传入："
  echo "   DB_USER=xxx DB_PASS=xxx  bash setup-server.sh"
fi

# DB 口令兜底守卫（#OPS-48）：空值或公开 dev 兜底值 → 绝不写进 .env，明确报错并中止本步骤
# （DEV_FALLBACK_DB_PASS 与 api-py app/core/config.py::DEV_FALLBACK_DB_PASS / src/config.js 同源；
#   它**仅用于「拒绝把它写进 .env」的比对**，绝不作为默认值使用）
DEV_FALLBACK_DB_PASS="root123"
if [ -z "$DB_PASS" ] || [ "$DB_PASS" = "$DEV_FALLBACK_DB_PASS" ]; then
  echo "!! [3/5] DB_PASS 为空或等于公开 dev 兜底值 —— 拒绝写入自动化 .env（否则会用兜底口令去连生产库）。"
  echo "   如何提供真实口令（二选一）："
  echo "     1) 环境变量：DB_PASS=xxx bash setup-server.sh"
  echo "     2) 先写入 automation/.env（服务器 <SERVER_ROOT>/automation/.env，权限 600）：DB_PASS=<真实口令>，再重跑本脚本"
  echo "   本步骤中止（未生成/未改动 .env，也未连接任何数据库）。"
  exit 1
fi

if [ -f .env ]; then
  echo "   已存在 .env，保留现有内容（如需重写请先删除 automation/.env）"
else
  cat > .env <<EOF
# 拍拍二手资费同步自动化 · 服务器实际配置（勿提交）
DB_HOST=$DB_HOST
DB_PORT=$DB_PORT
DB_USER=$DB_USER
DB_PASS=$DB_PASS
DB_NAME=$DB_NAME
FEISHU_APP_ID=$FEISHU_APP_ID
FEISHU_APP_SECRET=$FEISHU_APP_SECRET
FEISHU_ADMIN_OPEN_ID=$FEISHU_ADMIN_OPEN_ID
FEE_RULE_URL=https://learn-jdm.jd.com/knowledge/rule/detail?ruleId=1323517376196349952
FEE_SCRAPE_TIMEOUT_MS=120000
EOF
  echo "   已写入 automation/.env"
fi

echo "==> [4/5] 校验配置与数据库连接"
node -e "import('./src/config.js').then(async m=>{const {q}=await import('./src/db.js');const c=m.config;console.log('  DB        = '+c.db.host+':'+c.db.port+'/'+c.db.database);console.log('  FEISHU_APP= '+c.feishu.appId+' -> '+c.feishu.adminOpenId);const r=await q('SELECT COUNT(*) c FROM fee_config');console.log('  fee_config rows = '+r[0].c);}).catch(e=>{console.error('校验失败: '+e.message);process.exit(1)})"

echo "==> [5/5] 定时（每月1日 09:00）示例："
echo "  0 9 1 * * cd $SELF_DIR && $(command -v node) src/index.js --apply >> $SELF_DIR/reports/cron.log 2>&1"
echo ""
echo "  启用："
echo "  (crontab -l 2>/dev/null; echo '0 9 1 * * cd $SELF_DIR && $(command -v node) src/index.js --apply >> $SELF_DIR/reports/cron.log 2>&1') | crontab -"
echo ""
echo "  先跑一次 dry-run（不写库）确认： cd $SELF_DIR && node src/index.js"
echo ""
if [ "$NOTIFY_CONFIGURED" = "0" ]; then
  echo "⚠️  提醒：FEISHU_ADMIN_OPEN_ID 未配置 → 安装完成后飞书通知处于「跳过推送」状态；"
  echo "    补写 automation/.env（600）后重跑本脚本的 [3/5]~[4/5] 校验即可启用。"
  echo ""
fi
echo "✅ 完成。注意："
echo "  · 服务器需能出网访问 https://learn-jdm.jd.com 与 https://open.feishu.cn"
echo "  · 首次建议 node src/index.js（dry-run）核对“需更新/未匹配”，再上 --apply"
