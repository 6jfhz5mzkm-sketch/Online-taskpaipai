# 阶段隔离规则与阶段二任务清单基准（R2）

> 版本：v2.1
> 创建日期：2026-08-06（替代同日 v1.0 草稿）
> 更新日期：2026-08-06
> 状态：进行中（待总控验收）
> v2.1 变更（2026-08-06）：依据《数据分析专区方案》v2.0 同步 T2.5 剥离——阶段二计入进度二级任务 33 → 27；shopdata（6 个）移出、数据与进度单独记录；数据上传页独立解锁（T2.2 商品发布全部完成）
> 任务来源：#P-002 · 阶段二重新开发
> 数据来源：`project/docs/阶段二任务体系.md`（v1.1）、`project/02-规划说明.md`（v1.2）、`project/docs/后端技术方案.md`、`project/docs/任务管理后台开发标准.md`、阶段一前端实现（`project/src/pages/index/index.vue`）

---

## 一、阶段隔离规则

### 1.1 核心定义

**阶段一（入驻准备）与阶段二（开店搭建）是两个独立任务体系，二者之间唯一的耦合点是「解锁」：商家完成阶段一全部任务后，阶段二才开启。**

| 维度 | 阶段一：入驻准备 | 阶段二：开店搭建 |
|------|----------------|----------------|
| 任务体系 | 一级任务 T1.1–T1.5（18 个二级任务 + 支线提示） | 一级任务 T2.1–T2.4（27 个计入进度二级任务）+ 数据分析专区（T2.5 店铺数据上传，6 个，单独记录） |
| 解锁前提 | 商家注册后默认开放 | 阶段一全部启用任务完成 |
| 任务间依赖 | 各一级任务内部按序引导 | T2.1–T2.4 互相独立，任意顺序完成；专区数据任务独立于阶段二进度（完成 T2.2 全部任务即解锁） |
| 完成判定 | T1.1–T1.5 全部二级任务完成 | T2.1–T2.4 全部 27 个二级任务完成（shopdata 不计入阶段二进度） |
| 解锁后表现 | 保持已完成展示 | 阶段二入口开启、任务中心正常展示 |
| 相互影响 | 阶段二完成不影响阶段一 | 阶段一状态变化影响阶段二可见性（见 §3.5） |

### 1.2 命名规范（关键，防混淆）

现有系统把阶段一内部的 5 个一级任务建模为 5 个 `stage`，其中 **`setup` 已被阶段一 T1.2「资质材料准备」占用**。R2 各任务单里出现的「setup 阶段任务」若直接使用 `setup` 会与既有 stage 冲突，因此规定如下唯一标识：

| 层级 | 标识 | 说明 |
|------|------|------|
| 大阶段 phase-1 | `onboarding`（沿用 `merchant.current_stage`） | 入驻准备，商家注册默认值 |
| 大阶段 phase-2 | `shop_setup`（`merchant.current_stage` 解锁值） | 开店搭建；**禁止**用 `setup` 指代 |
| 阶段一 stage_id（既有） | `onboarding` / `setup` / `application` / `review` / `opening` | 对应 T1.1–T1.5 |
| 阶段二 stage_id（新增） | `brand` / `listing` / `optimize` / `activity`（计入进度）；`shopdata`（已剥离至数据分析专区，stage 行保留单独列项、进度单独记录） | 对应 T2.1–T2.4 + 专区 T2.5 |

> 硬性约定：阶段二相关代码、数据、文档中不得使用 `setup` 作为阶段标识；口头简称「setup 任务」一律按 `shop_setup` / `brand|listing|optimize|activity|shopdata` 理解。

### 1.3 隔离边界与例外

