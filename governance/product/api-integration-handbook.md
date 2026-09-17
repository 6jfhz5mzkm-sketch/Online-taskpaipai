# 前后端对接方案（当前对接手册 · 派生视图）

> 版本：v2.0（2026-09-15 重写，整体替换 v1.0「阶段一历史快照」）
> **定位（硬口径）**：本文件是**派生视图（derived view）**，只用于三端对接时快速查阅。
> 接口 / 字段 / 错误码 / 业务规则的**唯一真源 = `project/docs/后端技术方案.md`**；表结构真源 = `project/scripts/schema.sql`。
> **两者不一致时，一律以后端技术方案为准，并回头修本文件**——本文件不得反向覆盖真源，也不得作为新契约的登记处。
> 生成依据：`api-py/app/api/v1/**` **实际路由** + `app.openapi()` 输出快照（2026-09-16：OpenAPI 路径 **65** 条、端点 **78** 个 = 本文件登记的 77 个业务端点 + `GET /health`）。
> 覆盖范围：**三端全覆盖**——商家端 H5（阶段一 / 阶段二 / 数据看板）、管理后台。旧 v1.0 只覆盖阶段一，且基于已作废的 NestJS + `localhost:3000`，其正文与「漂移校正速查」不再保留（历史见 git 历史）。

---

## 一、怎么用这份文件

| 你要查什么 | 去哪里 |
|-----------|--------|
| 有哪些接口、谁要鉴权、入参出参长相、主要错误码 | **本文件** §二 / §三 / §四 / §五 |
| 字段级口径、业务规则、**错误文案原文**、变更记录 | 真源 `project/docs/后端技术方案.md` §4 / §5.2 / §6 / §9.7 |
| 表结构与列类型 | `project/scripts/schema.sql`（结构校验 `uv run python scripts/check_schema.py`） |
| 发现本文件与真源不一致 | **以真源为准**；同时按 §七 回写本文件 |

## 二、运行面与通用约定

### 2.1 基址与入口

| 项 | 值 |
|----|----|
| 后端运行面 | api-py（Python 3.12 + FastAPI），本地 `http://127.0.0.1:8000` |
| 商家端 H5 基址 | `export const BASE_URL = import.meta.env.VITE_API_BASE_URL || ''`（`project/src/api/request.ts:19`）；本地由 `project/.env.development` 注入 `http://localhost:8000` |
| 管理后台基址 | admin 端 vite proxy → `http://localhost:8000`（本地）；生产走域名 |
| 健康检查 | `GET /health`（**不在 `/api` 前缀下**，无鉴权） |
| 接口文档 | `GET /docs`，仅 `DEBUG=true` 可访问（生产 404） |
| 静态资源 | `GET /api/static/advisor-qr.jpg`（单文件，无需登录，返回图片二进制） |

### 2.2 统一响应信封

所有 JSON 接口统一 `{ code, message, data }`：成功 `code = 0`、`message = "success"`；失败 `data = null`，`message` 为用户可读中文（文案真源见后端技术方案 §4.3.1 与各接口节）。**HTTP 状态码与 `code` 一般同值**（校验失败固定 400；管理员登录限流/锁定 429；第三方失败 502）。前端判成功请用 `code === 0`。

| code | 含义 | 典型来源 |
|------|------|---------|
| 0 | 成功 | 全部 |
| 400 | 参数/业务校验失败 | Pydantic 校验、文件与业务规则（Excel 表头/跨度、关键词为空等） |
| 401 | 未登录 / Token 无效或过期 / 管理员不存在或已禁用 | `app/api/deps.py` |
| 403 | 无权限：角色不足 / 阶段二未解锁 / 数据专区未解锁 | `require_roles`、`_assert_phase2` |
| 404 | 目标不存在（类目、资费、阶段/任务、反馈、商家等） | 各服务层 |
| 405 | 请求方法不允许 | 框架统一出口 |
| 429 | 限流 / 登录失败锁定 / AI 额度用完或繁忙 | `app/services/auth.py`、`app/services/ai.py` |
| 500 | 服务器内部错误（堆栈只进日志） | 未知异常出口 |
| 502 | 第三方服务失败（飞书 / AI 上游） | `app/services/feishu.py`、`ai.py` |

### 2.3 鉴权三档（服务端边界，`app/api/deps.py`）

| 档位 | 头部 | 说明 | 失败 |
|------|------|------|------|
| 公开 | 无 | 登录、埋点上报、静态资源、健康检查 | — |
| 商家 JWT | `Authorization: Bearer <merchant token>` | `get_current_merchant`（只验 JWT；`merchant_id` 一律取自 token，禁止客户端传入） | 401「未登录或 Token 已过期」/「Token 无效」 |
| 管理端 JWT | `Authorization: Bearer <admin token>` | `get_current_admin`（查库并校验 `status=1`）；角色不足由 `require_roles(...)` 拦 | 401「未登录或 Token 已过期」/「管理员不存在或已禁用」；403「无权限执行该操作」 |

- Token 有效期 7 天；过期后请求返回 401，前端应清 token 并回登录页。
- **角色**：`super_admin`（含全部写权限与账号/AI 配置管理）、`admin`（任务配置写 + 反馈处理）、`viewer`（只读平台数据）。
- **阶段隔离**：阶段二接口在未解锁时返回 403「阶段二未解锁」；数据专区相关返回 403「数据专区未解锁」（判定真源见后端技术方案 §5.2 扩展与 §6）。

### 2.4 通用上界（禁止无界响应）

