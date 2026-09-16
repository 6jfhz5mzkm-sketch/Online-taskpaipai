# 拍拍二手资费标准 · 月度自动抓取/比对/更新/通知

> 独立运行（自带依赖），由系统定时器（crontab / Windows 任务计划程序）每月 1 日触发。
> 数据用于任务 T1.1.3「查询类目资费」所展示的 fee_config 基础资费。

## 一、做什么

每月 1 日抓取《拍拍二手开放平台类目资费标准》页面，抽取各二级类目的
**运营支持服务费率 / 交易服务费率 / 四档保证金（GMV<5万、5-10万、10-30万、≥30万）**，
与数据库 fee_config 逐项比对：

- **有调整** → 更新库表 + 生成变更报告；
- **无调整** → 也生成报告并通知「无变更」。

### 比对口径（已确认）
- 沿用现有 fee_config **每二级类目一条**的模型，不扩 schema。
- 规则行 → 二级类目：按「二级类目名在规则行三级类目范围内（支持 、，逗号分组）匹配，否则回退该一级类目下的「其他三级类目」档」。
- 页面含「试运营阶段」保证金列与「特殊品牌资费」表：**本期不纳入**（fee_config 无对应字段；brand override 未启用）。

## 二、目录

    automation/
      package.json
      .env.example          # 环境变量样例
      src/
        index.js            # 入口（抓取->映射->比对->更新->报告->通知）
        scrape.js           # Playwright 无头渲染抓取
        parser.js           # DOM 表格网格化解析（处理 rowspan/colspan）
        mapping.js          # 规则行 -> category_id 映射
        compare.js          # 比对（desired vs DB）
        update.js           # --apply 时写库（事务，整行合并更新，防止空值覆盖）
        report.js           # 生成报告 & 通知文本
        notify.js           # 飞书应用消息发给指定 open_id + 落库 feishu_notification
        config.js           # 环境配置（读取 automation/.env，回退 backend/.env.local）
        db.js               # mysql2 连接池
      reports/              # 报告与规则原始快照输出目录

## 三、安装（部署机）

    cd automation
    npm install
    # 安装 Playwright 浏览器（部署机若已有系统 Chrome/Edge 可跳过）
    npx playwright install chromium
    cp .env.example .env   # 并填写 FEISHU_ADMIN_OPEN_ID 等

> **注意：`FEISHU_ADMIN_OPEN_ID` 必须由 `automation/.env` 注入**（`setup-server.sh` 自 2026-09-16 起**不再内置任何默认值**）：
> 服务器上的位置 = **`<SERVER_ROOT>/automation/.env`，权限 600**；该值属内部标识（敏感形态），**不落仓库、不写入文档/日志/汇报**。
> 未配置时安装脚本会**显式跳过并打印指引**（不中止安装），运行期 `src/notify.js` 会打印「未配置 FEISHU_ADMIN_OPEN_ID，跳过推送」并返回 `sent=false`（抓取/比对/写库不受影响）。

> 启动浏览器优先级：FEE_SCRAPE_BROWSER_PATH > 系统 Chrome / Edge > Playwright 自带 Chromium。
> 若部署机无系统浏览器且不想装 Playwright，请用 FEE_SCRAPE_BROWSER_PATH 指向已有 Chrome。

## 四、运行

    # 仅比对 + 通知（默认，不写库）—— 首次建议先跑这个
    node src/index.js

    # 有调整时写库
    node src/index.js --apply

    # 用本地规则快照做离线比对（调试 / 验证映射）
    node src/index.js --fixture reports/fee-rule-fixture-subset.json

- 输出：reports/fee-sync-report-<时间戳>.md、reports/fee-rule-raw-<时间戳>.json（抓取原始快照，可审计）。
- 通知：无论是否有调整都发飞书文本消息给 FEISHU_ADMIN_OPEN_ID，并写入 feishu_notification 表。
- 失败：会尝试发「同步失败」通知，并以非零码退出（便于定时器感知）。

## 四.5、备份（本次新增：更新前必备份）

- **--apply 写库前会自动备份**：先用 `mysqldump`（`--default-character-set=utf8mb4`，避免中文乱码）把整个库备份到 `automation/backups/<库名>-<时间戳>.sql`，备份成功后才写库。
- **备份失败则中止**（绝不未备份就更新），并以非零码退出，便于定时器感知。
- 手动备份：`node src/index.js --backup-only`。
- 备份目录可用 `FEE_BACKUP_DIR` 覆盖；建议定期清理（`automation/backups/` 已在 .gitignore）。

## 四.6、抓取内容校验 + 差异熔断（防错写）

每次抓取后、写库前会做两道检查，任一不过即**中止并通知**（不写库）：