| 场景 | 规则 |
|------|------|
| 新商家 | 默认阶段一开放、阶段二锁定 |
| 存量商家（已开店） | 上线初始化时由运营在管理后台「一键标记阶段一完成并解锁」，避免存量商家被卡在门外 |
| 停用任务 | 阶段判定只统计 `status=1`（启用）任务；停用任务自动剔除 |
| 默认已完成任务 | `default_completed=1` 的任务按已完成计入 |
| 支线任务 | 不参与解锁判定（`branch_checked` 仅提示）；若业务要求必做，另行确认 |
| 阶段一无启用任务 | 视为异常配置，按未解锁处理并提示运营检查 |
| 新任务上线 | 阶段一新增启用任务后，未完成则该商家回到锁定态（严格派生口径） |

---

## 二、阶段二任务清单基准（27 个计入阶段二进度 + 6 个专区单独记录，md → 数据字段）

### 2.1 字段映射总则

| `阶段二任务体系.md` 内容 | 数据字段 | 映射规则 |
|-------------------------|---------|---------|
| 任务 ID（T2.x.y） | `task_id`（second_level_task） | 直接沿用，如 `T2.1.1` |
| 一级任务归属（T2.x） | `first_level_task_id` | 直接沿用，如 `T2.1` |
| 一级任务 → 阶段 | `stage_id` | 按 §1.2：brand / listing / optimize / activity（计入阶段二进度）；shopdata（已剥离至数据分析专区，stage 行保留、进度单独记录） |
| 任务名称 | `title` | 直接沿用 |
| 任务类型（引导/功能/跳转/上传/填写） | `type` | 数据模型枚举 mandatory/suggested/guide；阶段二默认 `guide`；专区数据上传任务（T2.5）建议 `suggested`（可后台调整） |
| 完成标准 | `completion_type` | 点击已完成 → `click_read`；填写/上传提交 → `manual_submit` |
| 跳转链接 | `action_url` | 外部京麦/商智 URL；内部功能（商标搜索、上传）填空，由前端组件实现 |
| 引导内容/字段说明 | `detail` | 从 md 迁移为 Markdown 详情，保留要点 |
| 任务顺序 | `sort_order` | 按 md 章节顺序 1–27（阶段二计入进度）；shopdata 6 条单独排序、与阶段二分离记录 |
| 特殊功能 | 前端组件 / 后端接口 | 见 §2.3 |

### 2.2 任务对照表（T2.1–T2.4 计入进度 27 个；T2.5 专区单独记录 6 个，合计 33）

#### T2.1 品牌申请（`stage_id=brand`，4 个）

| 任务 ID | 任务名称 | type | completion_type | action_url | 实现要点 |
|---------|---------|------|----------------|------------|---------|
| T2.1.1 | 了解品牌申请规则 | guide | click_read | - | detail：申请条件/审核周期/所需材料 |
| T2.1.2 | 查询商标注册号 | guide | manual_submit | -（内部接口） | 商标搜索组件；输入品牌名 → 注册号列表，模糊搜索；查询成功即完成 |
| T2.1.3 | 引导去京麦完成品牌申请 | guide | click_read | 京麦首页-店铺-品牌管理（外链） | 跳转按钮 + 步骤引导 |
| T2.1.4 | 了解品牌审核跟进 | guide | click_read | - | detail：审核周期/催审渠道（拍拍商家企微） |

#### T2.2 商品发布（`stage_id=listing`，14 个）