| 场景 | 上界 | 越界表现 |
|------|------|---------|
| `page_size` | 100（超出按 100 计） | 不报错，静默收敛 |
| `GET /api/admin/merchant/progress`（不传 merchantId） | 5000 行 | 400「结果过多，请按商家查询」 |
| Excel 上传 | ≤10MB、数据行 ≤5000、sheet ≤10 | 400（文案见 §三 4.1） |
| 图片上传（主图优化） | ≤5MB，jpg/png/webp | 400 |
| 埋点统计 | 查询范围 ≤90 天 | 400「查询范围不能超过90天」 |
| AI 调用 | 进程内并发/频率 + 每日额度 | 429 |

### 2.5 字段命名风格（务必按表照抄，别猜）

历史原因本仓库**不统一**：`merchant` / `fee` / `tour` / `feedback`（管理端列表）等偏 snake_case（`merchant_id`、`category_id`、`page_size`）；`admin` 任务配置族、`shop` 表单与 AI 族偏 camelCase（`totalCount`、`dataDate`、`spuTitle`、`realName`）。**以 §三「关键入参 / 响应」列写明的实际形态为准**。

---

## 三、接口总表（78 端点）

> 「鉴权」列：`公开` / `商家`（商家 JWT）/ `管理`（管理端 JWT）/ `admin+`（`require_roles("super_admin", "admin")`）/ `super`（仅 `super_admin`）。
> 「响应」列给出信封内 `data` 的形状；错误码列只列**该端点特有或高频**的错误，通用 400 校验失败文案见 §五。

### 3.1 认证与系统（10）

| 方法 | 路径 | 鉴权 | 关键入参 | 响应（`data`） | 主要错误码 |
|------|------|------|---------|---------------|-----------|
| POST | `/api/admin/auth/login` | 公开 | body `AdminLoginBody{username, password}` | `{token, admin{...}}` | 400 校验；401「用户名或密码错误」；429 限流/锁定 |
| GET | `/api/admin/auth/profile` | 管理 | — | `{id, username, realName, role}` | 401 |
| POST | `/api/admin/auth/change-password` | 管理 | body `ChangePasswordBody{oldPassword, newPassword}` | `{success:true}`（201） | 401「旧密码错误」；400 校验 |
| POST | `/api/auth/feishu/callback` | 公开 | body `FeishuCallbackBody{code}` | `{token, merchant{merchant_id, nickname, avatar, merchant_name, current_stage, status}}` | 400「授权码不能为空」；401 飞书错误码映射（`20003` →「登录链接已失效，请重新点击飞书登录」）；502 网络异常 / **后端凭证不合规 →「登录服务暂不可用，请稍后重试或联系管理员」（白话，可直接展示）** |
| POST | `/api/auth/phone/send-code` | 公开 | body `SendLoginCodeBody{phone, captcha_verify_param?}`（`captcha_verify_param` = 前端图形认证 `getValidate()` 的 **4 字段 JSON**：`lot_number`/`captcha_output`/`pass_token`/`gen_time`；其中的 `captcha_id` 由**服务端配置**决定、传了也会被忽略） | `{sent:true, cooldown_seconds, expires_in_seconds, code_length}`（**不含账号存在性信息**） | 400「手机号格式不正确」/「请先完成安全验证」；429 冷却与频控（带 N 秒或统一句）；502「短信服务暂不可用，请稍后重试」；503「当前发送量已达上限，请稍后再试」/ **「登录服务暂不可用，请稍后重试或联系管理员」（图形认证凭证未配置 = 服务侧故障）** |
| POST | `/api/auth/phone/login` | 公开 | body `PhoneLoginBody{phone, code}` | `{token, merchant{merchant_id, nickname, avatar, merchant_name, current_stage, status}, is_new_merchant}`（**201**） | 400「验证码不正确或已过期」；403「账号已被禁用，请联系平台」；429「验证尝试次数过多，请重新获取验证码」；502 短信服务不可用 |
| POST | `/api/event/track` | 公开（带 token 时顺带提取 merchant_id；无效 token 静默忽略） | body `TrackBody{event_type, page_name?, task_key?, stage_key?, element?, meta?}` | `{received:true}`（201） | 400 校验 |
| GET | `/api/event/stats` | 管理 | query `start_date`、`end_date`（均必填，YYYY-MM-DD）、`event_type?`、`group_by=day\|week` | `{date_range, summary, trend, page_distribution, task_stats}` | 400「日期格式不合法」/「查询范围不能超过90天」；401 |
| GET | `/health` | 公开 | — | `{status:"ok"}` | — |
| GET | `/api/static/advisor-qr.jpg` | 公开 | — | JPEG 二进制（**非 JSON 信封**） | 404「顾问二维码未配置」；500 配置越界 |

### 3.2 商家端基础能力（10）

