# 店铺数据上传剥离与数据分析专区方案

> 版本：v2.0  
> 创建日期：2026-08-06  
> 状态：方案定稿（待实施）  
> 决策确认：4 项决策点已由用户确认（见 §5）  
> 关联文档：`project/docs/阶段二任务体系.md`、`project/03-长期路线.md`（V3 数据分析规划）、`project/docs/阶段隔离规则与阶段二任务清单.md`

---

## 一、背景与目标

### 1.1 背景

阶段二（开店搭建）的 **T2.5 店铺数据上传**（stage_id = `shopdata`，6 个二级任务）在后续 **阶段三（数据分析）** 中仍需要该模块。当前它作为阶段二第 5 个一级任务展示，与"开店搭建"语义耦合，不利于阶段三直接复用。

### 1.2 目标

1. T2.5 店铺数据上传从阶段二任务列表中**剥离**，不再作为"开店搭建"的一级任务展示
2. 侧边栏底部新增独立「**数据分析专区**」：**店铺数据上传** + **数据看板（含 AI 经营分析）** 两个入口
3. 阶段二进度**完全不计入** shopdata；数据库**单独列项、单独记录**
4. 阶段三可直接复用数据模块（表、接口、组件、入口均不绑定阶段二）

---

## 二、现状盘点（2026-08-06 代码已核实）

| 项 | 现状 |
|------|------|
| T2.5 任务 | stage_id = `shopdata`，6 个二级任务：T2.5.1 星级（DataForm）、T2.5.2~4 交易/流量/商品 Excel（ExcelUpload）、T2.5.5 商品数量（DataForm）、T2.5.6 健康分（DataForm） |
| 数据存储 | 后端 `shop_*` 6 张表（star/trade/traffic/product/product-count/health-score），**独立于任务表**，已解耦 |
| 数据接口 | `/api/shop/*` 上传/保存、`/api/shop/summary` 看板聚合、`/api/shop/analysis` AI 经营分析（后端 `ai` 模块 + 每日限流 + 缓存） |
| 数据看板 | `pages/stage2/data-board.vue`（709 行）：时间维度切换 + 指标卡片 + **AI 经营分析区块（analysis-card，内嵌于看板页，非独立页面）** |
| 侧边栏 | `Stage2Sidebar.vue`：Logo → 阶段标识 → 阶段进度 → 一级任务导航（T2.1~T2.5 循环）→ 用户信息；无独立"专区"概念 |
| 阶段三规划 | `03-长期路线.md` V3 已规划「数据分析看板、数据任务、商家分层」——数据模块是阶段三核心 |
| 关键耦合 | `PHASE2_STAGE_IDS = ['brand','listing','optimize','activity','shopdata']`（前端 `constants/stage2.ts` + 后端 `shared/enums/index.ts` 各一份）；侧边栏导航与阶段进度统计都按该数组遍历 |

**核心结论：数据层已解耦（shop_* 表独立于任务体系）；剥离的难点在「阶段归属枚举」与「导航呈现」两层。**

---

## 三、方案设计（v2）

### 3.1 剥离方式：逻辑剥离 + 独立专区（推荐）

**不做物理迁移**（不删阶段二任务数据、不动 shop_* 表），做**归属与呈现层剥离**：

| 层 | 改动 |
|------|------|
| **数据层** | ✅ **零改动**：`shop_*` 表、`/api/shop/*`、`/api/shop/analysis`、AI 分析缓存全部保留 |
| **任务归属** | 前后端 `PHASE2_STAGE_IDS` 移除 `shopdata`（剩 brand/listing/optimize/activity 4 个）；任务数据仍留库（stage_id=shopdata 保留），仅不再计入阶段二导航与进度 |
| **数据库记录** | stage 表保留 `shopdata` 行（单独列项）；任务进度仍记录于 `merchant_task_progress`（按 shopdata stage_id 单独记录，与阶段二分离统计） |
| **前端呈现** | 侧边栏新增「数据分析专区」区块；阶段二页面不再渲染 shopdata 分组 |
| **路由** | 数据看板提升为独立页 `pages/data-center/index`（内容整体搬移 data-board 逻辑，含 AI 分析区块）；保留 `pages/stage2/data-board` 旧路由兼容跳转 |