| 任务 ID | 任务名称 | type | completion_type | action_url | 实现要点 |
|---------|---------|------|----------------|------------|---------|
| T2.2.1 | 了解商品发布流程 | guide | click_read | 京麦商品发布页面 | 智能/普通发品说明，二手优先普通发品 |
| T2.2.2 | 选择类目、品牌及型号 | guide | click_read | 京麦发品页 | 类目选择步骤 + 特殊类目提示 |
| T2.2.3 | 填写商品基本信息 | guide | click_read | 京麦发品页 | 必填字段说明 |
| T2.2.4 | 填写商品属性 | guide | click_read | 京麦发品页 | 必填/重要/其他属性说明 |
| T2.2.5 | 上传商品图片 | guide | click_read | 京麦发品页 | 主图规格/一套多套说明 |
| T2.2.6 | 填写销售属性 | guide | click_read | 京麦发品页 | 字符限制/禁止内容 |
| T2.2.7 | 填写商品描述 | guide | click_read | 京麦发品页 | 商详图规格 |
| T2.2.8 | 设置商品物流 | guide | click_read | 京麦发品页 | 48 小时发货等字段 |
| T2.2.9 | 设置商品服务 | guide | click_read | 京麦发品页 | 无理由退货必填 |
| T2.2.10 | 设置功能设置 | guide | click_read | 京麦发品页 | 个人/个体店暂不支持 |
| T2.2.11 | 使用发布助手 | guide | click_read | 京麦发品页 | 填写规则/报错反馈/建议优化 |
| T2.2.12 | 使用草稿箱功能 | guide | click_read | 京麦发品页 | 草稿上限 200 条 |
| T2.2.13 | 提交商品审核 | guide | click_read | 京麦发品页 | 提交并上架/暂不上架 |
| T2.2.14 | 修改商品 | guide | click_read | 京麦-商品列表（外链） | 修改入口与说明 |

#### T2.3 商品优化（`stage_id=optimize`，3 个）

| 任务 ID | 任务名称 | type | completion_type | action_url | 实现要点 |
|---------|---------|------|----------------|------------|---------|
| T2.3.1 | 优化商品标题 | guide | click_read | - | 标题规范/关键词优化 |
| T2.3.2 | 优化商品图片 | guide | click_read | - | 主图规范/图片质量 |
| T2.3.3 | 优化商品信息健康分 | guide | click_read | https://wares-jdm.jd.com/ware/commodity-inspection | 分数等级/6 大类因子说明 |

#### T2.4 店铺活动配置（`stage_id=activity`，6 个）

| 任务 ID | 任务名称 | type | completion_type | action_url | 实现要点 |
|---------|---------|------|----------------|------------|---------|
| T2.4.1 | 了解优惠券类型 | guide | click_read | - | 商品券/店铺券/无门槛券 |
| T2.4.2 | 了解推广方式 | guide | click_read | - | 全网自动/官方营销 |
| T2.4.3 | 配置优惠券 | guide | click_read | 京麦营销中心优惠券配置页面 | 券面额/门槛/数量/预算 |
| T2.4.4 | 了解首购礼金 | guide | click_read | - | 促销版/优惠券版 |
| T2.4.5 | 创建首购礼金 | guide | click_read | 京麦营销中心首购礼金配置页面 | 金额/门槛/预算/目标用户 |
| T2.4.6 | 了解活动运营技巧 | guide | click_read | - | 券与礼金配合/投放/分析 |

#### T2.5 店铺数据上传（`stage_id=shopdata`，6 个）

> **剥离标注（2026-08-06，依据《数据分析专区方案》v2.0）**：本组任务已从阶段二剥离至「数据分析专区」——不计入阶段二进度（33 → 27）；stage 表保留 shopdata 行（单独列项），`merchant_task_progress` 按 shopdata 单独记录、与阶段二分离统计；**独立解锁**：完成 T2.2 商品发布（listing）全部任务后解锁「店铺数据上传」独立页（`pages/data-center/upload.vue`，复用 DataForm / ExcelUpload）；入口为侧边栏底部「数据分析专区」（另一入口：数据看板，含 AI 经营分析）。下表内容仍为专区数据任务的字段 / 接口实现基准。

