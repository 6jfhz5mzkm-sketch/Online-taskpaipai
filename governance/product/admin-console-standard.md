# 京东拍拍二手 · 商家任务体系 — 任务管理后台开发标准

> 版本：v1.0  
> 日期：2026-07-23  
> 状态：**唯一标准（后续开发必须遵守）**
> 变更记录（2026-09-16）：新增 **§十一 用户可见文案登记**（#AF-20「行为类型 / 行为参数」文案 + #AF-21 `type` / `completionType` 下拉补齐文案）；同步 **§10.2 任务类型枚举** 补 5 个库内既有取值。口径：**dev 已验证、生产未部署**。

---

## 一、文档说明

### 1.1 文档定位

本文档是**任务管理后台开发的唯一标准**，包含：

1. 架构设计标准
2. 数据库设计标准
3. 后端模块开发标准
4. 前端开发标准
5. 账号密码管理标准
6. API接口标准
7. 安全标准
8. 开发流程标准

### 1.2 适用范围

| 模块 | 适用 |
|------|------|
| 任务管理后台（Vue 3 + Element Plus） | ✅ 完全适用 |
| 后端任务相关模块（Stage/Task） | ✅ 完全适用 |
| 管理员认证模块 | ✅ 完全适用 |
| H5任务中心（改造部分） | ✅ 适用 |

### 1.3 与其他文档的关系

| 文档 | 关系 |
|------|------|
| 01-立项文档.md | 产品需求来源 |
| 02-规划说明.md | 版本规划参考 |
| project/docs/后端技术方案.md | 后端技术规范唯一真源（本文档后端实现部分以其为准；`04-后端架构设计.md` 为 NestJS 时代历史文档） |
| AGENTS.md | AI Agent行为准则 |

---