### 3.2 侧边栏「数据分析专区」设计（Stage2Sidebar.vue 底部新增）

```
┌─────────────────────┐
│  商家任务中心        │
│  2 开店搭建          │
│  阶段进度 xx/xx      │
│  ──────────────     │
│  ① 品牌申请  x/x     │
│  ② 商品发布  x/x     │
│  ③ 商品优化  x/x     │
│  ④ 店铺活动  x/x     │
│  ──────────────     │
│  📊 数据分析专区      │  ← 新增分区标题
│  ▸ 店铺数据上传       │  ← 独立数据上传页入口
│  ▸ 数据看板          │  ← 看板 + AI 经营分析（同页一体）
│  ──────────────     │
│  用户信息            │
└─────────────────────┘
```

- **分区位置**：一级任务导航之后、用户信息之前（侧边栏下方）
- **分区入口**（2 个，已按用户决策 4 确认）：
  1. **店铺数据上传** → 进入**独立数据上传页**（见 3.3）
  2. **数据看板** → 进入数据看板页（指标 + AI 经营分析一体，AI 区块已在页内，零改动）
- **视觉**：沿用现有侧边栏样式与设计 Token，不引入新组件库
- **AI 分析输出的指标名册（#PB-32 · #PB-33，指针）**：AI 回答文本里的指标名一律中文（如「商品信息健康分」「成交金额」）；**名册与用词对齐规则登记在唯一真源 `project/docs/后端技术方案.md` §10.6**（经营分析 50 键 + 标题优化入参 9 键；与前端 `SHOP_METRIC_LABELS` / `SHOP_SUMMARY_TYPES` 现存 0 处用词差异），本文件不重复登记。

### 3.3 店铺数据上传独立页（用户决策 4：②进入独立页）

新建 `pages/data-center/upload.vue`：

- **内容**：6 个数据上传任务（T2.5.1~T2.5.6）以列表/卡片形式展示，展开后复用现有 `DataForm.vue`（星级/商品数量/健康分）与 `ExcelUpload.vue`（交易/流量/商品）组件
- **数据**：任务定义仍来自 `GET /api/task/stages`（stage_id=shopdata 分组），进度来自 `merchant_task_progress`（单独记录）——**不新增后端接口**，仅前端以独立路由/页面重新组织入口
- **解锁规则（用户决策 5 确认）**：**独立于阶段二解锁**；解锁条件 = **完成阶段二「商品发布」（T2.2，listing）全部任务**。即：商家完成 T2.2 全部任务后即解锁数据上传页，无需等待阶段二全部完成。该规则为**独立解锁判定**（并行于"完成阶段一解锁阶段二"），实现上需后端在进度接口提供 `data_center_unlocked` 判定（依据 listing stage 任务完成情况），前端数据上传页据此展示锁定/解锁态
- **健康分卡片跳转入口（#F-29，2026-09-15 用户要求）**：商品信息健康分卡片（T2.5.6）描述行右侧新增「去商品体检」跳转按钮，**文案与链接全部取自任务数据**（`second_level_task.actionText` / `actionUrl`，前者当前库值「去京麦商品体检」，链接 `https://wares-jdm.jd.com/ware/commodity-inspection`）——前端不硬编码文案；`actionUrl` 为空/null 或文案缺失即整块不渲染（不出现空按钮）；点击在 tap 手势同步栈内新窗口打开（H5），统一走 `src/utils/link.ts` 的 `openExternalLink()`（`#ifdef H5` + `typeof window` 双保险，其它平台 no-op 返回 false，不产生跨端报错）；**常驻入口**：与任务完成态无关（已完成卡片同样显示）。**范围**：按任务单「不得影响其它 5 张卡片」约束，仅 `form:health-score` 渲染（范围常量 `DATA_CENTER_ACTION_INTERACTIONS`）；注意库中 T2.5.1~T2.5.6 六个任务均已配置 `actionText`/`actionUrl`，若后续要求 6 张卡片统一渲染，只需在该常量追加交互键（前端一行改动）——**已于 #F-30 落地：白名单常量删除，改为纯数据驱动（见下条）**
- **健康分 5 字段改非必填（#F-29，用户口径「5 个字段全留空 = 全是 0，分析侧跳过这一项」）**：`avgScore` + 4 个分段 count 去掉必填约束（保留 0-100 / 非负整数范围校验），留空由 schema 声明 `emptyAsZero` 统一以 **0** 提交（不是 null、不是省略），与后端约定的语义一致——**全 0 = 该商家本次无该项数据**；`avg_score=0` 作为哨兵值的判定 owner 在后端分析侧（真源登记见 `后端技术方案.md`，由 py-backend 承接），前端只负责口径一致的提交