| 任务 ID | 任务名称 | type | completion_type | action_url | 实现要点 |
|---------|---------|------|----------------|------------|---------|
| T2.5.1 | 上传店铺星级数据 | suggested | manual_submit | https://shop.jd.com/jdm/shopstar/vane/VaneContainer | 表单：星级 1-5 + 4 因子得分（5.5-10）；POST /api/shop/star |
| T2.5.2 | 上传交易数据 | suggested | manual_submit | https://jdsz.jd.com/szweb/view/tradeAnalysis/tradeSummary.html | Excel 上传（12 指标）；POST /api/shop/trade |
| T2.5.3 | 上传流量数据 | suggested | manual_submit | https://jdsz.jd.com/szweb/view/flow/flow-summary.html | Excel 上传（57 指标）；POST /api/shop/traffic |
| T2.5.4 | 上传商品数据 | suggested | manual_submit | https://jdsz.jd.com/szweb/view/product/product360.html | Excel 上传（60 指标）；POST /api/shop/product |
| T2.5.5 | 填写商品数量 | suggested | manual_submit | https://wares-jdm.jd.com/ware/wareList | 表单 4 项数量（非负整数）；POST /api/shop/product-count |
| T2.5.6 | 上传商品信息健康分 | suggested | manual_submit | https://wares-jdm.jd.com/ware/commodity-inspection | 表单 5 项（平均分 0-100 + 各分段数量）；POST /api/shop/health-score |

> 数量核对：阶段二计入进度 4 + 14 + 3 + 6 = **27**；专区单独记录 6（T2.5.1–T2.5.6）；合计 33，与源文档逐条一致。

### 2.3 特殊功能任务说明

1. **T2.1.2 商标注册号查询**：前端需商标搜索组件（输入关键词实时联想），后端提供 `GET /api/trademark/search?keyword=`，数据源 `trademark_registry`（品牌注册号清单【8月5日】.xlsx，139 行）。完成动作 = 查询成功并展示结果（`manual_submit`）。
2. **T2.5.2–T2.5.4 Excel 上传**：前端上传组件 + 后端文件解析，采用「宽松校验」（能解析即视为上传成功），不因个别字段缺失阻塞任务完成；上传成功即 `completed`。
3. **T2.5.1 / T2.5.5 / T2.5.6 表单填写**：前端表单 + 后端 DTO 校验（星级 1-5、因子 5.5-10、数量 ≥0 整数、健康分 0-100），提交成功即 `completed`。

### 2.4 数据依赖与导入

| 依赖 | 说明 |
|------|------|
| `trademark_registry` | 139 行品牌注册号数据，UTF-8 导入（勿用 PowerShell→SQL 方式丢中文）；后台维护入口（新增/编辑/删除/批量导入） |
| 阶段二 7 张表 | 预期：`trademark_registry` + `shop_star_data` / `shop_trade_data` / `shop_traffic_data` / `shop_product_data` / `shop_product_count` / `shop_health_score`（实际表名由数据库 Agent 对现有 MySQL 核对后确认） |
| schema.sql / migration | 当前已回退不含阶段二对象，需重新补回并同步 `migrations` 数组与 `migration:run` 脚本 |
| 任务 seed | 阶段二 stage（4 条：brand/listing/optimize/activity）+ first_level_task（4 条）+ second_level_task（27 条）按 §2.2 入库；`shopdata` stage 行保留（单独列项），其 6 个二级任务单独记录，与阶段二分离统计 |

---

## 三、解锁判定方案

### 3.1 判定规则（唯一标准）

**事实源：`merchant_task_progress`（商家×任务完成记录）。阶段一完成 = 阶段一全部「启用」二级任务均为 `completed`（含 `default_completed=1`）。**

判定只依赖阶段一任务完成度，与商家经营数据、注册时长、等级、付费情况无关。

> **补充（2026-08-06，依据《数据分析专区方案》v2.0 §3.3）**：「数据分析专区」的店铺数据上传页为**独立解锁判定**（与上述阶段解锁并行，非阶段二完成前置）：解锁条件 = 阶段二「商品发布」（T2.2，listing）全部启用任务完成；由后端在进度接口返回 `data_center_unlocked`，前端据此展示锁定/解锁态。

### 3.2 判定流程（逻辑示意，非代码实现）

```
输入：merchant_id
1. 取阶段一启用任务集合 S1（stage_id ∈ onboarding/setup/application/review/opening 且 status=1）
2. 取该商家对 S1 的进度记录，过滤 status='completed' → 集合 D
3. 未完成 = S1 − D
4. 未完成为空 → 阶段一完成，解锁阶段二；否则返回未完成任务清单
```