## 二、架构设计标准

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        任务管理后台                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  admin/（独立项目）                                       │   │
│  │  Vue 3 + Vite + Element Plus + Pinia + TypeScript       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              后端 API 服务（FastAPI · api-py/）           │   │
│  │  ├── /api/admin/*（管理后台接口）                         │   │
│  │  └── /api/task/*（商家端接口）                            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              MySQL 8.0 数据库                            │   │
│  │  ├── admin_account（管理员账号）                          │   │
│  │  ├── stage_config（阶段配置）                            │   │
│  │  ├── first_level_task（一级任务）                         │   │
│  │  ├── second_level_task（二级任务）                        │   │
│  │  └── merchant_task_progress（商家任务进度）               │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 技术栈

| 层级 | 技术 | 版本 | 说明 |
|------|------|------|------|
| **前端框架** | Vue 3 | 3.4+ | Composition API + `<script setup>` |
| **构建工具** | Vite | 5.4+ | 快速构建，HMR |
| **UI组件库** | Element Plus | 2.4+ | PC端管理后台专用 |
| **状态管理** | Pinia | 2.2+ | 轻量级状态管理 |
| **路由** | Vue Router | 4.2+ | 路由管理 |
| **HTTP** | Axios | 1.6+ | 请求封装 |
| **后端框架** | Python 3.12 + FastAPI | FastAPI 0.115+ | `api-py/` 应用服务（原 NestJS `backend/` 已作废） |
| **ORM** | SQLAlchemy 2.0（同步） + PyMySQL | 2.0+ | Python ORM，同步 Session |
| **数据库** | MySQL | 8.0 | 关系型数据库 |
| **语言** | 前端 TypeScript 5.x（uni-app/管理后台）；后端 Python 3.12 | 5.x / 3.12 | 各端使用各自语言 |

### 2.3 目录结构标准

#### 后端目录

```
api-py/app/
├── main.py                       # FastAPI 应用入口（uvicorn 启动）
├── api/
│   ├── deps.py                   # 鉴权依赖：get_current_admin / require_roles
│   ├── router.py                 # 路由聚合，统一挂 /api 前缀
│   └── v1/
│       ├── admin_auth.py         # 管理员认证接口
│       ├── admin_account.py      # 管理员账号管理接口
│       ├── admin_merchant.py     # 商家任务进度（管理端）
│       ├── task.py               # 阶段/一级任务/二级任务接口
│       └── ...                   # 其余模块路由：category/fee/shop/tour/feishu/event 等
├── core/
│   ├── config.py                 # 配置读取（环境变量）
│   ├── exceptions.py             # ApiException 统一异常
│   ├── response.py               # 统一响应 { code, message, data }
│   └── security.py               # 密码哈希 / JWT 工具
├── db/
│   ├── base.py                   # Declarative Base
│   ├── engine.py                 # 引擎与连接池
│   ├── session.py                # get_db 会话依赖
│   └── models/
│       ├── admin_account.py      # 管理员账号实体
│       ├── stage_config.py       # 阶段实体
│       ├── first_level_task.py   # 一级任务实体
│       ├── second_level_task.py  # 二级任务实体
│       └── merchant_task_progress.py   # 商家任务进度实体
└── services/
    ├── auth.py                   # 认证业务逻辑
    ├── admin_account.py          # 管理员账号业务逻辑
    ├── task.py                   # 阶段/任务查询业务逻辑
    └── task_progress.py          # 商家任务进度业务逻辑
```

#### 管理后台目录

```
admin/
├── src/
│   ├── pages/
│   │   ├── login/
│   │   │   └── index.vue              # 登录页
│   │   ├── dashboard/
│   │   │   └── index.vue              # 仪表盘
│   │   ├── stage/
│   │   │   └── index.vue              # 阶段管理
│   │   ├── first-level-task/
│   │   │   └── index.vue              # 一级任务管理
│   │   ├── second-level-task/
│   │   │   ├── index.vue              # 二级任务列表
│   │   │   └── edit.vue               # 二级任务编辑
│   │   ├── account/
│   │   │   └── index.vue              # 账号管理
│   │   ├── profile/
│   │   │   └── index.vue              # 个人中心
│   │   └── ai-config/
│   │       └── index.vue              # AI 配置（仅 super_admin 可见；#AF-14）
│   ├── components/
│   │   ├── Layout/
│   │   │   └── index.vue              # 布局组件
│   │   ├── MarkdownEditor/
│   │   │   └── index.vue              # Markdown编辑器
│   │   └── AccountForm/
│   │       └── index.vue              # 账号表单弹窗
│   ├── api/
│   │   ├── request.ts                 # 请求封装
│   │   ├── auth.ts                    # 认证API
│   │   ├── stage.ts                   # 阶段API
│   │   ├── first-level-task.ts        # 一级任务API
│   │   ├── second-level-task.ts       # 二级任务API
│   │   ├── account.ts                 # 账号管理API
│   │   └── ai-config.ts               # AI 配置API（列表/更新/连通性自检）
│   ├── store/
│   │   ├── index.ts
│   │   └── modules/
│   │       ├── auth.ts
│   │       ├── stage.ts
│   │       └── task.ts
│   ├── router/
│   │   └── index.ts
│   ├── styles/
│   │   └── index.scss
│   ├── types/
│   │   └── index.ts
│   ├── utils/
│   │   └── auth.ts                    # Token管理工具
│   ├── App.vue
│   └── main.ts
├── public/
├── index.html
├── package.json
├── vite.config.ts
└── tsconfig.json
```

---

## 三、数据库设计标准

### 3.1 表结构清单

| 表名 | 用途 | 关联页面/接口 |
|------|------|----------------|
| `merchant` | 商家主表（系统核心主体） | 管理端「商家管理」页 `GET /api/admin/merchant`；商家端 `GET /api/merchant/info`、`PUT/GET /api/merchant/registration` |
| `merchant_category` | 商家经营类目（merchant↔category 多对多；任务 T1.1.2 结果） | 商家端 `POST/GET /api/merchant/category` |
| `category` | 商品类目（两级：一级 → 二级） | 商家端 `GET /api/category/list`、`GET /api/category/{id}` |
| `fee_config` | 二级类目基础资费（佣金费率 + 保证金；一个类目一套） | 商家端 `GET /api/fee/detail` |
| `fee_brand_override` | 品牌资费覆盖（特定品牌在特定类目下的费率） | 商家端 `GET /api/fee/detail`（品牌维度覆盖） |
| `category_requirement` | 二级类目入驻资质要求（API-16） | 商家端 `GET /api/category/requirement/{categoryId}` |
| `first_level_task` | 阶段下的任务分组 | 管理端「一级任务管理」页 `GET/POST/PUT/DELETE /api/admin/group/*`；商家端 `GET /api/task/stages` |
| `second_level_task` | 具体可执行的任务项 | 管理端「二级任务管理」页 `GET/POST/PUT/DELETE /api/admin/task/*`；商家端 `GET /api/task/stages` |
| `merchant_task_progress` | 商家任务完成进度（一商家一任务一行，`uk_merchant_task` 保证） | 商家端 `GET/POST /api/task/progress`；管理端「商家管理」抽屉 `GET /api/admin/merchant/progress[/{merchantId}]` |
| `merchant_stage_progress` | 商家阶段解锁/完成状态（阶段隔离依据） | 管理端 `POST /api/admin/merchant/{id}/unlock-phase1`；商家端 `GET /api/task/progress`（`stage2_unlocked`） |
| `merchant_binding_group` | 账号绑定组（同店账号：1 个京麦商家ID ↔ N 个商家账号；**只共享进度**；`uk_group_active` 保证一个京麦ID至多一个活跃组，关闭置 NULL 保留历史） | 管理端「商家进度」页抽屉「同店账号」`GET/POST /api/admin/merchant/{merchantId}/bindings`（API-22） |
| `merchant_binding_member` | 绑定组成员（账号 ↔ 组；解绑 = 行保留 + `active_key` 置 NULL，该行即审计；`uk_member_active` 保证一个账号只在一个活跃组） | 同上 + `DELETE /api/admin/merchant/{merchantId}/bindings/{memberMerchantId}`；进度共享为**读取期并集**，本表不复制/不改写任何进度行 |
| `merchant_login_code` | 商家登录短信验证码**发送/校验审计 + 频控计数**（短信走阿里云 PNVS 认证，验证码由阿里云生成与校验，**本表不存验证码哈希/盐**；留存 7 天由运维按 `created_at` 清理） | 商家端 `POST /api/auth/phone/send-code`、`POST /api/auth/phone/login`（API-21） |
| `captcha_daily_counter` | 人机校验服务端校验的**每日调用计数**（成本闸 C7；1 行/天，`INSERT … ON DUPLICATE KEY UPDATE` 原子自增，达 `LOGIN_CAPTCHA_DAILY_MAX`（默认 3000）即 503 + 告警） | 商家端 `POST /api/auth/phone/send-code`（人机校验前置） |
| `stage_config` | 阶段配置（**阶段唯一真源**；原 `stage` 表已 DROP，见下方说明） | 管理端「阶段管理」页 `GET/POST/PUT/DELETE /api/admin/stage/*`；商家端 `GET /api/task/stages` |
| `shop_star_data` | 店铺星级及各因子得分（任务 T2.5.1） | 商家端 `POST /api/shop/star`、`GET /api/shop/summary`；管理端「数据统计」页 |
| `shop_trade_data` | 交易概况数据（商智指标，T2.5.2） | 商家端 `POST /api/shop/trade`、`GET /api/shop/summary` |
| `shop_traffic_data` | 流量概况数据（商智指标，T2.5.3） | 商家端 `POST /api/shop/traffic`、`GET /api/shop/summary` |
| `shop_product_data` | 商品概况数据（商智指标，T2.5.4） | 商家端 `POST /api/shop/product`、`GET /api/shop/summary` |
| `shop_product_count` | 各状态商品数量（T2.5.5） | 商家端 `POST /api/shop/product-count`、`GET /api/shop/summary` |
| `shop_health_score` | 店铺信息健康分（T2.5.6） | 商家端 `POST /api/shop/health-score`、`GET /api/shop/summary` |
| `trademark_registry` | 品牌名称 ↔ 商标注册号映射（支撑 T2.1.2 查询） | 商家端 `GET /api/trademark/search` |
| `event_log` | 埋点事件流水（只追加，定期归档，无软删列） | 上报 `POST /api/event/track`；管理端「数据统计」页 `GET /api/event/stats` |
| `feishu_notification` | 飞书消息生命周期记录（频率控制/打开率） | `POST /api/feishu/notify/welcome`、`POST /api/feishu/notify/stage-complete` |
| `internal_notify_log` | 内部通知（飞书单聊）发送记录：`sent/failed` 留痕 + 幂等/去重键（`dedupe_key`，24h 窗口）；可观测、可手工重放；**与面向商家的 `feishu_notification` 分表** | 触发方：`POST /api/auth/phone/login`（新商家自注册 → `merchant_registered`）、`PUT /api/merchant/registration`（京麦ID重复登记 → `merchant_id_duplicate_registration`，#PB-36） |
| `feedback` | 商家反馈（功能建议/使用问题/任务异常；管理端筛选与回复） | 商家端 `POST /api/feedback`；管理端「反馈处理」页 `GET /api/admin/feedback`、`PATCH /api/admin/feedback/{id}` |
| `admin_account` | 管理后台管理员账号 | 管理端「账号管理」页 `GET/POST/PUT/DELETE /api/admin/account/*`、`POST /api/admin/account/{id}/reset-password` |
| `ai_entry_config` | AI 三入口配置覆盖（密钥**加密存储**；一入口一行；字段 NULL = 回落 env） | 管理端「AI 配置」页 `GET/PUT /api/admin/ai-config/*`（仅 super_admin） |
| `admin_ai_config_audit` | AI 配置修改审计（密钥只留掩码/长度/指纹，不落原文与密文） | 同上（每次 PUT 的每个变更字段写一行） |
| `ai_analysis_log` | AI 调用日志（限流/审计；只追加不修改） | 商家端 `POST /api/shop/analysis`、`POST /api/shop/image-optimize`、`POST /api/shop/title-optimize` |

> 上表与全量表结构真源 `project/scripts/schema.sql`（当前 **v1.10 / 30 张表**，2026-09-16 / #DB-19）**逐表一一对应：30 张全部收录**。#PL-8 复核结论（2026-09-16）：本节定位为**全量 schema 的管理端视角索引**（已含商家端表：`merchant_category` / `shop_*` / `trademark_registry` / 手机号登录三表等），故应收全 30 张而非只收管理端直接读写的表；v1.8 / #DB-13 的 3 张手机号登录表（`merchant_login_code` 段 27 / `internal_notify_log` 段 28 / `captcha_daily_counter` 段 29）已于本轮（#PL-8）补齐。列定义与 AI 密钥加密口径见 `project/docs/后端技术方案.md` §8.3.6；手机号登录三表口径见 §8.3.7；账号绑定两表口径见 §8.3.8。
>
> 阶段配置的唯一真源为 `stage_config`（表结构见 `project/scripts/schema.sql`，ORM 见 `api-py/app/db/models/stage_config.py`）。原 `stage` 表与 `stage_config` 重复且四端零调用依赖，已按 #DB-7「冗余表清理」从 dev 库与 `schema.sql` 中 **DROP**（删除发生在 v1.6；表数 24→23、唯一键 18→17），过程与备份记录见 `dev-docs/迁移交接-2026.md`。

### 3.2 表结构定义

> 本节仅收录管理后台直接操作的 **5 张核心表** DDL；其余表的列定义以 `project/scripts/schema.sql`（当前 **v1.10 / 30 张表**）为**唯一真源**，不在此重复（§3.1 已逐表列出表名/用途/关联接口）。

#### admin_account（管理员账号表）

```sql
CREATE TABLE admin_account (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  username VARCHAR(64) NOT NULL COMMENT '登录用户名',
  passwordHash VARCHAR(256) NOT NULL COMMENT '密码哈希值',
  salt VARCHAR(64) NOT NULL COMMENT '密码盐值',
  realName VARCHAR(64) NOT NULL DEFAULT '' COMMENT '真实姓名',
  phone VARCHAR(20) DEFAULT NULL COMMENT '手机号',
  email VARCHAR(128) DEFAULT NULL COMMENT '邮箱',
  role VARCHAR(16) NOT NULL DEFAULT 'admin' COMMENT '角色(super_admin/admin/viewer)',
  status TINYINT NOT NULL DEFAULT 1 COMMENT '0=禁用 1=启用',
  lastLoginAt DATETIME DEFAULT NULL COMMENT '最后登录时间',
  lastLoginIp VARCHAR(45) DEFAULT NULL COMMENT '最后登录IP',
  createdAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
  updatedAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
  deletedAt DATETIME(6) DEFAULT NULL COMMENT '软删除时间',
  PRIMARY KEY (id),
  UNIQUE KEY IDX_a6a5b15c5c225de1b4ecbfef9e (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='管理员账号表';
```

#### stage_config（阶段配置表）

```sql
CREATE TABLE stage_config (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  title VARCHAR(128) NOT NULL COMMENT '阶段标题',
  description TEXT COMMENT '阶段描述',
  status TINYINT DEFAULT 1 COMMENT '0=禁用 1=启用',
  stage_id VARCHAR(32) NOT NULL COMMENT '阶段唯一标识',
  stage_num INT NOT NULL COMMENT '阶段序号',
  button_text VARCHAR(64) NOT NULL DEFAULT '' COMMENT '按钮文案',
  sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
  phase_num INT NOT NULL DEFAULT 1 COMMENT '所属大阶段(1=阶段一/2=阶段二)',
  PRIMARY KEY (id),
  UNIQUE KEY uk_stage_id (stage_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='阶段表(Stage实体映射)';
```

#### first_level_task（一级任务表）

```sql
CREATE TABLE first_level_task (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  taskId VARCHAR(32) NOT NULL COMMENT '一级任务唯一标识',
  stageId VARCHAR(32) NOT NULL COMMENT '所属阶段',
  title VARCHAR(128) NOT NULL COMMENT '一级任务标题',
  description TEXT COMMENT '一级任务描述',
  buttonText VARCHAR(64) NOT NULL DEFAULT '' COMMENT '按钮文案',
  status TINYINT NOT NULL DEFAULT 1 COMMENT '0=禁用 1=启用',
  sortOrder INT NOT NULL DEFAULT 0 COMMENT '排序',
  createdAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
  updatedAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY IDX_61f121d89996f7548b239af555 (taskId)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='一级任务表';
```

#### second_level_task（二级任务表）

```sql
CREATE TABLE second_level_task (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  taskId VARCHAR(32) NOT NULL COMMENT '二级任务唯一标识',
  firstLevelTaskId VARCHAR(32) NOT NULL COMMENT '所属一级任务',
  stageId VARCHAR(32) NOT NULL COMMENT '所属阶段(冗余)',
  title VARCHAR(128) NOT NULL COMMENT '二级任务标题',
  description TEXT COMMENT '二级任务描述',
  detail TEXT COMMENT '任务详情(Markdown)',
  type VARCHAR(16) NOT NULL COMMENT '任务类型(mandatory/suggested/guide)',
  completionType VARCHAR(16) NOT NULL COMMENT '完成方式(system_check/manual_submit/click_read)',
  actionText VARCHAR(64) DEFAULT NULL COMMENT '操作按钮文案',
  actionUrl VARCHAR(512) DEFAULT NULL COMMENT '操作按钮链接',
  tag VARCHAR(32) DEFAULT NULL COMMENT '标签',
  defaultCompleted TINYINT NOT NULL DEFAULT 0 COMMENT '默认已完成',
  status TINYINT NOT NULL DEFAULT 1 COMMENT '0=禁用 1=启用',
  sortOrder INT NOT NULL DEFAULT 0 COMMENT '排序',
  createdAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
  updatedAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY IDX_827dce5e14d27c57b8bc5d1cb5 (taskId)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='二级任务表';
```

#### merchant_task_progress（商家任务进度表）

```sql
CREATE TABLE merchant_task_progress (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  merchantId VARCHAR(64) NOT NULL COMMENT '商家ID',
  taskId VARCHAR(32) NOT NULL COMMENT '二级任务ID',
  status VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/in_progress/completed/expired',
  completedAt DATETIME DEFAULT NULL COMMENT '完成时间',
  createdAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
  updatedAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_merchant_task (merchantId, taskId)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='商家任务进度表';
```

### 3.3 数据库规范

| 规范 | 说明 |
|------|------|
| 字符集 | utf8mb4 |
| 存储引擎 | InnoDB |
| 主键 | BIGINT UNSIGNED AUTO_INCREMENT |
| 时间字段 | DATETIME，使用 CURRENT_TIMESTAMP |
| 软删除 | deleted_at DATETIME DEFAULT NULL |
| 命名 | snake_case（目标规范；迁移期按实际库列名映射，见下方说明） |
| 注释 | 每个字段必须有COMMENT |

> **迁移期双风格（命名，现状）**：目标为 snake_case；迁移期按实际库列名映射——少数 camelCase 表（`admin_account` / `first_level_task` / `second_level_task` / `merchant_task_progress`）沿用实际列名（含其软删除列 `deletedAt`、时间戳列 `createdAt` / `updatedAt`），切换完成后再统一 snake_case。依据：`api-py/app/db/models/__init__.py:1-5`、`dev-docs/agents/Python后端Agent.md:58`（列名策略，状态更新 2026-09-10：是否统一属新决策、待总控/用户拍板，在此之前禁止擅自改列名）。
> **真源与实库一致性（2026-09-11 复核）**：`schema.sql` v1.6 已与实库对齐——上述 camelCase 表的时间列为 `DATETIME(6)` / `CURRENT_TIMESTAMP(6)`、表级 `COLLATE=utf8mb4_0900_ai_ci`、非空列显式 `NOT NULL`；除主键 `id` 外各列均带 `COMMENT`。原「collation / 时间精度待收敛」条目已由真源收敛。
> **索引命名（现状，未纳入本规范目标｜总控裁决 2026-09-10）**：唯一键命名现状**混用**——语义名（`uk_merchant_id` / `uk_feishu_open_id` / `uk_brand_number` / `uk_merchant_task` / `uk_category` / `uk_stage_id` 等）与 TypeORM 生成的哈希名（`admin_account` / `first_level_task` / `second_level_task` 的 `IDX_<hash>`，历史遗留）。**是否统一命名属新决策、待总控/用户拍板**；在此之前：新增约束请用语义名（`uk_<column>` 或 `uk_<table>_<column>`），**既有哈希名不擅自 RENAME**（改名涉及生产库 DDL 与 ORM 声明）。

---

## 四、后端模块开发标准

### 4.1 模块开发流程

```
1. 创建 Entity（app/db/models/*.py，SQLAlchemy 2.0）
2. 创建 DTO（Pydantic v2 BaseModel，随路由模块定义）
3. 创建 Service（app/services/*.py，业务逻辑）
4. 创建 Router（app/api/v1/*.py，FastAPI APIRouter）
5. 在 app/api/router.py 用 include_router 注册（api-py 无 Module 概念）
6. 创建 Migration（如果有表结构变更）
7. 更新 schema.sql
```

### 4.2 Entity 开发规范

```python
# 示例：app/db/models/stage_config.py
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StageConfig(Base):
    __tablename__ = "stage_config"
    __table_args__ = (UniqueConstraint("stage_id", name="uk_stage_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    stage_id: Mapped[str] = mapped_column(String(32), comment="阶段唯一标识")
    stage_num: Mapped[int] = mapped_column(Integer, comment="阶段序号")
    title: Mapped[str] = mapped_column(String(128), comment="阶段标题")
    description: Mapped[str] = mapped_column(Text, nullable=True, comment="阶段描述")
    status: Mapped[int] = mapped_column(SmallInteger, default=1, comment="状态")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")
```

### 4.3 DTO 开发规范

```python
# 示例：CreateStageBody（定义在 app/api/v1/admin_stage.py，Pydantic v2）
from typing import Optional

from pydantic import BaseModel, Field


class CreateStageBody(BaseModel):
    stageId: str = Field(..., min_length=1, description="阶段唯一标识")
    stageNum: int = Field(..., ge=1, description="阶段序号")
    title: str = Field(..., min_length=1, description="阶段标题")
    description: Optional[str] = Field(default=None, description="阶段描述")
    sortOrder: int = Field(default=0, ge=0, description="排序")
    # 枚举型字段用 Literal，如 status: Literal["pending", "completed"]
```

### 4.4 Service 开发规范

```python
# 示例：app/services/stage.py
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ApiException
from app.db.models.stage_config import StageConfig


def _row(stage: StageConfig) -> Dict[str, Any]:
    return {
        "id": str(stage.id),
        "stageId": stage.stage_id,
        "stageNum": stage.stage_num,
        "title": stage.title,
        "description": stage.description,
        "status": stage.status,
        "sortOrder": stage.sort_order,
    }


def find_all(db: Session) -> List[Dict[str, Any]]:
    rows = db.execute(
        select(StageConfig).order_by(StageConfig.sort_order.asc())
    ).scalars().all()
    return [_row(s) for s in rows]


def find_one(db: Session, id: int) -> Dict[str, Any]:
    stage = db.execute(
        select(StageConfig).where(StageConfig.id == id)
    ).scalar_one_or_none()
    if stage is None:
        raise ApiException(f"阶段 {id} 不存在", code=404, status_code=404)
    return _row(stage)


def create(db: Session, data: Dict[str, Any]) -> Dict[str, Any]:
    stage = StageConfig(**data)
    db.add(stage)
    db.commit()
    db.refresh(stage)
    return _row(stage)


def update(db: Session, id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    stage = db.execute(
        select(StageConfig).where(StageConfig.id == id)
    ).scalar_one_or_none()
    if stage is None:
        raise ApiException(f"阶段 {id} 不存在", code=404, status_code=404)
    for key, value in data.items():
        setattr(stage, key, value)
    db.commit()
    db.refresh(stage)
    return _row(stage)


def remove(db: Session, id: int) -> Dict[str, bool]:
    stage = db.execute(
        select(StageConfig).where(StageConfig.id == id)
    ).scalar_one_or_none()
    if stage is None:
        raise ApiException(f"阶段 {id} 不存在", code=404, status_code=404)
    db.delete(stage)
    db.commit()
    return {"success": True}
```

### 4.5 Router 开发规范

```python
# 示例：app/api/v1/admin_stage.py
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, require_roles
from app.core.response import success, success_response
from app.db.session import get_db
from app.services import stage as stage_service

router = APIRouter(prefix="/admin/stage", tags=["阶段管理"])


class CreateStageBody(BaseModel):
    stageId: str = Field(..., min_length=1)
    stageNum: int = Field(..., ge=1)
    title: str = Field(..., min_length=1)
    description: Optional[str] = None
    sortOrder: int = Field(default=0, ge=0)


@router.get("/list", summary="获取阶段列表", dependencies=[Depends(get_current_admin)])
def stage_list(db: Session = Depends(get_db)) -> dict:
    return success(stage_service.find_all(db))


@router.get("/{id}", summary="获取阶段详情", dependencies=[Depends(get_current_admin)])
def stage_detail(id: int, db: Session = Depends(get_db)) -> dict:
    return success(stage_service.find_one(db, id))


@router.post("/create", summary="创建阶段", dependencies=[Depends(require_roles("super_admin", "admin"))])
def stage_create(body: CreateStageBody, db: Session = Depends(get_db)) -> dict:
    return success_response(stage_service.create(db, body.model_dump()), status_code=201)


@router.put("/{id}", summary="更新阶段", dependencies=[Depends(require_roles("super_admin", "admin"))])
def stage_update(id: int, body: CreateStageBody, db: Session = Depends(get_db)) -> dict:
    return success(stage_service.update(db, id, body.model_dump()))


@router.delete("/{id}", summary="删除阶段", dependencies=[Depends(require_roles("super_admin", "admin"))])
def stage_remove(id: int, db: Session = Depends(get_db)) -> dict:
    return success(stage_service.remove(db, id))
```

### 4.6 路由聚合规范

> api-py 无 Module 概念，按 APIRouter + Depends 组织。

```python
# 示例：app/api/router.py（路由聚合）
from fastapi import APIRouter

from app.api.v1.admin_account import router as admin_account_router
from app.api.v1.admin_auth import router as admin_auth_router
from app.api.v1.admin_stage import router as admin_stage_router
from app.core.config import get_settings

settings = get_settings()

api_router = APIRouter(prefix=settings.API_PREFIX)

api_router.include_router(admin_auth_router)
api_router.include_router(admin_account_router)
api_router.include_router(admin_stage_router)
```

### 4.7 注册到应用入口

```python
# 示例：app/main.py（节选）
from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)
    # 聚合路由统一挂 /api 前缀（settings.API_PREFIX）
    app.include_router(api_router)
    return app


app = create_app()
```

---

## 五、账号密码管理标准

### 5.1 角色定义

| 角色 | 权限 | 说明 |
|------|------|------|
| `super_admin` | 全部权限 | 超级管理员，可管理所有模块 |
| `admin` | 任务管理权限 | 运营人员，可管理任务配置 |
| `viewer` | 只读权限 | 查看者，只能查看不能修改 |

### 5.2 密码安全规范

| 规范 | 说明 |
|------|------|
| 密码存储 | PBKDF2-SHA512 哈希，每账号随机盐 + 210000 次迭代（见 app/core/security.py） |
| 密码强度 | 最少8位，包含字母+数字 |
| 登录失败锁定 | 连续5次失败锁定30分钟 |
| Token有效期 | 7天（可通过配置调整） |

### 5.3 登录流程

```
1. 管理员输入用户名+密码
2. 后端验证密码（PBKDF2-SHA512 重算 + hmac.compare_digest 恒时比较）
3. 验证通过，生成JWT Token
4. 返回Token给前端
5. 前端存储Token（localStorage）
6. 后续请求携带Token（Authorization: Bearer <token>）
```

---

## 六、API接口标准

### 6.1 统一响应格式

```typescript
// 成功响应
{
  "code": 0,
  "message": "success",
  "data": { ... }
}

// 失败响应
{
  "code": 40001,
  "message": "参数错误",
  "data": null
}
```

### 6.2 错误码规范

| 错误码范围 | 模块 |
|-----------|------|
| 1xxxx | 通用错误 |
| 2xxxx | 管理员认证 |
| 3xxxx | 阶段管理 |
| 4xxxx | 一级任务管理 |
| 5xxxx | 二级任务管理 |
| 6xxxx | 商家进度管理 |

### 6.3 接口列表

#### 管理员认证

| 接口 | 方法 | 说明 | 权限 |
|------|------|------|------|
| `/api/admin/auth/login` | POST | 管理员登录 | 公开 |
| `/api/admin/auth/profile` | GET | 获取当前管理员信息 | 需登录 |
| `/api/admin/auth/change-password` | POST | 修改密码 | 需登录 |

#### 账号管理

| 接口 | 方法 | 说明 | 权限 |
|------|------|------|------|
| `/api/admin/account/list` | GET | 获取管理员列表 | 需登录 |
| `/api/admin/account/:id` | GET | 获取管理员详情 | 需登录 |
| `/api/admin/account/create` | POST | 创建管理员 | super_admin |
| `/api/admin/account/generate` | POST | 生成管理员账号 | super_admin |
| `/api/admin/account/:id` | PUT | 更新管理员 | super_admin |
| `/api/admin/account/:id` | DELETE | 删除管理员 | super_admin |
| `/api/admin/account/:id/reset-password` | POST | 重置密码 | super_admin |

#### 阶段管理

| 接口 | 方法 | 说明 | 权限 |
|------|------|------|------|
| `/api/admin/stage/list` | GET | 获取阶段列表 | 需登录 |
| `/api/admin/stage/:id` | GET | 获取阶段详情 | 需登录 |
| `/api/admin/stage/create` | POST | 创建阶段 | admin / super_admin |
| `/api/admin/stage/:id` | PUT | 更新阶段 | admin / super_admin |
| `/api/admin/stage/:id` | DELETE | 删除阶段 | admin / super_admin |

#### 一级任务管理

| 接口 | 方法 | 说明 | 权限 |
|------|------|------|------|
| `/api/admin/group/list` | GET | 获取一级任务列表 | 需登录 |
| `/api/admin/group/:id` | GET | 获取一级任务详情 | 需登录 |
| `/api/admin/group/create` | POST | 创建一级任务 | admin / super_admin |
| `/api/admin/group/:id` | PUT | 更新一级任务 | admin / super_admin |
| `/api/admin/group/:id` | DELETE | 删除一级任务 | admin / super_admin |

#### 二级任务管理

| 接口 | 方法 | 说明 | 权限 |
|------|------|------|------|
| `/api/admin/task/list` | GET | 获取二级任务列表 | 需登录 |
| `/api/admin/task/:id` | GET | 获取二级任务详情 | 需登录 |
| `/api/admin/task/create` | POST | 创建二级任务 | admin / super_admin |
| `/api/admin/task/:id` | PUT | 更新二级任务 | admin / super_admin |
| `/api/admin/task/:id` | DELETE | 删除二级任务 | admin / super_admin |

> 管理端 `stage` / `group` / `task` 三组接口路径以 admin 前端调用与既有实现为准：列表 `/list`、创建 `/create`、详情/更新/删除统一为 `/{id}`（GET / PUT / DELETE）。

#### 商家进度管理

| 接口 | 方法 | 说明 | 权限 |
|------|------|------|------|
| `/api/admin/merchant` | GET | 商家主表列表（**API-17**）：`page?`（默认 1）/ `page_size?`（默认 20，**上界 100**）+ `keyword?` 对 `merchant_id` / `nickname` / `jd_merchant_id` / `shop_name` **4 字段 OR 模糊包含匹配**（`LIKE '%kw%'`）+ `stage?` / `status?` **精确筛选**（已登记取值 `{onboarding, shop_setup}` / `{0,1,2}`，**传其它值 → 400**、空串或不传 = 不筛选）；`deleted_at IS NULL`、`created_at` 倒序；返回 `{ list: [**9 字段投影**（**#PB-25 起含 `status`**；不含 `phone`）], total（筛选后行数）, page, page_size }`；「商家清单」页与绑定弹窗候选列表均复用 | 需登录 |
| `/api/admin/merchant/progress` | GET | 获取商家任务进度（`merchantId` 可选；不传 = 全部商家，前端按 merchantId 聚合为商家列表） | 需登录 |
| `/api/admin/merchant/progress/:merchantId` | GET | 获取指定商家进度 | 需登录 |
| `/api/admin/merchant/:id/unlock-phase1` | POST | 商家阶段一解锁（幂等永久；:id 即 merchantId） | admin / super_admin |
| `/api/admin/merchant/{merchantId}/bindings` | GET | 同店账号绑定详情（返回 `{ jd_merchant_id, group_id, members[] }`；未绑定 → `group_id` 为 null、成员仅自己；成员含 `is_self`） | 需登录 |
| `/api/admin/merchant/{merchantId}/bindings` | POST | 绑定同店账号（body `{ member_merchant_id }`；**幂等**：目标已在同组则返回现状不重复写行；成功 **201** `{ success, group_id, members[] }`） | admin / super_admin |
| `/api/admin/merchant/{merchantId}/bindings/{memberMerchantId}` | DELETE | 解绑同店账号（路径两参数，**不暴露内部 binding id**；成功 **200** `{ success: true }`） | admin / super_admin |

> 同店账号（**API-22**，2026-09-16 / #PL-7 / #AF-18）：绑定关系统一只在管理端「商家进度」页抽屉的「同店账号」区维护（**不新增页面/路由/菜单**，故 §2.3 目录不变）；候选商家复用 `GET /api/admin/merchant?keyword=`（**API-17**，见本节上表第 1 行）搜索。契约真源见 `project/docs/后端技术方案.md` §5.2 API-22，交互与文案见 `dev-docs/任务单/merchant-account-binding-design.md` §6。

#### 反馈管理

| 接口 | 方法 | 说明 | 权限 |
|------|------|------|------|
| `/api/admin/feedback` | GET | 反馈列表（状态/分类/日期筛选） | admin / super_admin |
| `/api/admin/feedback/:id` | PATCH | 处理反馈（更新 status + admin_reply） | admin / super_admin |

#### AI 配置（2026-09-14 / #P-9 登记）

| 接口 | 方法 | 说明 | 权限 |
|------|------|------|------|
| `/api/admin/ai-config/list` | GET | 三入口（`analysis` / `image_optimize` / `title_optimize`）配置总览：掩码 + 指纹 + 状态 + 逐字段生效来源 | **仅 super_admin** |
| `/api/admin/ai-config/{entry}` | PUT | 部分更新：省略 = 不修改 / 显式 `null` = 清除并回落 env / 空串与掩码或指纹回写 = **400** | **仅 super_admin** |
| `/api/admin/ai-config/{entry}/verify` | POST | 连通性自检（`max_tokens=1`、超时上界 15s、不落库；失败恒 **502** 且附错误码） | **仅 super_admin** |

- **界面**：`admin/src/pages/ai-config/index.vue`（路由 `ai-config`；菜单项 `v-if="isSuperAdmin"`）。**非 super_admin 完全不可见**：菜单不渲染 + 路由守卫拦截 + 后端 403 三层，**后端 403 是唯一可信边界**。
- **凭据纪律**：任何响应都不返回密钥原文、密文、长度或 `AI_CONFIG_ENC_KEY` 任何形态；只回掩码/指纹/状态（口径见 `后端技术方案` §5.2 API-18 与 §8.3.6）。
- **页面文案**：集中声明在 `admin/src/constants/ai-config.ts`（页面不散落字面量）。
- **表单契约**：API Key 输入框初始为空、placeholder 显示当前掩码；保存只提交**实际改动过的字段**（未触碰 key 时请求体不含 `api_key`）——避免把掩码写回库（#AF-8 教训）。

#### 埋点统计

| 接口 | 方法 | 说明 | 权限 |
|------|------|------|------|
| `/api/event/stats` | GET | 获取埋点统计（PV/UV/任务完成率/趋势，≤90 天） | 需登录 |

#### 商家端接口

| 接口 | 方法 | 说明 | 权限 |
|------|------|------|------|
| `/api/task/stages` | GET | 获取阶段和任务列表 | 需登录 |
| `/api/task/progress` | GET | 获取商家任务进度 | 需登录 |

> 原规划端点 `/api/task/detail/:id`、`/api/task/complete` 未实现，admin 前端与商家端均未调用，已从清单移除。

---

## 七、安全标准

### 7.1 认证机制

| 机制 | 说明 |
|------|------|
| JWT Token | 管理员登录后生成，有效期7天 |
| 密码存储 | PBKDF2-SHA512 哈希，随机盐 + 210000 次迭代（存量 10000 迭代平滑迁移） |
| CORS | 仅允许指定域名访问 |
| Rate Limiting | 登录接口限制每分钟10次 |

### 7.2 权限控制

| 控制点 | 说明 |
|------|------|
| 鉴权入口 | 在 API 层用 FastAPI 依赖注入声明：Depends(get_current_admin) / Depends(get_current_merchant)；公开路由不注入鉴权依赖 |
| 角色校验 | 依赖层声明 Depends(require_roles("super_admin", "admin")) 校验，Service 层不处理角色 |
| 数据隔离 | 无「仅本人数据」隔离：管理员账号数据仅 super_admin 可写（读取为登录即可）；本人信息经 GET /api/admin/auth/profile 与 POST /api/admin/auth/change-password 读写；商家/任务/埋点等平台数据登录管理员均可读，反馈列表需 admin 及以上，写权限由角色（super_admin / admin / viewer）决定 |

### 7.3 输入校验

| 校验点 | 说明 |
|------|------|
| DTO校验 | 使用 Pydantic v2 模型（BaseModel + Field）校验 |
| SQL注入 | SQLAlchemy参数化查询/ORM |
| XSS攻击 | 前端使用v-text，后端转义输出 |

---

## 八、开发流程标准

### 8.1 开发步骤

```
1. 阅读本文档，确认开发规范
2. 创建数据库表（如果有变更）
3. 创建 Entity（app/db/models/*.py）
4. 创建 DTO（Pydantic v2 BaseModel）
5. 创建 Service（app/services/*.py）
6. 创建 Router（app/api/v1/*.py）
7. 在 app/api/router.py 用 include_router 注册
8. 编写单元测试
9. 提交代码
```

### 8.2 代码审查清单

| 检查项 | 说明 |
|--------|------|
| Entity字段类型正确 | 字段类型、长度、默认值 |
| DTO校验完整 | 必填字段、类型约束 |
| Service逻辑正确 | 业务逻辑、异常处理 |
| Router只做参数提取与依赖声明 | 不写业务逻辑 |
| 路由注册正确 | 在 app/api/router.py include_router 注册 |
| API响应格式统一 | { code, message, data } |
| 错误码已分配 | 按模块分段 |
| 公开路由已显式声明 | 不注入鉴权依赖（区别于需鉴权路由） |

### 8.3 Git提交规范

```
feat: 新增XXX功能
fix: 修复XXX问题
docs: 更新文档
style: 代码格式调整
refactor: 代码重构
test: 新增测试
chore: 构建/工具变动
```

---

## 九、验收标准

### 9.1 功能验收

| 验收项 | 验收标准 | 优先级 |
|--------|---------|--------|
| 管理员登录 | 输入正确账号密码可登录 | P0 |
| 阶段管理 | 可创建、编辑、删除阶段 | P0 |
| 一级任务管理 | 可创建、编辑、删除一级任务 | P0 |
| 二级任务管理 | 可创建、编辑、删除二级任务 | P0 |
| 任务配置后台 | 配置正确生效 | P0 |
| 商家端任务列表 | 从API获取数据，正确展示 | P0 |
| 任务完成流程 | 必做任务可正常完成 | P0 |
| 飞书推送 | 推送消息可正常送达 | P1 |
| 数据埋点 | 关键行为数据正确采集 | P1 |

### 9.2 数据验收

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 入驻任务完成率 | ≥ 70% | 上线后2周内统计 |
| 任务中心访问率 | ≥ 80% | 入驻期间至少访问1次 |
| 页面加载时间 | ≤ 2秒 | H5首屏加载时间 |

### 9.3 体验验收

| 验收项 | 验收标准 |
|--------|---------|
| 移动端适配 | 主流手机浏览器正常显示 |
| 操作流畅性 | 任务完成操作≤3步 |
| 引导清晰度 | 无经验商家可独立完成所有必做任务 |

---

## 十、附录

### 10.1 任务ID命名规范

```
格式：T{阶段编号}.{一级任务编号}.{二级任务编号}

示例：
T1.1.1 = 阶段一 > 一级任务1 > 二级任务1
T1.2.3 = 阶段一 > 二级任务2 > 二级任务3
T2.1.1 = 阶段二 > 一级任务1 > 二级任务1
```

### 10.2 任务类型枚举

```typescript
export enum TaskType {
  MANDATORY = 'mandatory',    // 必做
  SUGGESTED = 'suggested',    // 建议
  GUIDE = 'guide',            // 引导
  // #AF-21 追加（2026-09-16）：库内既有取值，此前下拉/校验未收录；真源 = DB second_level_task.type + 后端 Literal
  FORM = 'form',              // 表单
  JUMP = 'jump',              // 跳转
  UPLOAD = 'upload',          // 上传
}

export enum CompletionType {
  SYSTEM_CHECK = 'system_check',    // 系统检测
  MANUAL_SUBMIT = 'manual_submit',  // 手动提交
  CLICK_READ = 'click_read',        // 点击已读
  // #AF-21 追加（2026-09-16）：库内既有取值，此前下拉/校验未收录；真源 = DB second_level_task.completionType + 后端 Literal
  FORM_SUBMIT = 'form_submit',      // 表单提交
  FILE_UPLOAD = 'file_upload',      // 文件上传
}
```

### 10.3 角色枚举

```typescript
export enum AdminRole {
  SUPER_ADMIN = 'super_admin',
  ADMIN = 'admin',
  VIEWER = 'viewer',
}
```

## 十一、用户可见文案登记（管理后台唯一真源）

> **本节是管理后台（`admin/`）用户可见文案的唯一登记处** —— 新增或修改任何 admin 端文案必须先在此登记（文案 + 位置 + 触发条件 + 依据单号 + 状态）。依据：本文 §1.1（本文档是任务管理后台开发的唯一标准）与 owner 映射（管理后台 owner = `admin-frontend`）。
> **与商家端文案册的边界**：`project/docs/开发规则.md` §8.2 面向商家端 `project/src`（H5、uni-app）；管理后台文案集中定义在 `admin/src/constants/*`，登记在本节。两端是**独立应用、无法共享常量文件**，同一句文案两端各自单点定义，不视为重复；改动须同步各自真源。
> **状态口径**：本轮登记项均为 **dev 已验证、生产未部署**（生产部署须过 `dev-docs/部署规则.md` 确认闸）。

### 11.1 本轮登记（#AF-20 / #AF-21，2026-09-16）

| # | 文案 | 位置（常量 → 接入点） | 触发条件 | 依据 | 状态 |
|---|------|---------------------|----------|------|------|
| 1 | 行为类型 | `admin/src/constants/second-level-task.ts:76`（`ACTION_TYPE_FIELD_LABEL`）→ `admin/src/pages/second-level-task/edit.vue:94` 表单 label | 渲染任务编辑页「行为类型」表单项时 | #AF-20 | **本次新增（#AF-20）**；dev 已验证、生产未部署 |
| 2 | 行为参数 | 同文件 `:77`（`ACTION_PARAM_FIELD_LABEL`）→ `edit.vue:106` 表单 label | 同上（仅 `data_form` / `data_upload` 时可编辑，其余取值禁用） | #AF-20 | 同上 |
| 3 | 行为类型（列表列标签） | 同文件 `:80`（`ACTION_TYPE_COLUMN_LABEL`）→ `admin/src/pages/second-level-task/index.vue:39` 表头 | 渲染任务列表表头时 | #AF-20 | 同上 |
| 4 | `actionType` 10 个下拉项文案（`none` 置首，逐项见 #5~#14） | 同文件 `:19-29`（`ACTION_TYPE_OPTIONS`）→ `edit.vue:96-101`；`:33-35` 派生 `ACTION_TYPE_LABELS` 供列表只读展示 | 打开「行为类型」下拉时逐项展示 | #AF-20 | 同上 |
| 5 | 无特殊行为（有外链则打开外链） | 同上（取值 `none`） | 下拉首项（列表只读列中 `none` 不展示该文案，用占位 `—`） | #AF-20 | 同上 |
| 6 | 弹商家顾问企微二维码 | 同上（取值 `advisor_qr`） | 下拉项 | #AF-20 | 同上 |
| 7 | 卡内经营类目选择器 | 同上（取值 `category_picker`） | 下拉项 | #AF-20 | 同上 |
| 8 | 卡内资费选择器 + fee 锚点定位 | 同上（取值 `fee_picker`） | 下拉项 | #AF-20 | 同上 |
| 9 | 商标注册号查询表单 | 同上（取值 `trademark_lookup`） | 下拉项 | #AF-20 | 同上 |
| 10 | AI 标题优化面板 | 同上（取值 `title_optimize`） | 下拉项 | #AF-20 | 同上 |
| 11 | 图片优化区块 | 同上（取值 `image_optimize`） | 下拉项 | #AF-20 | 同上 |
| 12 | 顾问入口区块 | 同上（取值 `advisor_entry`） | 下拉项 | #AF-20 | 同上 |
| 13 | 数据分析专区表单录入 | 同上（取值 `data_form`） | 下拉项 | #AF-20 | 同上 |
| 14 | 数据分析专区文件上传 | 同上（取值 `data_upload`） | 下拉项 | #AF-20 | 同上 |
| 15 | `行为类型（行为参数）` 组合展示格式（label 后附「（参数值）」） | `index.vue:138-141`（`actionTypeText`：label + `（` + `actionParam` + `）`） | 列表只读列中带参数的行为类型行（便于核对「哪个表单 / 哪种上传」） | #AF-20 | 同上 |
| 16 | 提交的内容有误，请检查后重试 | `second-level-task.ts:87`（`ACTION_PAIR_VALIDATION_MESSAGE`） | 提交时 `data_*` 缺 `actionParam`、或非 `data_*` 却带 `actionParam` → 前端本地拦截（**与后端 400 同句**，取自统一校验出口原文，非新造） | #AF-20（后端真源 `app/core/error_handlers.py::VALIDATION_MESSAGE`） | 同上；本句属后端 `message` 复用，登记目的是**可检索的归属与触发条件** |
| 17 | 必做 / 建议 / 引导 | `second-level-task.ts:48-50`（`TASK_TYPE_OPTIONS` 前 3 项） | 「任务类型」下拉 | 既有文案（#AF-21 复核：标签与顺序**保持不变**） | 既有，本次仅登记 |
| 18 | 表单 / 跳转 / 上传 | 同文件 `:51-53`（追加项，对应库内真实取值 `form` / `jump` / `upload`） | 同上 | #AF-21 | **本次新增（#AF-21）**；dev 已验证、生产未部署 |
| 19 | 点击已读 / 手动提交 / 系统检测（兼容旧任务） | 同文件 `:63-65`（`COMPLETION_TYPE_OPTIONS` 前 3 项） | 「完成方式」下拉 | 既有文案（#AF-21 复核：标签与顺序**保持不变**） | 既有，本次仅登记 |
| 20 | 表单提交 / 文件上传 | 同文件 `:66-67`（追加项，对应库内真实取值 `form_submit` / `file_upload`） | 同上 | #AF-21 | **本次新增（#AF-21）**；dev 已验证、生产未部署 |
| 21 | 库内未知取值兜底项（label = 库内原值本身，不新增字面量） | `edit.vue:193-198`（`withUnknownOption`）；列表只读同口径 `index.vue:135,144` | 库内 `type` / `completionType` 出现下拉之外的取值时，**如实显示原值**（不静默改成默认值、不隐藏、提交不丢原值） | #AF-21 | **本次新增（#AF-21）**；无新增字面量 |

补充规则：

1. **单一来源**：以上文案全部定义在 `admin/src/constants/second-level-task.ts`；页面不得出现第二份字面量（本文 §8.2 代码审查清单「DTO校验完整」同精神）。
2. **枚举真源不在本节**：`type` / `completionType` / `actionType` 的**取值集合**真源是数据库列 + 后端校验（`api-py/app/api/v1/admin_task.py` 的 `TaskType` / `CompletionType` Literal，及 `project/docs/后端技术方案.md` §8.3.9）；本节只登记**展示文案**。本文 §10.2 的枚举清单已按 #AF-21 同步补齐。
3. **不新造同义句**：错误/校验提示一律复用后端 `message` 原文（同商家端 `project/docs/开发规则.md` §8.1 第 3 条口径）。
4. **跨端同句不重复登记**：管理后台与商家端若出现同一句文案，分别在各自真源登记，不互相引用为「重复」。

### 11.2 迁入登记（原《开发规则》§8.2 的管理后台文案；#PL-15，2026-09-16）

> **迁入原因**：`project/docs/开发规则.md` §8.2 面向商家端（`project/src`），历史上混入了管理后台文案；按本文档（管理后台文案唯一真源）归属，本批 **37 行**迁入本表。
> **逐字未改**：文案、位置（常量键）、触发条件、依据与状态**全部照录原文**（取自已发布快照 `frontend-rules.md`，sha256 = 迁移前 `开发规则.md` 的 `9753CBCD…4AD176`，逐字可核）；首列「原 #N」= `开发规则.md` §8.2 的**原始登记编号**（该表编号 1~76 **不重排**，原位置保留「已迁出」标注以便按号追溯）。
> **本批范围**：原 #8~#12（管理后台退出登录）/ #20~#32（AI 配置页）/ #43~#46（商家登记信息抽屉）/ #61~#68（商家清单·商家进度）/ #69~#75（同店账号）。**未迁**的相邻号段（如 #76「该商家已被登记」）经核对属**商家端**（前端无字面量、经 `project/src/api/*` 透传），保留原表。

| 原 # | 文案 | 位置（常量 → 接入点） | 触发条件 | 依据 | 状态 |
|------|------|---------------------|----------|------|------|
| 原 #8 | 退出登录 | `admin/src/constants/auth.ts`（常量 `LOGOUT_ENTRY_TEXT`；管理后台用户区下拉菜单项，接入于 `admin/src/components/Layout/index.vue`） | 管理后台已登录时用户区菜单显示入口；点击打开二次确认弹窗 | #AF-13（用户 2026-09-14「管理后台也要加退出登录」）；文案风格与商家端 #3 一致 | **本次新增（#AF-13）** |
| 原 #9 | 退出登录（确认弹窗标题） | 同文件（常量 `LOGOUT_CONFIRM_TITLE`；Element Plus `ElMessageBox` 标题） | 打开退出确认弹窗时展示 | #AF-13 | **本次新增（#AF-13）** |
| 原 #10 | 退出后需重新登录才能继续管理后台，确认退出吗？ | 同文件（常量 `LOGOUT_CONFIRM_MESSAGE`；确认弹窗正文） | 打开退出确认弹窗时展示（说明退出后果；句式与商家端 #5 一致，仅场景词改为「管理后台」） | #AF-13 | **本次新增（#AF-13）** |
| 原 #11 | 取消 | 同文件（常量 `LOGOUT_CONFIRM_CANCEL_TEXT`；确认弹窗次要按钮） | 退出确认弹窗的取消动作（不退出、仅关闭弹窗） | #AF-13 | **本次新增（#AF-13）** |
| 原 #12 | 确认退出 | 同文件（常量 `LOGOUT_CONFIRM_OK_TEXT`；确认弹窗主按钮） | 确认执行退出：清 `admin_token` / `admin_info` 并跳 `/login`（无额外 toast；管理后台 token 与商家端互相独立，只清 admin 自己的） | #AF-13 | **本次新增（#AF-13）** |
| 原 #20 | AI 配置 | `admin/src/constants/ai-config.ts`（常量 `AI_CONFIG_MENU_TEXT`；菜单项 + 页面标题，接入于 `admin/src/components/Layout/index.vue` 与 `admin/src/router/index.ts` meta.title） | super_admin 登录后侧栏显示入口；点击进入 AI 分入口配置页 | #AF-14（P7 v1.1 方案 §六；用户 2026-09-14） | **本次新增（#AF-14）** |
| 原 #21 | AI 配置页顶部说明（密钥留空=不修改、清空=回落 env） | 同文件（常量 `AI_CONFIG_PAGE_INTRO_TEXT`；页面顶部 `el-alert`） | 进入 AI 配置页即展示（说明写入语义，避免误改） | #AF-14（P7 §5.3 写入契约） | **本次新增（#AF-14）** |
| 原 #22 | 三入口展示名（AI 经营分析 / 主图优化 / 标题优化） | 同文件（常量 `AI_CONFIG_ENTRY_LABELS`；入口卡片标题） | 渲染三入口卡片标题时 | #AF-14（任务单 §3.2） | **本次新增（#AF-14）** |
| 原 #23 | 字段标签（密钥（api_key）/ 接口地址（base_url）/ 模型（model）/ 超时（ms）/ 最大 tokens / 每日限流 / 启用） | 同文件（常量 `AI_CONFIG_FIELD_LABELS`；表单 `el-form-item` label） | 渲染配置表单字段标签时 | #AF-14（P7 §6.2 字段表） | **本次新增（#AF-14）** |
| 原 #24 | 保存 / 测试连接 / 清除自定义密钥 | 同文件（常量 `AI_CONFIG_SAVE_TEXT` / `AI_CONFIG_VERIFY_TEXT` / `AI_CONFIG_CLEAR_KEY_TEXT`；各入口卡片操作按钮） | 点击触发对应动作：保存（仅提交 dirty 字段）/ 连通性自检 / 显式清除回落 env | #AF-14（P7 §6.2） | **本次新增（#AF-14）** |
| 原 #25 | 密钥正常 / 未配置密钥（回落 env）/ 加密密钥不匹配，当前回落 env | 同文件（常量 `AI_CONFIG_KEY_STATUS_OK_TEXT` / `AI_CONFIG_KEY_STATUS_NONE_TEXT` / `AI_CONFIG_KEY_STATUS_DECRYPT_FAILED_TEXT`；入口卡片状态标签） | 按后端 `apiKeyStatus`（ok / none / decrypt_failed）渲染；`decrypt_failed` 用 danger 样式显著告警，不吞成空值 | #AF-14（任务单 §3.3；P7 §5.2 状态枚举） | **本次新增（#AF-14）** |
| 原 #26 | 已配置：{掩码}（留空表示不修改）/ 未配置（留空表示不修改） | 同文件（常量 `AI_CONFIG_SECRET_PLACEHOLDER_CONFIGURED_PREFIX` / `AI_CONFIG_SECRET_PLACEHOLDER_SUFFIX` / `AI_CONFIG_SECRET_PLACEHOLDER_EMPTY`；密钥输入框 placeholder，**输入框初始为空、绝不预填掩码**） | 渲染密钥输入框占位时展示当前掩码（仅作提示，不进入表单值） | #AF-14（P7 §6.3 三条防线之一） | **本次新增（#AF-14）** |
| 原 #27 | 指纹：{16hex} / 指纹：— / 最近修改：{人} @ {时间} / 最近修改：— | 同文件（常量 `AI_CONFIG_FINGERPRINT_PREFIX` / `AI_CONFIG_FINGERPRINT_EMPTY_TEXT` / `AI_CONFIG_UPDATED_PREFIX` / `AI_CONFIG_UPDATED_EMPTY_TEXT`；卡片只读元信息） | 渲染指纹与最近修改信息时（指纹用于确认「改的是不是同一把 key」） | #AF-14（P7 §6.2 只读列） | **本次新增（#AF-14）** |
| 原 #28 | 密钥长度需在 8-256 之间 / 检测到掩码内容，请填写完整密钥 / 接口地址需以 http:// 或 https:// 开头 / 没有需要保存的修改 | 同文件（常量 `AI_CONFIG_API_KEY_LENGTH_TEXT` / `AI_CONFIG_API_KEY_MASK_REJECT_TEXT` / `AI_CONFIG_BASE_URL_FORMAT_TEXT` / `AI_CONFIG_NO_DIRTY_TEXT`；提交前本地校验提示） | 提交前拦截：空串/超长/掩码回写/格式非法/无 dirty 字段（避免发出必然 400 的请求） | #AF-14（P7 §5.3 + §6.3 第 3 条前移） | **本次新增（#AF-14）** |
| 原 #29 | 已保存，当前进程立即生效；其它 worker 最多 60 秒后生效 | 同文件（常量 `AI_CONFIG_SAVE_OK_TEXT`；保存成功 toast） | PUT 返回 200 后提示（把多 worker 生效边界写在 UI 上） | #AF-14（P7 §6.2 保存提示） | **本次新增（#AF-14）** |
| 原 #30 | 清除自定义密钥（确认框标题）/ 清除后该入口将回落使用环境变量（env）中的密钥，确认清除吗？/ 确认清除 / 取消 / 已清除自定义密钥，该入口已回落 env | 同文件（常量 `AI_CONFIG_CLEAR_CONFIRM_TITLE` / `AI_CONFIG_CLEAR_CONFIRM_MESSAGE` / `AI_CONFIG_CLEAR_CONFIRM_OK_TEXT` / `AI_CONFIG_CLEAR_CONFIRM_CANCEL_TEXT` / `AI_CONFIG_CLEAR_OK_TEXT`；`ElMessageBox` 二次确认 + 成功提示） | 点击「清除自定义密钥」时二次确认；确认后提交显式 `null`（回落 env） | #AF-14（P7 §5.3「显式 null」；任务单 §3.4） | **本次新增（#AF-14）**；注：`取消` 与 #11 字面量相同，建议后续抽公共按钮文案常量（本轮未改 #AF-13 文件） |
| 原 #31 | 无权访问该页面（仅超级管理员） | 同文件（常量 `AI_CONFIG_ROLE_DENIED_TEXT`；`admin/src/router/index.ts` 路由守卫） | 非 super_admin 直连 `/ai-config` 时提示并重定向 `/dashboard` | #AF-14（P7 §5.4 三层防线之二） | **本次新增（#AF-14）** |
| 原 #32 | 暂无 AI 配置 / 关闭后该入口整体回落 env 配置（不清空已存字段） | 同文件（常量 `AI_CONFIG_EMPTY_TEXT` / `AI_CONFIG_ENABLED_HINT_TEXT`；空态与启用开关旁提示） | 列表为空时展示空态；渲染「启用」开关说明时 | #AF-14（任务单 §3.2/§3.8） | **本次新增（#AF-14）** |
| 原 #43 | 商家登记信息（抽屉信息区标题） | `admin/src/constants/merchant.ts`（常量 `MERCHANT_INFO_TITLE`；`admin/src/pages/merchant-progress/index.vue` 详情抽屉 `el-descriptions` 标题） | 打开商家进度详情抽屉时展示 | #AF-15（用户 2026-09-14「点击商家带出京麦商家ID/店铺名称」） | **本次新增（#AF-15）** |
| 原 #44 | 京麦商家ID / 店铺名称（管理后台字段标签） | 同文件（常量 `MERCHANT_INFO_JD_ID_LABEL` / `MERCHANT_INFO_SHOP_NAME_LABEL`；抽屉信息区字段标签，**措辞与 #33/#34 商家端一致**） | 渲染详情抽屉两个字段标签时 | #AF-15 | **本次新增（#AF-15）** |
| 原 #45 | 未登记 | 同文件（常量 `MERCHANT_INFO_UNREGISTERED_TEXT`；字段空态） | `jd_merchant_id` / `shop_name` 为 `null` 或空串时展示（不显示 `null`、不隐藏该行） | #AF-15（任务单 §3.3） | **本次新增（#AF-15）** |
| 原 #46 | 加载中… / 登记信息获取失败 | 同文件（常量 `MERCHANT_INFO_LOADING_TEXT` / `MERCHANT_INFO_FAILED_TEXT`；信息区加载态与失败态） | 打开抽屉后取回登记信息期间展示加载态；请求失败展示失败态（与「未登记」区分，不静默当空值） | #AF-15（任务单 §3.3/§3.4） | **本次新增（#AF-15）** |
| 原 #61 | 商家清单（页面标题 / 侧栏菜单 / 面包屑 / 首页入口） | `admin/src/constants/merchant.ts`（常量 `MERCHANT_LIST_TITLE`；接入 `admin/src/router/index.ts` meta.title、`components/Layout/index.vue` 菜单项、`pages/dashboard/index.vue` 快捷入口） | 渲染侧栏菜单与面包屑时 | #AF-14（商家清单页；用户 2026-09-15） | **本次新增（#AF-14）** |
| 原 #62 | 商家进度（菜单项改名，原「商家管理」） | 同文件（常量 `MERCHANT_PROGRESS_TITLE`；同一批接入点） | 与新页「商家清单」区分：进度聚合页保留独立入口 | #AF-14（任务单 §2 改名并保持顺序） | **本次新增（#AF-14）** |
| 原 #63 | 商家ID / 昵称 / 京麦商家ID / 店铺名（关键词占位）；查询；重置；全部 | 同文件（常量 `MERCHANT_LIST_KEYWORD_PLACEHOLDER` / `MERCHANT_LIST_SEARCH_TEXT` / `MERCHANT_LIST_RESET_TEXT` / `MERCHANT_LIST_ALL_OPTION_LABEL`；筛选区输入与按钮、下拉「全部」项） | 关键词输入占位（说明匹配范围）；点击查询/重置；下拉未选择时 | #AF-14（冻结契约：keyword 4 字段匹配） | **本次新增（#AF-14）** |
| 原 #64 | 表格列标签：商家ID / 昵称 / 京麦商家ID / 店铺名 / 当前阶段 / 状态 / 最近活跃 / 注册时间 | 同文件（常量 `MERCHANT_LIST_COLUMN_LABELS`；`pages/merchant-list/index.vue` 表头） | 渲染商家清单表头时 | #AF-14（任务单 §1 列清单） | **本次新增（#AF-14）** |
| 原 #65 | 阶段选项与标签：入驻准备（onboarding）/ 开店搭建（shop_setup） | 同文件（常量 `MERCHANT_STAGE_OPTIONS` / `MERCHANT_STAGE_LABELS`；筛选项与列表「当前阶段」列） | 阶段下拉渲染与列表映射（未登记取值回退原值，不隐藏） | #AF-14（冻结契约 stage 枚举） | **本次新增（#AF-14）** |
| 原 #66 | 状态选项与标签：正常（1）/ 禁用（0）/ 已退出（2） | 同文件（常量 `MERCHANT_STATUS_OPTIONS` / `MERCHANT_STATUS_LABELS`；筛选项与列表「状态」列） | 状态下拉渲染与列表映射（注：当前后端投影未返回 status，列按空值占位展示，#PB-24 落地后自动生效） | #AF-14（冻结契约 status 枚举） | **本次新增（#AF-14）** |
| 原 #67 | — （列表空值占位）/ 没有符合条件的商家（空态）/ 商家列表加载失败（错误态） | 同文件（常量 `MERCHANT_LIST_VALUE_PLACEHOLDER` / `MERCHANT_LIST_EMPTY_TEXT` / `MERCHANT_LIST_FAILED_TEXT`；列表单元格与页面状态） | 时间列/普通文本列为空、筛选无结果、请求失败时展示（不显示 null、不隐藏该行） | #AF-14（任务单 §1 空值/状态要求） | **本次新增（#AF-14）** |
| 原 #68 | 查看商家清单 / 查看商家进度（首页快捷入口描述） | 同文件（常量 `MERCHANT_LIST_QUICK_DESC` / `MERCHANT_PROGRESS_QUICK_DESC`；`pages/dashboard/index.vue` 快捷入口） | 首页快捷入口列表渲染时 | #AF-14 | **本次新增（#AF-14）** |
| 原 #69 | 同店账号（区块标题）/ 绑定账号（按钮）/ 解绑（成员行操作）/ 本账号（自身行标记） | `admin/src/constants/merchant.ts`（常量 `MERCHANT_BINDING_TITLE` / `MERCHANT_BINDING_BIND_TEXT` / `MERCHANT_BINDING_UNBIND_TEXT` / `MERCHANT_BINDING_SELF_TAG_TEXT`；接入 `admin/src/pages/merchant-progress/index.vue` 抽屉「同店账号」区） | 打开商家进度详情抽屉时渲染区块标题与「绑定账号」按钮；成员行 `is_self=true` 显示「本账号」且**不渲染解绑按钮** | 设计单 `dev-docs/任务单/merchant-account-binding-design.md` §6.2；#AF-18（任务单 §1） | **本次新增（#AF-18）** |
| 原 #70 | 该商家尚未登记京麦商家ID（区内提示）/ 需先在商家端登记京麦商家ID，才能绑定同店账号（按钮 tooltip） | 同文件（常量 `MERCHANT_BINDING_UNREGISTERED_TEXT` / `MERCHANT_BINDING_UNREGISTERED_TOOLTIP_TEXT`） | `merchant.jd_merchant_id` 为空/null 时：`el-alert`(info) 常显 + 「绑定账号」按钮**禁用**（hover 才出 tooltip；禁用态点击不弹窗） | 设计单 §6.2；#AF-18 | **本次新增（#AF-18）** |
| 原 #71 | 表格列标签：商家ID / 昵称 / 状态 / 绑定时间 / 绑定人 / 操作 | 同文件（常量 `MERCHANT_BINDING_COLUMN_LABELS`；`pages/merchant-progress/index.vue` 成员表表头） | 渲染同店账号成员表表头时 | 设计单 §6.2 列清单；#AF-18 | **本次新增（#AF-18）** |
| 原 #72 | 暂无同店账号绑定（空态）/ 同店账号信息加载失败（错误态） | 同文件（常量 `MERCHANT_BINDING_EMPTY_TEXT` / `MERCHANT_BINDING_FAILED_TEXT`） | 读取成功但成员为空 / `GET /api/admin/merchant/{merchantId}/bindings` 非 2xx 时（失败态只呈现错误条，**不叠加空表**） | #AF-18 | **本次新增（#AF-18）** |
| 原 #73 | 绑定账号（弹窗标题）/ 商家ID / 昵称（搜索占位「商家ID / 昵称」）/ 搜索 / 取消 / 候选表列标签（商家ID / 昵称 / 状态）/ 没有匹配的账号 / 请先选择一个账号 | 同文件（常量 `MERCHANT_BINDING_DIALOG_TITLE` / `MERCHANT_BINDING_SEARCH_PLACEHOLDER` / `MERCHANT_BINDING_SEARCH_TEXT` / `MERCHANT_BINDING_CANCEL_TEXT` / `MERCHANT_BINDING_CANDIDATE_COLUMN_LABELS` / `MERCHANT_BINDING_CANDIDATE_EMPTY_TEXT` / `MERCHANT_BINDING_SELECTED_REQUIRED_TEXT`） | 打开绑定弹窗（默认空关键字拉第 1 页候选，**剔除当前商家自身**）；未选行点「绑定账号」给 warning | 设计单 §6.2（候选**只展示 3 列**：商家ID / 昵称 / 状态，**绝不展示手机号**）；#AF-18 | **本次新增（#AF-18）** |
| 原 #74 | 确认绑定（标题）/ 绑定后两个账号共享阶段/任务进度；账号级标记（新手引导、欢迎消息、数据专区解锁标记）不共享（正文）/ 确认绑定（主按钮）；确认解绑（标题）/ 解绑后该账号不再共享本店进度；已完成的进度记录保持不变（正文）/ 确认解绑（主按钮） | 同文件（常量 `MERCHANT_BINDING_CONFIRM_TITLE` / `MERCHANT_BINDING_CONFIRM_MESSAGE` / `MERCHANT_BINDING_CONFIRM_OK_TEXT` / `MERCHANT_BINDING_UNBIND_CONFIRM_TITLE` / `MERCHANT_BINDING_UNBIND_CONFIRM_MESSAGE` / `MERCHANT_BINDING_UNBIND_CONFIRM_OK_TEXT`；`ElMessageBox.confirm`） | 绑定/解绑二次确认弹窗展示；点「取消」不发送任何写请求 | 设计单 §6.2 **原文照录**（不得改写）；#AF-18 | **本次新增（#AF-18）** |
| 原 #75 | 绑定/解绑的结果提示（前端无字面量） | `admin/src/pages/merchant-progress/index.vue`（成功：`ElMessage.success(res.message)`；失败：由 `admin/src/api/request.ts` 拦截器按后端 `message` 原样 toast） | 绑定/解绑请求返回后 | 后端文案真源（如「该商家已被登记」「该商家尚未登记京麦商家ID，无法绑定」「该账号已绑定到其它商家」「不能绑定自身」「绑定关系不存在」）；前端**不新造同义句**（§8.1 第 3 条）；#AF-18 | **本次新增（#AF-18）** |

---

> **本文档是任务管理后台开发的唯一标准，后续开发必须遵守。**