| 方法 | 路径 | 鉴权 | 关键入参 | 响应（`data`） | 主要错误码 |
|------|------|------|---------|---------------|-----------|
| GET | `/api/merchant/info` | 商家 | — | `{merchant_id, nickname, avatar, merchant_name, current_stage, status}` | 401；404「商家不存在」 |
| GET | `/api/category/list` | 商家 | query `parent_id?`（不传=一级） | `[{id, name, parent_id, sort_order}]`（id 为字符串） | 401 |
| GET | `/api/category/{id}` | 商家 | path `id` | `{id, name, parent_id, sort_order}` | 401；404「类目不存在」 |
| GET | `/api/category/requirement/{categoryId}` | 商家 | path `categoryId`（正整数） | `{id, categoryId, shopType, shopNameRule, requirements, reviewFocus, contactEmail, isActive, createdAt, updatedAt, deletedAt, category}`；无记录 `null` | 401；400 校验 |
| GET | `/api/fee/detail` | 商家 | query `category_id`（必填）、`brand_name?` | `{category_id, brand_name, operation_rate, transaction_rate, deposit_gmv_lt_5w, deposit_gmv_5w_10w, deposit_gmv_10w_30w, deposit_gmv_gte_30w, is_brand_override}` | 401；404「该类目暂无资费信息」 |
| GET | `/api/trademark/search` | 商家 + 阶段二 | query `keyword` | `[{brand_name, registration_number}]`（≤50 条） | 401；403「阶段二未解锁」；400「关键词不能为空」 |
| GET | `/api/merchant/category` | 商家 | — | `{success:true, categories:[...]}` | 401 |
| POST | `/api/merchant/category` | 商家 | body `CategoriesBody{categories:[{category_id, is_primary}]}`（1–3 个，`is_primary` 唯一） | `{success:true, count}`（201） | 400「类目不存在」/「请选择1-3个类目」/「只能选择一个主营类目」；401 |
| GET | `/api/merchant/registration` | 商家 | — | `{jd_merchant_id, shop_name}`（未登记为 `null`） | 401 |
| PUT | `/api/merchant/registration` | 商家 | body `RegistrationBody{jd_merchant_id?, shop_name?}`（**缺省=不更新**；`null`/空串=清空） | `{success:true}` | 400「京麦商家ID仅支持数字」/「店铺名称仅支持汉字」/超长走通用句；401 |

### 3.3 任务体系与新手引导（6）

| 方法 | 路径 | 鉴权 | 关键入参 | 响应（`data`） | 主要错误码 |
|------|------|------|---------|---------------|-----------|
| GET | `/api/task/progress` | 商家 | — | `{completedTasks, stage2_unlocked, data_center_unlocked, phase1_remaining_task_ids}` | 401 |
| POST | `/api/task/progress` | 商家 | body `UpdateProgressBody{taskId, status}` | `{success, stage2_unlocked, data_center_unlocked}`（201） | 400「任务不存在」/「任务已停用，不可提交进度」/「该任务默认已完成，不可置为未完成」；403「阶段二未解锁」/「数据专区未解锁」；401 |
| GET | `/api/task/stages` | 商家 | — | 阶段+任务树（阶段二未解锁时该阶段返回锁定壳 `locked:true, firstLevelTasks:[]`；解锁后 4/14/3/6/6 共 33 个任务）；**二级任务含 `actionType`/`actionParam`（#PB-39，位置在 `actionUrl` 之后）** | 401 |
| GET | `/api/tour/seen` | 商家 | — | `{seen:bool}` | 401 |
| POST | `/api/tour/seen` | 商家 | — | `{success:true}` | 401 |
| POST | `/api/tour/seen/reset` | 商家 | — | `{success:true}` | 401 |

### 3.4 店铺数据上传与看板（7）

| 方法 | 路径 | 鉴权 | 关键入参 | 响应（`data`） | 主要错误码 |
|------|------|------|---------|---------------|-----------|
| POST | `/api/shop/star` | 商家 + 阶段二 | body `StarBody{shopStar(1–5), serviceScore?, logisticsScore?, afterSaleScore?, productScore?, dataDate}` | `{success:true}`（201） | 400 日期专句/整数越界通用句；403「阶段二未解锁」；401 |
| POST | `/api/shop/product-count` | 商家 + 阶段二 | body `ProductCountBody{totalCount, onSaleCount?, offSaleCount?, auditCount?, dataDate}`（整数 0–4294967295） | `{success:true}`（201） | 同上 |
| POST | `/api/shop/health-score` | 商家 + 阶段二 | body `HealthScoreBody{avgScore(0–100), scoreGte90Count?, score78_90Count?, score60_77Count?, scoreLt60Count?, dataDate}` | `{success:true}`（201） | 同上 |
| POST | `/api/shop/trade` | 商家 + 阶段二 | multipart `file`（≤10MB、`.xlsx`）；**不传 `timeRange`** | `{success, count, total_rows, skipped, normalized, issues[], issues_truncated}`；**有写入 201 / 全部行皆坏 200** | 400 表头无法识别 / 跨度不支持 / 文件过大 / 解析失败 / sheet>10 / 行数>5000；403；401 |
| POST | `/api/shop/traffic` | 商家 + 阶段二 | 同 `trade` | 同 `trade` | 同 `trade` |
| POST | `/api/shop/product` | 商家 + 阶段二 | 同 `trade` | 同 `trade` | 同 `trade` |
| GET | `/api/shop/summary` | 商家 + 阶段二 | query `time_range?`（**可选，默认 `7d`**；取值 `yesterday`/`7d`/`30d`） | `{time_range, star, trade, traffic, product, product_count, health_score}`（无数据为 `null`） | 400 非法 `time_range`（中文专句）；403「阶段二未解锁」；401 |

> ✅ **`time_range` 校验（#PB-30 已修）**：`summary` 为**可选 + 默认 `7d`**、非法值 → **400**；非法入参在**路由边界先于阶段二门禁**判定，所以未解锁商家传错值时拿到的是 400 而不是 403。文案为中文专句（`app/services/shop.py::TIME_RANGE_INVALID_MESSAGE`），**不回显英文枚举原文**；真源 §5.2 API-14 已同步为同一口径。
> ⚠️ **`time_range` 从哪来（Excel 场景）**：**不在前端传**——后端按上传文件的日期跨度推导（1 天→`yesterday`、2–10 天→`7d`、11–31 天→`30d`，其它跨度 400）。因此「当日导出」不再被混进 `7d` 桶。字段级口径见真源 API-13.3。
> ⚠️ **逐行问题清单怎么展示**：`count` 写入行数 / `total_rows` 处理行数 / `skipped` 跳过行数 / `normalized` 归一后仍写入的行数；`issues[]` 每条含 `row`（**Excel 物理行号，表头=1**）/`field`/`value`/`reason`/`action`（`skipped`\|`normalized`）/`message`，**最多 200 条**，被截断时 `issues_truncated=true` 而四个计数仍为全量。前端建议文案：「成功导入 N 行，跳过 M 行」，并允许展开清单。