### 3.3 解锁动作（false → true 时执行一次，幂等）

1. 更新 `merchant.current_stage = 'shop_setup'`（阶段二已解锁）。
2. 记录解锁时间：建议 `merchant` 表新增 `phase2_unlocked_at DATETIME NULL`（或复用 `event_log` 记录解锁事件，二选一，待确认）。
3. 埋点：阶段解锁事件（沿用 event_log 体系）。
4. 可选：飞书推送「恭喜完成入驻准备，开店搭建已解锁」（P2，非本期必做）。

### 3.4 触发时机

| 触发点 | 动作 |
|--------|------|
| `POST /api/task/progress` 完成阶段一任务 | 写库后立即执行解锁判定 |
| `GET /api/task/progress`（打开任务中心） | 返回时实时重算，保证一致 |
| 管理后台调整任务进度 / 任务停启用 | 调整后触发重算 |
| 阶段一新增任务 | 按 §1.3「新任务上线」规则重算 |

### 3.5 回滚规则

**默认：严格派生** —— 阶段一任一启用任务被回滚为非 `completed`（仅可能来自运营后台纠错或系统检测撤回）→ 阶段二立即重新锁定；阶段二已产生的进度记录保留不删除，阶段一重新完成后立即恢复解锁。

**备选：一次性解锁** —— 解锁后不回锁，仅提示。列为待决策项。

### 3.6 接口与数据结构影响

| 对象 | 影响 |
|------|------|
| `GET /api/task/stages` | 按商家进度过滤：阶段一未完成时不返回阶段二 stages；解锁后返回全部已解锁 stages。**建议支持可选查询参数 `?phase=1|2`** 供阶段二页面精确取数；响应中每个 stage 增加 `phase` 字段（1/2）便于前端分组 |
| `GET /api/task/progress` | 响应增加阶段级信息：`phases: [{ phase_num, title, unlocked, unfinished }]`（最小改动：新增 `stage2_unlocked` 字段） |
| `POST /api/task/progress` | 入参保持兼容；写库后执行解锁推导 |
| `merchant` 表 | 已有 `current_stage`；建议新增 `phase2_unlocked_at` |
| 管理后台 | 商家详情展示两阶段完成度与解锁状态；提供「标记阶段一完成并解锁」运营动作（存量商家初始化） |
| H5 前端 | 阶段一未完成时不展示阶段二入口；直接访问阶段二页面时接口不返回数据 → 展示「未解锁」态（防绕过） |

---

## 四、与阶段一的对齐清单（结构 / 组件 / 数据流 / 验收）

阶段一基准：`project/src/pages/index/index.vue` + `store/modules/task.ts` + `components/` + `styles/tokens/`。

### 4.1 页面结构对齐

| 结构项 | 阶段一基准 | 阶段二要求 |
|--------|-----------|-----------|
| 整体布局 | flex 左右布局：`sidebar`（20%，fixed）+ `main-content`（margin-left 20%） | 完全一致 |
| 侧边栏-顶部 | Logo（图标+「商家任务中心」） | 一致 |
| 侧边栏-进度 | 总进度：进度条 + completed/total | 一致，进度口径为阶段二 27 任务（shopdata 不计入） |
| 侧边栏-导航 | 编号圆点 + 阶段标题，激活态高亮 | 4 项：T2.1–T2.4；底部新增「数据分析专区」分区（店铺数据上传 / 数据看板 2 入口） |
| 侧边栏-底部 | 用户头像 + 用户名 | 一致 |
| 内容区 | StageHeader + 一级任务分组 + TaskCard 列表 | 一致（4 个分组：T2.1–T2.4；T2.5 分组不渲染，迁至专区） |
| 弹窗 | 通用 Modal（保证金/二维码/驳回） | 沿用 Modal；新增业务弹窗（上传结果/表单） |

### 4.2 组件对齐