- **6 张卡片统一跳转入口（#F-30，2026-09-15 用户裁决）**：删除 #F-29 的交互键白名单常量 `DATA_CENTER_ACTION_INTERACTIONS`，`shouldShowTaskAction` 改为**纯数据驱动**——`actionText` 与 `actionUrl` 双非空即渲染，读库现状 6 张卡片全部渲染（T2.5.1「去店铺星级页」/ T2.5.2~4「去商智下载」/ T2.5.5「去京麦商品列表」/ T2.5.6「去京麦商品体检」），点击均走 `src/utils/link.ts` 的 `openExternalLink()` 新窗口打开对应 `actionUrl`（常驻入口，与完成态无关）。
- **按钮布局断点（#F-30 用户确认）**：≥900px 三列时按钮与描述同行；**≤900px 换行到描述下方**（不换行会把描述压成每行 3~7 字，实测数据见 `upload.vue` 样式注释），该策略已由用户确认并留痕在样式注释中。
- **Excel 上传参数收口（#F-30）**：`api/stage2.ts` 的 `uploadShopExcel` 移除从未被调用方传入的死参数 `timeRange`（grep 全仓仅 `ExcelUpload.vue` 一处调用且只传 2 参），并同步移除共享 helper `uploadFileViaFetch` 中已无调用方的 `fields` 选项及其 FormData 分支；时间范围改由后端按文件区间自行推导（语义修正归 `#PB-24-2`）。

- **已完成角标改右上角绝对定位（#F-31，2026-09-15 用户要求）**：`.upload-card__badge` 由 header flex 行内元素改为 `position: absolute` 贴卡片右上角（`top/right` 取 `$up-space-2`，卡片容器补 `position: relative`）→ **脱离文档流**，完成态与未完成态下「按钮 + 描述」可用宽度完全一致（改前实测：完成态 descW 119px / 未完成态 184px，角标占 65px；改后两态均为 184px）。长标题防覆盖：仅完成态给**标题**加右侧避让 `padding-right: calc($up-space-12 + $up-space-5)`（=68px ≥ 角标 57px + 间距 8px），只影响标题换行盒、不影响按钮/描述宽度。
- **卡片不再折起（#F-31，2026-09-15 用户要求）**：删除 header 的 `@tap="toggleCard"` 与交互区 `v-show`，交互区（Excel 上传 / 数据表单）**常显**；一并删净 `collapsedMap` / `toggleCard` / `upload-card--expanded`（grep 全仓 0 命中）与失效的 `.upload-card__body @tap.stop`（其唯一保护对象是被删除的折叠 tap）。勾选圈 `@tap.stop="store.toggleTask()"` 保留（手动完成态，与折叠无关）。