### 3.5 店铺 AI 与数据清理（4）

| 方法 | 路径 | 鉴权 | 关键入参 | 响应（`data`） | 主要错误码 |
|------|------|------|---------|---------------|-----------|
| POST | `/api/shop/analysis` | 商家（内部经看板聚合 → 受阶段二门禁） | query `time_range`（**必填**，`yesterday`/`7d`/`30d`） | `{summary, strengths[], weaknesses[], suggestions[]}`；无数据时 `{summary:null, ..., message:"暂无已上传的经营数据，请先完成数据上传"}` | 400 非法/缺失 `time_range`（与 `summary` **同一句**中文专句）；403「阶段二未解锁」；429 频繁/额度用完/上游限流；**504 超时**；502 上游失败/结果异常；401 |
| POST | `/api/shop/image-optimize` | 商家 | multipart `file`（≤5MB、jpg/png/webp） | `{summary, compliance, issues, plan}` | 400「请上传图片文件」/「仅支持 JPG/PNG/WebP 格式图片」/「图片过大，请上传 5MB 以内的图片」；429；502；401 |
| POST | `/api/shop/title-optimize` | 商家 | body `TitleOptBody{mode, category, brand?, model?, features?, condition?, keyAttrs?, saleAttrs?, currentTitle?}` | `{spuTitle, skuTitle, notes}` | 400「请至少填写品牌、型号、产品特点、成色、关键属性或销售属性中的一项」/「请提供现有标题」；429；502；401 |
| POST | `/api/shop/clear-data` | 商家（**无阶段二门禁**） | — | `{success, cleared, reset_tasks}`（201） | 401 |

> ✅ **文案已中文化（#PB-30 已修）**：`/api/shop/analysis` 的 400 文案原为英文 NestJS 遗留，现与 `summary` 共用同一中文专句「时间范围不支持，请使用 昨天 / 近7天 / 近30天」（单一真源 `app/services/shop.py::TIME_RANGE_INVALID_MESSAGE`），行为不变（仍必填 + 枚举）。前端可直接展示 `message`，无需再兜底翻译。
> ✅ **AI 回答中的指标名已中文化（#PB-32 · #PB-33）**：送模型的汇总数据键改为中文指标名（如「商品信息健康分」「成交金额」），系统提示同时**禁止英文字段名与下划线命名**；`POST /api/shop/title-optimize` 同口径——入参键改为中文（品牌/型号/成色/关键属性/销售属性/现有标题…），系统提示禁止 camelCase 字段名。**响应结构、错误码、文案均不变**。名册（经营分析 50 键 + 标题优化 9 键）与用词对齐规则见真源 §10.6；与前端 `SHOP_METRIC_LABELS`/`SHOP_SUMMARY_TYPES` 现存 0 处用词差异。

### 3.6 反馈与飞书推送（4）

| 方法 | 路径 | 鉴权 | 关键入参 | 响应（`data`） | 主要错误码 |
|------|------|------|---------|---------------|-----------|
| POST | `/api/feedback` | 商家 | body `CreateFeedbackBody{content(1–1000), category?}` | `{received:true}`（201） | 400 校验；401 |
| GET | `/api/feishu/advisor-qr` | 商家 | — | 顾问二维码信息（服务层返回，字段以真源为准） | 401 |
| POST | `/api/feishu/notify/welcome` | 商家 | — | `{sent, first}` | 400「商家未绑定飞书」；502 飞书凭证/网络异常；401 |
| POST | `/api/feishu/notify/stage-complete` | 商家 | body `StageBody{stage_name, next_stage_name}` | `{success, notification_id, skipped, reason}` | 400「商家不存在」/「商家未绑定飞书」/「template_type 不在枚举范围」；502；401 |

### 3.7 管理后台：商家与进度（7）