1. **抓取结果校验**（`validateScrape`）：有效规则行 < `FEE_SYNC_MIN_ROWS`(默认20)、运营/交易费率越界、缺保证金档位、类目名缺失 → 中止。
2. **与上次基线差异熔断**（`compareSnapshots`）：
   - 基线 = 上次**成功应用**的规则快照（`reports/fee-snapshot-baseline.json`，首次成功 `--apply` 时建立）；
   - 本次快照与基线按「类目作用域」逐行比对费率/保证金，若**行数变化**或**费率变更**超过阈值（默认 30%）→ 中止 + 通知。
   - 阈值可用环境变量调：`FEE_SYNC_ROW_CHANGE_LIMIT`、`FEE_SYNC_FEE_CHANGE_LIMIT`、`FEE_SYNC_MIN_ROWS` 等。

> 目的：抓不到、解析异常、或与历史差异过大（疑似页面改版/解析错位/编码问题）时，绝不把错误数据写进 `fee_config`，而是中止并人工核对。

## 四.7、数据库口令兜底守卫（#OPS-48，防「静默用兜底口令连生产」）

- **动机**：本工具在**生产库**上按月运行。旧行为在 `automation/.env` 缺失或键名写错时会**静默**用公开 dev 兜底口令去连生产库；api-py 对同类兜底有启动期 fail-fast，自动化侧此前没有 → 口径不一致（现已在 `src/config.js` 补齐，与 `api-py/app/core/config.py::validate_startup_settings` 同款）。
- **判定（集中在纯函数 `guardDbPass`，可单测、不建连接）**：
  1. 提供了**真实口令**（≠ 兜底值）→ **行为完全不变**，照常连库；
  2. **生产形态**（`DB_NAME` 以 `_prod` 结尾 **或** `DB_HOST` 非本机）**且**口令为空或等于兜底值 → **中文报错 + 退出码 1**，拒绝启动（不回落到兜底口令）；
  3. **开发形态**（本机 + `merchant_task`）且口令为空 → 允许沿用兜底值，但打印**显著 warning**（本地开发可用）。
- **安装脚本侧**：`setup-server.sh` 在生成 `.env` 之前同样拦截——`DB_PASS` 为空或等于兜底值时**报错并中止该步骤**（不写 `.env`、不连接数据库）。
- **如何修复**：在服务器 `<SERVER_ROOT>/automation/.env`（权限 600）配置真实 `DB_PASS`，或用环境变量 `DB_PASS=...` 临时传入；生产库口令禁止使用任何公开 dev 兜底值。

## 五、认证/鉴权

- 规则页为微前端 SPA，**当前无需登录即可渲染**（已实测）。
- **提示**：若未来页面改为需登录才能查看，或微前端加载路径变化导致抓取失败，需重新处理登录态 / 选择器。
- 脚本仅在探测到失败时会失败退出，不会静默写入错误数据。

## 六、系统定时（每月 1 日）

### Linux / macOS（crontab）

    crontab -e
    # 每月 1 日 09:00 执行（--apply 才写库；日志落 reports/cron.log）
    0 9 1 * * cd /path/to/automation && /usr/bin/node src/index.js --apply >> /path/to/automation/reports/cron.log 2>&1

### Windows（任务计划程序）
1. 打开「任务计划程序」→「创建任务」。
2. 触发器：每月，日期选 1，时间 09:00。
3. 操作：node，参数 src/index.js --apply，起始于 <项目>/automation。

## 七、上线前必做

1. 在部署机跑 node src/index.js（dry-run），核对报告：需更新数、未匹配类目。
2. 由于规则页比库表更细，「未匹配到规则」列表需人工确认映射（是否属于「其他三级类目」档）；
   确认无误后再上 --apply。
3. 首次抓取会生成 fee-rule-raw-*.json，建议留档，便于追溯规则变化。
4. 确认 FEISHU_ADMIN_OPEN_ID 能收到消息（配置错误会记录到 feishu_notification）；该值只放服务器 `automation/.env`（600），安装脚本不再内置默认值（未配置即「跳过推送」）。

## 八、已知边界

- **映射粒度**：规则页粒度（一/二/三/四级）比库表（仅二级）细；fee_config 每二级类目仅存一条「代表档」，
  同一二级类目下若规则按三级拆多档（如「二手手机」普通 4.5% / 官翻 3.0%），库表只保存匹配档，无法完整表达。
- **试运营保证金 / 品牌覆盖**：本期未纳入（无字段/未启用），后续可扩展。
- **页面改版风险**：若知识点子应用 DOM 结构变化，需同步更新 parser.js 的选择器与列定义。
- **浏览器依赖**：部署机需能启动 Chromium；1GiB 轻量机建议每次冷启动跑完即退（脚本已 await browser.close()）。