| 组件 | 阶段一 | 阶段二 | 说明 |
|------|--------|--------|------|
| TaskCard | ✅ | ✅ 复用 | 任务卡片，含完成态/展开 |
| StageHeader | ✅ | ✅ 复用 | 阶段标题 + 完成按钮 |
| Checkbox | ✅ | ⚠️ 按需 | 阶段二无勾选场景可不用，表单校验如需则复用 |
| ProgressBar | ✅ | ✅ 复用 | 侧边栏进度条 |
| Modal | ✅ | ✅ 复用 | 通用弹窗 |
| BranchTask | ✅ | ❌ 不适用 | 阶段二无支线任务 |
| 新增组件 | - | ✅ `components-local/stage2/` | TrademarkSearch（商标搜索）、ExcelUpload（上传）、DataForm（表单） |

### 4.3 样式与 Token

- 配色、字号、间距、圆角一律取自 `$u-*` / `$up-*` Token，禁止硬编码颜色。
- 侧边栏宽度 20%、内边距、导航项高度、激活态样式与阶段一逐项一致。
- 遗留问题（不属本任务，不得复制）：阶段一 `index.vue` 弹窗区存在少量硬编码色值（如 `#E2E8F0`、`#1F2937`），阶段二新建代码一律走 Token，后续可统一收编。

### 4.4 数据流对齐

| 环节 | 阶段一模式 | 阶段二要求 |
|------|-----------|-----------|
| 页面加载 | onMounted → trackPageView → fetchStages → restoreProgress | 同模式 |
| 任务数据 | GET /api/task/stages（后端过滤） | 同接口 + `?phase=2` 或后端按解锁返回 |
| 完成操作 | toggleTask → saveProgress | 同模式 |
| 进度同步 | POST /api/task/progress（异步，不阻塞 UI） | 同接口 |
| 本地缓存 | localStorage `task_progress_cache` | localStorage `stage2_progress_cache`（key 隔离，防两阶段串数据） |
| 进度恢复 | GET /api/task/progress → completedTasks → 标记；localStorage 兜底 | 同模式 |
| Store | `store/modules/task.ts`（Pinia setup 风格） | 新建 `store/modules/stage2.ts`，结构完全对齐（fetchStages / restoreProgress / progress / toggleTask / completeStage） |
| API 封装 | `src/api/request.ts`（Token 注入、统一响应） | 复用；新增 `src/api/stage2.ts`（商标搜索、上传、表单） |
| 类型 | `types/task.ts`（StageInfo/FirstLevelTask/SecondLevelTask） | 复用；`TaskStage` 联合类型扩展 brand/listing/optimize/activity/shopdata（shopdata 供数据分析专区取数，不参与阶段二进度） |
| 路由 | `pages.json` 注册 | 注册 `pages/stage2/index`（navigationStyle custom，与 index 一致；不入 tabBar） |
| 埋点 | trackPageView('task-center') / trackTaskComplete | trackPageView('stage2-center')，事件类型沿用 |

### 4.5 入口与解锁联动

1. 阶段一页面在**全部任务完成后**出现「阶段二：开店搭建」入口（入口位置由前端 Agent 阶段一任务 #F1-001 出方案：侧边栏底部或主内容区按钮，待总控确认）。
2. 入口跳转 `uni.navigateTo` 到独立页面 `pages/stage2/index`，不混入阶段一页面。
3. 未解锁时入口隐藏/置灰；直接访问阶段二页面时，后端接口不返回阶段二数据 → 前端展示「未解锁」态，防止绕过。

### 4.6 验收：必须与阶段一一致项