| 方法 | 路径 | 鉴权 | 关键入参 | 响应（`data`） | 主要错误码 |
|------|------|------|---------|---------------|-----------|
| GET | `/api/admin/merchant` | 管理 | query `keyword?`（**4 字段 OR 模糊匹配**：`merchant_id`/`nickname`/`jd_merchant_id`/`shop_name`）、`stage?`（**已登记取值** `onboarding`/`shop_setup`，空=不筛选）、`status?`（**已登记取值** `0`/`1`/`2`，空=不筛选）、`page?`（默认 1）、`page_size?`（默认 20，上界 100） | `{list:[{merchant_id, nickname, merchant_name, current_stage, status, jd_merchant_id, shop_name, last_login_at, created_at}], total, page, page_size}`（**9 字段投影**，`status` 由 #PB-25 补齐） | 400 未登记筛选取值；401 |
| GET | `/api/admin/merchant/progress` | 管理 | query `merchantId?`（**不传=全部商家**） | `[{id, merchantId, taskId, status, completedAt, createdAt, updatedAt}]`（`merchantId, taskId` 升序） | 400「结果过多，请按商家查询」（>5000 行）；401 |
| GET | `/api/admin/merchant/progress/{merchantId}` | 管理 | path `merchantId` | 同上（`createdAt` 降序，row 集与「全部」一致） | 401 |
| POST | `/api/admin/merchant/{id}/unlock-phase1` | admin+ | path `id`（= merchantId） | `{success:true, stage2_unlocked:true}`（201，幂等永久） | 403；404「该商家不存在」；401 |
| GET | `/api/admin/merchant/{merchantId}/bindings` | 管理 | path `merchantId` | `{jd_merchant_id, group_id, members:[{merchant_id, nickname, status, current_stage, bound_at, bound_by, is_self}]}`（**未绑定 → `group_id:null` 且仅含自身**；**不返回手机号**） | 404「商家不存在」；401 |
| POST | `/api/admin/merchant/{merchantId}/bindings` | admin+ | path `merchantId`；body `BindMemberBody{member_merchant_id}` | `{success:true, group_id, members:[…]}`（**201**，信封 `message` = 「绑定成功」中文专句；**幂等**：目标已在同组 → 返回现状、不重复写行） | 400「该商家尚未登记京麦商家ID，无法绑定」/「该账号已绑定到其它商家」/「不能绑定自身」/「该京麦商家ID已有绑定组，请刷新后重试」（并发冲突）；404「商家不存在」；403；401 |
| DELETE | `/api/admin/merchant/{merchantId}/bindings/{memberMerchantId}` | admin+ | path 两参数（**不暴露内部 binding id**） | `{success:true}`（200，信封 `message` = 「已解绑」；活跃成员 < 2 时**同事务关闭组并退役剩余成员的活跃行**——店内只有 2 个账号时解绑任一 ⇒ **绑定整体解除**，另一账号也不再共享进度；**进度行不删不清零**，各自回落） | 404「绑定关系不存在」/「商家不存在」；403；401 |

### 3.8 管理后台：任务配置（阶段 / 一级任务 / 二级任务，15）

| 方法 | 路径 | 鉴权 | 关键入参 | 响应（`data`） | 主要错误码 |
|------|------|------|---------|---------------|-----------|
| POST | `/api/admin/stage/create` | admin+ | body `StageCreateBody{stageId, stageNum, title, description, buttonText, sortOrder, phaseNum}` | 阶段行（201） | 400「阶段标识 … 已存在」/「… 字段 … 不能为 null」；403；401 |
| GET | `/api/admin/stage/list` | 管理 | — | `[{id, stageId, stageNum, title, description, buttonText, status, sortOrder, phaseNum, createdAt, updatedAt}]` | 401 |
| GET | `/api/admin/stage/{id}` | 管理 | path `id` | 阶段行 | 404「阶段 {id} 不存在」；401 |
| PUT | `/api/admin/stage/{id}` | admin+ | body `StageUpdateBody{...}`（同 create） | 阶段行 | 404；400；403；401 |
| DELETE | `/api/admin/stage/{id}` | admin+ | path `id` | `{success:true}` | 404；403；401 |
| POST | `/api/admin/group/create` | admin+ | body `GroupCreateBody{taskId, stageId, title, description, buttonText, sortOrder}` | 一级任务行（201） | 400「一级任务标识 … 已存在」；403；401 |
| GET | `/api/admin/group/list` | 管理 | query `stageId?` | `[{id, taskId, stageId, title, description, buttonText, status, sortOrder, createdAt, updatedAt}]` | 401 |
| GET | `/api/admin/group/{id}` | 管理 | path `id` | 一级任务行 | 404「一级任务 {id} 不存在」；401 |
| PUT | `/api/admin/group/{id}` | admin+ | body `GroupUpdateBody{...}`（同 create） | 一级任务行 | 404；400；403；401 |
| DELETE | `/api/admin/group/{id}` | admin+ | path `id` | `{success:true}` | 404；403；401 |
| POST | `/api/admin/task/create` | admin+ | body `TaskCreateBody{taskId, firstLevelTaskId, stageId, title, description, detail, type, completionType, actionText, actionUrl, actionType, actionParam, tag, defaultCompleted, sortOrder}`（`type` 6 值 / `completionType` 5 值，**均与库内现实取值一致**（#PB-40，真源 §8.3.10）；`actionType` 10 值枚举、省略 = `none`；`actionParam` 仅 `data_*` 可用且**必填**） | 二级任务行（201，含 `actionType`/`actionParam`） | 400「二级任务标识 … 已存在」/ 非法枚举 / 参数规则违反（**统一文案**「提交的内容有误，请检查后重试」）；403；401 |
| GET | `/api/admin/task/list` | 管理 | query `firstLevelTaskId?`、`stageId?` | `[{id, taskId, firstLevelTaskId, stageId, title, description, detail, type, completionType, actionText, actionUrl, actionType, actionParam, tag, defaultCompleted, status, sortOrder, createdAt, updatedAt}]` | 401 |
| GET | `/api/admin/task/{id}` | 管理 | path `id` | 二级任务行 | 404「二级任务 {id} 不存在」；401 |
| PUT | `/api/admin/task/{id}` | admin+ | body `TaskUpdateBody{...}`（同 create，两字段省略 = 不改；切回非 `data_*` 时**必须显式 `actionParam: null`**） | 二级任务行 | 404；400（非法枚举 / 参数规则违反，统一文案）；403；401 |
| DELETE | `/api/admin/task/{id}` | admin+ | path `id` | `{success:true}` | 404；403；401 |

> 说明：以上写接口由 api-py 提供、管理后台 `admin/src/api/*.ts` 已封装；其中 `stage` 写接口**当前无页面调用**（阶段管理页不可达），按用户裁决**只登记不删**（真源 §5.2 API-19）。