- **Excel 导入逐行问题清单（#PB-24-3，承接 #PB-24-2 响应契约）**：`components-local/stage2/ExcelUpload.vue` 状态区下方新增「导入结果」区——**汇总行**（`共 N 行 / 写入 X 行 / 跳过 Y 行 / 修正 Z 行`，数值取后端 `total_rows/count/skipped/normalized`；文案片段集中在 `constants/stage2.ts`）+ **逐行问题清单**（`第 <Excel 物理行号> 行 · <字段中文名|库列名> · <后端 message>`；字段名经 `SHOP_METRIC_LABELS` 映射，**原因文案原样用后端 `message`**，前端不另造）+ `issues_truncated` 时的截断提示（`仅显示前 200 条问题，完整记录见服务端日志`）。`skipped==0 && normalized==0`（`issues` 为空）时**只渲染汇总行、不渲染清单**，避免全合法文件下出现空框。**HTTP 200（全部行皆坏、count=0）也是成功响应** → 仍渲染汇总行 + 清单，不显示为「上传失败」。清单限高 `calc($up-space-12 * 5)`（240px）并内部滚动，避免 200 条把卡片撑爆、破坏 3 列等高布局。类型层 `api/stage2.ts` 新增 `ShopExcelIssue` / `ShopExcelUploadResult`（字段全部可选，兼容老响应）。

### 3.4 阶段三复用路径（设计验证）

| 复用项 | 路径 |
|------|------|
| 数据入口 | 侧边栏数据分析专区（已独立于阶段二） |
| 数据源 | `shop_*` 表 + `/api/shop/summary` + `/api/shop/analysis`（零改动） |
| 任务绑定 | 阶段三"数据分析引导任务"可新建 stage 关联现有 shopdata 数据，或复用 shopdata 任务（数据与任务已解耦，两种方式均成立） |
| 扩展点 | 专区结构支持后续加"经营周报""健康评分"等新卡片 |

---

## 四、改动清单

| # | 端 | 文件 | 改动 |
|----|------|------|------|
| 1 | 前端 | `project/src/constants/stage2.ts` | `PHASE2_STAGE_IDS` 移除 `shopdata` |
| 2 | 前端 | `project/src/utils/stage2.ts` | `filterStage2Stages` 按数组过滤自动生效；核对进度口径（33→27） |
| 3 | 前端 | `project/src/components-local/stage2/Stage2Sidebar.vue` | 底部新增「数据分析专区」区块（数据上传 / 数据看板 2 入口） |
| 4 | 前端 | `project/src/pages/stage2/index.vue` | 移除 T2.5 分组渲染 + 顶部 board-entry（迁至专区） |
| 5 | 前端 | 新建 `project/src/pages/data-center/index.vue` | 数据看板独立页（搬移 data-board 逻辑，含 AI 分析区块） |
| 6 | 前端 | 新建 `project/src/pages/data-center/upload.vue` | 店铺数据上传独立页（复用 DataForm/ExcelUpload） |
| 7 | 前端 | `project/src/pages.json` | 新增 `pages/data-center/index`、`pages/data-center/upload` 路由；保留 `pages/stage2/data-board` 兼容 |
| 8 | 后端 | `backend/src/shared/enums/index.ts` | `PHASE2_STAGE_IDS` 移除 `shopdata` |
| 9 | 后端 | stage/任务数据 | **零改动**：stage 表 shopdata 行保留（单独列项）；`merchant_task_progress` 记录保持（单独记录） |
| 10 | 文档 | `阶段二任务体系.md` / `阶段隔离规则` / `03-长期路线.md` | T2.5 标注"已剥离至数据分析专区"；V3 章节补充专区规划；数据库列项说明 |
| 11 | 前端 | 新建 `project/src/utils/link.ts` | `openExternalLink()`：外链新窗口打开统一封装（`#ifdef H5` + `typeof window` 保护；非 H5 端 no-op），#F-29 |
| 12 | 前端 | `project/src/pages/data-center/upload.vue` | 健康分卡片描述行新增跳转入口（`v-if` 双字段判空、`@tap.stop`、常驻显示）+ 按钮样式（Token：caption 字号 / `$up-space-1`+`$up-space-3` 内边距 / `$up-radius-sm` / `$u-primary`；不照抄 TaskCard 尺寸），#F-29 |
| 13 | 前端 | `project/src/constants/stage2.ts`、`project/src/utils/stage2.ts`、`project/src/components-local/stage2/DataForm.vue` | 健康分 5 字段非必填（去 `required`）、新增 `emptyAsZero` 字段声明与提交侧「空→0」（留空与范围校验口径见 §3.3），**#F-29** |
| 14 | 前端 | `project/src/pages/data-center/upload.vue`、`project/src/constants/stage2.ts`、`project/src/api/stage2.ts` | **#F-30**：删除交互键白名单常量，跳转入口改纯数据驱动（6 张卡片统一）；≤900px 换行策略注释留痕；移除死参数 `uploadShopExcel(timeRange)` 与共享 helper 中已无调用方的 `fields` 分支 |
| 15 | 前端 | `project/src/pages/data-center/upload.vue` | **#F-31**：已完成角标改卡片右上角绝对定位（不占位、两态按钮/描述等宽，长标题加 Token 避让）；取消卡片折起（交互区常显，删净 `collapsedMap`/`toggleCard`/`upload-card--expanded` 与失效的 body `@tap.stop`） |
| 16 | 前端 | `project/src/components-local/stage2/ExcelUpload.vue`、`project/src/api/stage2.ts`、`project/src/constants/stage2.ts` | **#PB-24-3**：Excel 导入结果区（汇总行 + 逐行问题清单 + 截断提示 + 清单限高滚动）；上传响应类型扩展 `ShopExcelIssue`/`ShopExcelUploadResult`（全可选）；新增文案常量（§8.2 #47~#49） |