| 验收项 | 标准 | 级别 |
|--------|------|------|
| 视觉一致 | 侧边栏宽度 20%、内边距、字号、激活态、配色与阶段一截图对比一致 | P0 |
| Token 合规 | 新建样式无硬编码颜色，全部取自 `$u-*` / `$up-*` | P0 |
| 组件复用 | 不引入第二个组件库；TaskCard/StageHeader/ProgressBar/Modal 复用清单核对通过 | P0 |
| 数据流一致 | 展示 → 完成 → POST 同步 → localStorage 缓存 → 刷新恢复，行为与阶段一一致 | P0 |
| 任务展示 | T2.1–T2.4 共 27 个计入进度任务按 md 顺序与内容展示（4/14/3/6）；T2.5 不在阶段二页面渲染 | P0 |
| 阶段隔离 | 阶段一未完成：无入口且接口不返回阶段二；完成后：入口开启、27 个进度任务齐全 | P0 |
| 功能 | 商标搜索（模糊）、Excel 上传、表单校验、进度同步可用 | P1 |
| 数据分析专区 | 侧边栏底部展示「数据分析专区」2 入口；数据上传页按 T2.2 全部完成独立解锁（`data_center_unlocked`）；看板 + AI 经营分析可用；旧路由 `pages/stage2/data-board` 兼容跳转 | P1 |
| 性能 | 阶段二页面加载与阶段一同量级（≤2s） | P1 |

---

## 五、规划风险与建议

1. **`setup` 命名冲突**：阶段一已有 `setup` stage，阶段二不得复用；已由 §1.2 统一为 `shop_setup` + `brand/listing/optimize/activity/shopdata`，需同步到后端/前端/测试任务单。
2. **数据上传门槛高（剥离至专区后仍适用）**：129 项指标依赖京东商智导出，商家操作成本高。建议运营提供截图教程与样例文件；上传解析按宽松校验实现；专区数据任务类型为 `suggested`（该约束随剥离移至数据分析专区，不影响阶段二完成判定）。
3. **商标数据依赖**：139 行品牌注册号数据与后台维护入口是 T2.1.2 上线前置条件，需在排期前排入数据库/后端任务。
4. **任务体量**：阶段二计入进度 27 个，建议按 T2.1+T2.2 → T2.3 → T2.4 分批排期上线（仅影响发布节奏，不改变隔离规则）；T2.5 数据上传随「数据分析专区」独立排期（独立解锁，不阻塞阶段二完成）。
5. **阶段一编号偏移（既有问题，已闭环）**：`02-规划说明.md` 中 T1.4/T1.5 的二级任务编号曾写作 T1.5.x/T1.6.x（**历史事实，保留登记不删**）。**处置**：T1.4 节的 `T1.5.1` / `T1.5.2` / `T1.5.1-B1` 已于 **#PL-12**（2026-09-16）按数据库规范号更正为 **`T1.4.1` / `T1.4.2` / `T1.4.1-B1`**（依据 `second_level_task.taskId`：组 `T1.4`、阶段 `review`；数据库为运行时真源）；T1.5 节的 `T1.6.x` 已于 **#PL-11**（2026-09-16，随 `#DB-22` 阶段一序号调整）改为 `T1.5.1` 联系人信息及地址维护 / `T1.5.2` 开通京东钱包结算账户 / `T1.5.3` 缴费。本基准阶段二编号仍以 `阶段二任务体系.md` 为准。

---

## 六、待决策项

| 编号 | 决策项 | 建议 |
|------|--------|------|
| 1 | `merchant` 表新增 `phase2_unlocked_at` vs 复用 event_log 记录解锁 | 新增字段（查询简单），或 event_log（零表结构变更） |
| 2 | 阶段二任务 `type` 口径：全部 guide vs 数据上传任务用 suggested | 专区数据上传任务（T2.5）用 suggested，其余 guide |
| 3 | 解锁回滚：严格派生 vs 一次性解锁 | 严格派生 |
| 4 | 存量商家初始化：运营一键解锁 vs 系统自动判定 | 运营一键解锁 |
| 5 | 阶段二入口位置：侧边栏底部 vs 主内容区按钮 | 交前端 #F1-001 方案，建议侧边栏底部 |
| 6 | 阶段二解锁飞书推送 | P2 做，非 P0 |

---

> 本文件为 R2 规划基线；待决策项确认后，可合并进 `project/02-规划说明.md`，并将任务清单引用到 `01-立项文档.md` 的 V1 功能范围。