### 3.9 管理后台：管理员账号（7）

| 方法 | 路径 | 鉴权 | 关键入参 | 响应（`data`） | 主要错误码 |
|------|------|------|---------|---------------|-----------|
| GET | `/api/admin/account/list` | 管理 | — | `[{id, username, realName, phone, email, role, status, lastLoginAt, createdAt}]` | 401 |
| GET | `/api/admin/account/{id}` | 管理 | path `id` | 管理员行 | 404「管理员 {id} 不存在」；401 |
| POST | `/api/admin/account/create` | super | body `CreateAdminBody{username, password, realName, phone, email, role}` | `{id, username, realName, role}`（201） | 400「用户名 … 已存在」/「字段 … 不能为 null」；403；401 |
| POST | `/api/admin/account/generate` | super | body `GenerateAdminBody{username, realName, phone, email, role}` | `{id, username, realName, role, password, note}`（201，**口令仅此一次返回**） | 400 同上；403；401 |
| PUT | `/api/admin/account/{id}` | super | body `UpdateAdminBody{realName, phone, email, role, status}` | 管理员行 | 404；400；403；401 |
| DELETE | `/api/admin/account/{id}` | super | path `id` | `{success:true}` | 404；403；401 |
| POST | `/api/admin/account/{id}/reset-password` | super | body `ResetPasswordBody{password}` | `{success:true}`（201） | 404；400；403；401 |

### 3.10 管理后台：反馈与 AI 配置（5）

| 方法 | 路径 | 鉴权 | 关键入参 | 响应（`data`） | 主要错误码 |
|------|------|------|---------|---------------|-----------|
| GET | `/api/admin/feedback` | admin+ | query `status?`、`category?`、`start_date?`、`end_date?`、`page?`、`page_size?` | `{list:[{id, merchantId, content, category, status, adminReply, handlerId, createdAt, updatedAt}], total, page, page_size}` | 401；403 |
| PATCH | `/api/admin/feedback/{id}` | admin+ | path `id`；body `UpdateFeedbackBody{status?, adminReply?}` | `{id, status, adminReply, handlerId}` | 400「status 必须是 … 之一」；404「反馈 {id} 不存在」；403；401 |
| GET | `/api/admin/ai-config/list` | super | — | `[{entry, enabled, apiKeySet, apiKeyMasked, apiKeyFingerprint, apiKeyStatus, baseUrl, model, timeoutMs, maxTokens, dailyLimit, effectiveSource{...}, updatedBy, updatedAt}]` | 403；401 |
| PUT | `/api/admin/ai-config/{entry}` | super | path `entry`（`analysis`/`image_optimize`/`title_optimize`）；body `AiConfigPatchBody{api_key?, base_url?, model?, timeout_ms?, max_tokens?, daily_limit?, enabled?}`（**省略=不修改**；`null`=清除回落 env） | 单入口投影（同 list 元素） | 400 空串/掩码或指纹回写/加密密钥未配置；404「入口不存在」；403；401 |
| POST | `/api/admin/ai-config/{entry}/verify` | super | path `entry` | `{entry, model, baseUrl, message, effectiveSource{apiKey, baseUrl}}`（**不落库**） | 502 连通性失败（message 尾附「（错误码 X）」）；404；403；401 |

> ⚠️ **密钥安全**：AI 配置相关响应**永不返回密钥原文/密文/长度**，只回掩码与指纹；前端不要把 `api_key` 回显到表单默认值（提交掩码会被 400 拒绝）。

### 3.11 测试端点（3）

| 方法 | 路径 | 鉴权 | 关键入参 | 响应（`data`） | 主要错误码 |
|------|------|------|---------|---------------|-----------|
| GET | `/api/test/merchant/me` | 商家 | — | 鉴权自检信息 | 401 |
| GET | `/api/test/admin/me` | 管理 | — | 鉴权自检信息 | 401 |
| GET | `/api/test/admin/account-manage` | super | — | 鉴权自检信息 | 403；401 |

---

## 四、请求体模型字段速查（29 个）