**预计影响面**：前端 5 改 + 2 新建 + 路由；后端仅 1 个枚举常量；数据与接口零改动。

---

## 五、决策确认记录（2026-08-06 用户确认）

| # | 决策点 | 结论 |
|----|--------|------|
| 1 | T2.5 任务数据是否留库 | **保留**：stage_id=shopdata 任务数据留库，仅前端不渲染（零迁移风险，阶段三直接复用） |
| 2 | 阶段二进度口径 | **完全不计入**：阶段二进度 33→27；**数据库单独列项、单独记录**：stage 表保留 shopdata 行，`merchant_task_progress` 按 shopdata 独立记录，与阶段二分离统计 |
| 3 | 数据看板旧路由 | **保留**：`pages/stage2/data-board` 保留兼容跳转，避免旧链接失效 |
| 4 | 数据上传入口形态 | **② 进入独立数据上传页**（`pages/data-center/upload.vue`），不嵌入侧边栏 |
| 5 | 数据上传页进入权限 | **独立于阶段二解锁**；解锁条件 = **完成阶段二「商品发布」（T2.2，listing）全部任务**；需后端提供 `data_center_unlocked` 判定 |

## 六、遗留待确认项

1. ~~数据上传页的进入权限~~ ✅ 已确认（决策 5：独立解锁，T2.2 商品发布全部完成解锁）
2. **AI 分析限流**：数据看板独立后，AI 每日限流（`AI_DAILY_LIMIT`）是否维持每商家维度不变（推荐维持）——默认不动
3. **数据上传页是否展示任务完成状态**（如进度 x/6）——默认展示，与任务进度单独记录一致

---

## 七、实施分工（按协作体系派单，实施时执行）

| 角色 | 任务 |
|------|------|
| 前端 Agent（阶段二） | 改动清单 #1~#7（常量/工具/侧边栏专区/页面迁移/新页/路由） |
| 后端 Agent | 改动清单 #8（enums 移除 shopdata）+ 新增 `data_center_unlocked` 解锁判定（依据 listing stage 任务完成情况，进度接口返回） |
| 测试 Agent | 回归：阶段二 4 组任务进度、数据上传独立页、看板+AI、旧路由兼容 |
| 规划 Agent | 同步更新任务体系/隔离规则/长期路线文档（改动清单 #10） |