| 模型 | 字段 | 使用端点 |
|------|------|---------|
| `AdminLoginBody` | `username, password` | `POST /api/admin/auth/login` |
| `ChangePasswordBody` | `oldPassword, newPassword` | `POST /api/admin/auth/change-password` |
| `FeishuCallbackBody` | `code` | `POST /api/auth/feishu/callback` |
| `SendLoginCodeBody` | `phone, captcha_verify_param` | `POST /api/auth/phone/send-code` |
| `PhoneLoginBody` | `phone, code` | `POST /api/auth/phone/login` |
| `TrackBody` | `event_type, page_name, task_key, stage_key, element, meta` | `POST /api/event/track` |
| `RegistrationBody` | `jd_merchant_id, shop_name` | `PUT /api/merchant/registration` |
| `CategoryItem` | `category_id, is_primary` | 同上（数组元素） |
| `CategoriesBody` | `categories` | `POST /api/merchant/category` |
| `UpdateProgressBody` | `taskId, status` | `POST /api/task/progress` |
| `StarBody` | `shopStar, serviceScore, logisticsScore, afterSaleScore, productScore, dataDate` | `POST /api/shop/star` |
| `ProductCountBody` | `totalCount, onSaleCount, offSaleCount, auditCount, dataDate` | `POST /api/shop/product-count` |
| `HealthScoreBody` | `avgScore, scoreGte90Count, score78_90Count, score60_77Count, scoreLt60Count, dataDate` | `POST /api/shop/health-score` |
| `TitleOptBody` | `mode, category, brand, model, features, condition, keyAttrs, saleAttrs, currentTitle` | `POST /api/shop/title-optimize` |
| `CreateFeedbackBody` | `content, category` | `POST /api/feedback` |
| `UpdateFeedbackBody` | `status, adminReply` | `PATCH /api/admin/feedback/{id}` |
| `StageBody` | `stage_name, next_stage_name` | `POST /api/feishu/notify/stage-complete` |
| `CreateAdminBody` | `username, password, realName, phone, email, role` | `POST /api/admin/account/create` |
| `GenerateAdminBody` | `username, realName, phone, email, role` | `POST /api/admin/account/generate` |
| `UpdateAdminBody` | `realName, phone, email, role, status` | `PUT /api/admin/account/{id}` |
| `ResetPasswordBody` | `password` | `POST /api/admin/account/{id}/reset-password` |
| `BindMemberBody` | `member_merchant_id` | `POST /api/admin/merchant/{merchantId}/bindings` |
| `AiConfigPatchBody` | `api_key, base_url, model, timeout_ms, max_tokens, daily_limit, enabled` | `PUT /api/admin/ai-config/{entry}` |
| `StageCreateBody` / `StageUpdateBody` | `stageId, stageNum, title, description, buttonText, sortOrder, phaseNum` | `/api/admin/stage/create` · `PUT /api/admin/stage/{id}` |
| `GroupCreateBody` / `GroupUpdateBody` | `taskId, stageId, title, description, buttonText, sortOrder` | `/api/admin/group/create` · `PUT /api/admin/group/{id}` |
| `TaskCreateBody` / `TaskUpdateBody` | `taskId, firstLevelTaskId, stageId, title, description, detail, type, completionType, actionText, actionUrl, actionType, actionParam, tag, defaultCompleted, sortOrder` | `/api/admin/task/create` · `PUT /api/admin/task/{id}` |

> 字段的具体校验（长度、必填、枚举、`null` 语义）**不在本文件重复**：以后端技术方案 §5.2 对应 API 节为准。

---

## 五、主要错误文案速查（**原文以真源为准**）

| code | 文案 | 触发端点族 |
|------|------|-----------|
| 400 | 「提交的内容有误，请检查后重试」 | 任意接口的 Pydantic 校验失败（**不回显字段名**，真源 §4.3.1）；**服务层参数规则校验**同样复用本句（如任务 `actionType`/`actionParam` 组合非法、商家列表 `stage`/`status` 传未登记取值） |
| 400 | 「数据日期不正确，请填写如 2026-08-05 这样的日期」 | `POST /api/shop/star`\|`product-count`\|`health-score` |
| 400 | 「文件表头无法识别，请使用商智导出的原始文件」 | `POST /api/shop/trade`\|`traffic`\|`product` |
| 400 | 「文件的日期跨度不支持，请按单日、近 7 天或近 30 天导出后重试」 | 同上 |
| 400 | 「仅支持 .xlsx 文件，.xls 请另存为 .xlsx 后上传」/「Excel 文件解析失败…」/「Excel 数据量过大，最多支持 5000 行」 | 同上 |
| 400 | 「文件过大」/「图片过大，请上传 5MB 以内的图片」 | 上传类端点 |
| 400 | 「时间范围不支持，请使用 昨天 / 近7天 / 近30天」 | `GET /api/shop/summary`（可选，默认 `7d`）、`POST /api/shop/analysis`（必填）——**同一常量** |
| 400 | 「结果过多，请按商家查询」 | `GET /api/admin/merchant/progress` |
| 400 | 「京麦商家ID仅支持数字」/「店铺名称仅支持汉字」 | `PUT /api/merchant/registration` |
| 400 | 「该商家已被登记」（#PB-36：该京麦ID 已被别的账号登记 / 已有活跃绑定组） | `PUT /api/merchant/registration` |
| 400 | 「该商家尚未登记京麦商家ID，无法绑定」/「该账号已绑定到其它商家」/「不能绑定自身」 | `POST /api/admin/merchant/{merchantId}/bindings` |
| 400 | 「该京麦商家ID已有绑定组，请刷新后重试」（#PB-37：并发建组撞唯一键，改造前为 500） | `POST /api/admin/merchant/{merchantId}/bindings` |
| 404 | 「绑定关系不存在」 | `DELETE /api/admin/merchant/{merchantId}/bindings/{memberMerchantId}` |
| 400 | 「类目不存在」/「请选择1-3个类目」/「只能选择一个主营类目」 | `POST /api/merchant/category` |
| 401 | 「未登录或 Token 已过期」/「Token 无效」 | 所有鉴权端点 |
| 401 | 「用户名或密码错误」/「旧密码错误」 | 管理员登录 / 改密 |
| 403 | 「无权限执行该操作」 | `require_roles` 拦下的写接口 |
| 403 | 「阶段二未解锁」/「数据专区未解锁」 | 阶段二 / 数据专区相关端点与 `POST /api/task/progress` |
| 404 | 「类目不存在」/「该类目暂无资费信息」/「阶段 {id} 不存在」/「反馈 {id} 不存在」/「商家不存在」 | 对应查询端点 |
| 429 | 「登录请求过于频繁，请在 N 秒后重试」/「登录失败次数过多，账号已锁定，请在 N 秒后重试」 | `POST /api/admin/auth/login` |
| 400 / 403 / 429 / 502 / 503 | **手机号登录一族（#PB-23）**：「手机号格式不正确」/「请先完成安全验证」/「验证码不正确或已过期」/「账号已被禁用，请联系平台」/「发送过于频繁，请在 N 秒后重试」/「今日发送次数已达上限，请明天再试」/「发送过于频繁，请稍后再试」/「验证尝试次数过多，请重新获取验证码」/「短信服务暂不可用，请稍后重试」/「当前发送量已达上限，请稍后再试」/「登录服务暂不可用，请稍后重试或联系管理员」（图形认证凭证未配置；与飞书登录同句）（文案单一真源 `app/services/phone_auth.py` + `captcha.py` + `sms_verify.py`；真源 §4.3 / §5.2 API-21） | `POST /api/auth/phone/send-code`、`POST /api/auth/phone/login` |
| 429 | 「操作过于频繁，请稍后再试」/「今日 AI 分析次数已用完，请明天再试」/「AI 请求繁忙，请稍后重试」 | `POST /api/shop/analysis`\|`image-optimize`\|`title-optimize` |
| 500 | 「服务器内部错误」 | 未知异常（堆栈只进日志） |
| 502 | 「飞书应用凭证获取失败，请稍后重试」/「飞书登录网络异常，请稍后重试」/**「登录服务暂不可用，请稍后重试或联系管理员」**/「…（错误码 X）」 | 飞书登录、飞书推送、AI 连通性自检 |
| 502 / 504 / 429 | AI 分析/主图/标题优化失败**按错误码细分**：超时 504「AI 分析超时，请稍后重试」、上游限流 429「AI 服务繁忙，请稍后重试」、其余 502（「AI 分析结果异常，请稍后重试」/「AI 服务未配置，请联系管理员」/「网络连接失败，请检查网络后重试」/「AI 分析失败，请稍后重试」） | AI 类端点；文案单一真源 `app/services/ai.py::error_message_for_code`（真源 §10.1） |

---

## 六、三端对接要点

### 6.1 商家端 H5（阶段一 / 阶段二 / 数据看板）

- **基址与 token**：`request.ts` 已从 `VITE_API_BASE_URL` 取基址、自动带 `Authorization: Bearer <token>`；401 时清 token 并回登录页。
- **登录**：`POST /api/auth/feishu/callback`（`{ code }`）→ 存 `token` + `merchant`。本地 `LOGIN_MODE=mock`（固定 `mock_merchant_001`），生产必须 `LOGIN_MODE=real`，凭证缺失登录 502 且不降级（真源 §6.1）。
- **阶段二接口**：进入阶段二前会返回 403「阶段二未解锁」；前端以 `GET /api/task/progress.stage2_unlocked` / `GET /api/merchant/info.current_stage` 决定入口显隐。
- **Excel 上传**：`multipart/form-data` 只传 `file`；**不要再传 `timeRange`**（已被后端忽略/移除）；`201` 表示有写入、`200` 表示全部行皆坏（此时仍要展示 `issues[]`，不要当失败弹「服务器错误」）；`issues[]` 的 `row` 是 Excel 物理行号，可直接告诉用户「第 N 行有问题」。
- **日期与数值口径**：表单 `dataDate` 支持多种形态但会显式归一（区间取结束日）；无法识别的日期**不会**被兜底成「今天」；Excel 里的坏行会被跳过并列进清单。字段级规则见真源 API-13.1/13.2。
- **AI 功能**：`analysis` 无数据时返回 `summary:null` + 中文提示；`image-optimize` 只收 jpg/png/webp ≤5MB；三者均可能 429（额度/频率），前端要给出「明天再试 / 稍后重试」而不是通用报错。

### 6.2 管理后台

- **登录**：`POST /api/admin/auth/login`；连续 5 次失败锁定 30 分钟、每分钟 10 次限流，均返回 429 且 message 带剩余秒数（真源 §5.1；**单进程内存态**，多实例不共享）。
- **商家列表**：`keyword` 一个输入框搜 4 个字段（商家ID / 昵称 / 京麦商家ID / 店铺名），占位提示建议「商家ID / 店铺名 / 昵称」；`page_size` 上界 100。
- **任务进度**：不传 `merchantId` 取全量（>5000 行报 400「结果过多，请按商家查询」），按商家聚合展示时用 `merchantId` 查询更稳。
- **角色**：`viewer` 可读平台数据；写接口需要 `admin`/`super_admin`，账号管理与 AI 配置仅 `super_admin`（403 是后端唯一可信边界，前端隐藏菜单只是体验）。
- **AI 配置**：保存时**不要**把掩码/指纹当密钥提交（会 400）；`null` = 清除回落 env，省略 = 不修改。

### 6.3 公开与静态

- `GET /health`（探活，无 `/api` 前缀）；`POST /api/event/track`（埋点，未登录也能上报，失败静默）；`GET /api/static/advisor-qr.jpg`（图片，直接 `<img src>` 引用）。

---

## 七、维护规则（派生视图的更新义务）

1. **真源先改**：任何影响接口、字段、错误码、业务规则的改动，先在 `project/docs/后端技术方案.md` 落地（并在其 §9.7 登记变更），**再回写本文件** §二~§六对应行。
2. **对齐检查**：回写后必须用 `app.openapi()` 快照核对 —— 端点总数、路径与鉴权档位要和 §三 的行数一致（当前：**78** 端点 = 77 + `/health`，OpenAPI 路径 **65** 条）。
3. **不得私设契约**：本文件不新增真源里没有的字段/错误码/枚举；发现真源与实现不一致时，**照实登记差异并上报总控**，等裁决后统一改真源，再同步本文件。
4. **不留 TBD**：本文件不得出现「待定/后续补充」类占位；暂未核实的形状要么核实，要么明确写「以真源 / 实测为准」。
5. **所有者**：后端（`py-backend`）负责在本文件登记接口现状；前端只读引用，不在此处登记新约定。
