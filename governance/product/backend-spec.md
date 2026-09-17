# 后端技术方案

> 版本：v2.0
> 日期：2026-09-10（原 v1.0 · 2026-07-20）
> 状态：定稿（技术口径已同步为 `api-py`）
> 权威性：本文件是后端开发的唯一技术依据。任何语言、框架、核心 SDK 的变更必须先修改本文档并说明原因。
> 技术口径：Python 3.12 + FastAPI + SQLAlchemy 2.0（同步）+ PyMySQL（`api-py/`，唯一运行后端）；原 NestJS `backend/` **已作废、禁止修改**（仅作契约历史参考）。接口清单（API-01~API-16）、业务规则、错误码、阶段隔离规则等合同语义未变。

---

## 一、技术栈定选

> **口径说明（2026-09-10）**：后端已由 NestJS（`backend/`，已作废）迁移至 Python/FastAPI（`api-py/`，唯一运行后端）。本章及全文技术口径以 `api-py/` 现状为准；接口契约（路径/字段/错误码）对前端零改动。

### 1.1 技术栈总览

| 层级 | 技术方案 | 版本 |
|------|---------|------|
| **运行时** | Python | 3.12 |
| **后端框架** | FastAPI（内建 OpenAPI：`/docs`、`/redoc`） | ≥0.115 |
| **ORM / 驱动** | SQLAlchemy（同步）+ PyMySQL | ≥2.0 / ≥1.1 |
| **校验** | Pydantic v2（类型即校验） | ≥2.7 |
| **语言** | Python 3.12（类型注解） | 3.12 |
| **数据库** | MySQL | 8.0 |
| **缓存** | 无（当前未使用 Redis；仅 AI 结果用进程内缓存，见 §10.5） | - |
| **认证** | JWT（python-jose；商家 / 管理员**双 secret**） | - |
| **迁移** | Alembic（**仅结构一致性校验，禁止 autogenerate 执行**，见 §8.3） | ≥1.13 |
| **包管理** | uv（`uv run`） | - |
| **部署** | uvicorn + Nginx（阿里云轻量 1GiB） | - |

### 1.2 选择理由

| 理由 | 说明 |
|------|------|
| 单一运行后端 | `api-py/` 是唯一运行后端（uvicorn，端口 8000，**未启用 `--reload`**，代码变更后须手动重启）；原 NestJS `backend/` 已作废 |
| 类型即校验 | Pydantic v2 直接承担请求/响应校验与 OpenAPI 文档生成，无需再引独立校验层 |
| 同步 ORM 足够 | 当前商家规模下同步 SQLAlchemy 2.0 + PyMySQL 已足够，避免异步驱动带来的复杂度 |
| 部署成本可控 | 阿里云轻量 1GiB 单机可承载；部署口径见 `dev-docs/部署方案-阿里云轻量1gib.md` |
| 契约可验证 | 对前端零改动（字段名、统一响应、错误码不变）；`api-py/tests/` 提供 pytest 回归基线 |
| 工具链统一 | uv 管理依赖与虚拟环境；Alembic 负责结构一致性校验（只校验、不改库） |

### 1.3 原「不选其他方案」评估（已失效）

原 1.3 的技术选型对比表基于 NestJS 路线（其中含「不选 Python / FastAPI」），**该路线已作废**，对比结论不再作为当前依据；迁移决策与影响登记见 §9.7 变更记录。当前口径：**Python 3.12 + FastAPI + SQLAlchemy 2.0（同步）+ PyMySQL**。

### 1.4 重新评估条件

以下任一条件满足时，必须重新评估技术栈：

| 触发条件 | 说明 |
|---------|------|
| 商家数超过 5000 家 | 单机同步 ORM 可能需要读写分离或异步栈 |
| 日活超过 2000 | 单进程 uvicorn 需要多 worker 或反向代理层扩展 |
| 团队超过 10 人 | 需要更严格的架构约束与模块边界 |
| 需要 AI/ML 模型训练 | 需要独立训练侧，与在线服务解耦 |

---

## 二、核心依赖清单

### 2.1 FastAPI 及其生态自带能力（开箱即用）

| 能力 | 说明 |
|------|------|
| 路由系统 | `APIRouter` + `@router.get/@router.post` 声明式路由（`app/api/v1/` 按业务域一文件） |
| 依赖注入 | `Depends`：数据库会话 `get_db`、鉴权 `get_current_merchant`/`get_current_admin`、角色守卫 `require_roles` |
| 数据校验 | Pydantic v2 模型 + `RequestValidationError` 全局处理（400 + 只返回首个错误） |
| 异常处理 | 全局异常处理器（`app/main.py`）：业务异常 `ApiException` / HTTP 异常 / 未知异常兜底 500 |
| 配置管理 | pydantic-settings 读 `api-py/.env` + 环境变量（`app/core/config.py`，含启动期 fail-fast 校验） |
| API 文档 | 内建 OpenAPI：`/docs`、`/redoc`、`/openapi.json`（**仅 `DEBUG=true` 开放，生产 404**） |
| HTTP 客户端 | httpx（飞书 OAuth、AI 调用） |
| CORS | `CORSMiddleware` |
| 健康检查 | `GET /health`（不带 `/api` 前缀） |

### 2.2 已安装依赖（`api-py/pyproject.toml`，由 uv 管理）

| 能力 | 依赖 | 说明 |
|------|------|------|
| Web 框架 / ASGI | fastapi、uvicorn[standard] | 应用与服务器 |
| ORM / 驱动 | sqlalchemy（≥2.0）、pymysql、cryptography | 同步 ORM + MySQL 驱动 |
| 校验 / 配置 | pydantic（v2）、pydantic-settings | 请求校验 + 配置 |
| 认证 | python-jose[cryptography] | JWT 签发与校验 |
| 迁移 | alembic | **仅结构校验**（见 §8.3） |
| Excel | openpyxl | **仅支持 .xlsx**（.xls 明确拒绝并给出指引），含大小/行数上限防护 |
| 飞书 | lark-oapi | 仅保留导入；登录/通知主链路走 httpx 直连 OAuth；内部 IM 通知（§5.2 API-21 / §七）复用其 `im.v1.message.create` |
| 短信 / 人机校验（#PB-23 / #PB-23-R2 / #PB-23-R4） | alibabacloud_dypnsapi20170525（号码认证 PNVS：`SendSmsVerifyCode` / `CheckSmsVerifyCode`）、alibabacloud_tea_openapi；**接入点 `ALIYUN_SMS_ENDPOINT` 必须是 `dypnsapi.aliyuncs.com`**（默认值已改为此；`dysmsapi.aliyuncs.com` 是**短信服务**产品、不认识这两个 Action → `InvalidAction.NotFound` → 统一 502） | **短信验证码由阿里云生成与校验**，我方不接触明文（`ReturnVerifyCode=false`）→ 唯一出口 `app/services/sms_verify.py`；**图形认证（人机校验）走官方 HTTP 二次校验接口**（`POST /validate`、form-urlencoded、HMAC-SHA256 签名），用既有 `httpx` 实现、**不引入额外 SDK** → 唯一接缝 `app/services/captcha.py`（曾用的 `alibabacloud_captcha20230305` 已移除） |
| HTTP / 上传 | httpx、python-multipart | 外部调用 + 表单与文件上传 |
| 测试（dev） | pytest、pytest-cov | `api-py/tests/` |

**新增依赖规则见 §9.2**；历史遗留依赖（Redis、slowapi、passlib 等已移除项）**不得回引**。

---

## 三、后端目录规范

```
api-py/
├── app/
│   ├── main.py                       # FastAPI 应用装配入口（CORS / 全局异常处理器 / 健康检查）
│   ├── core/                         # 公共层
│   │   ├── config.py                 # pydantic-settings 配置 + 启动期 fail-fast 校验
│   │   ├── response.py               # 统一响应 {code,message,data} 构造
│   │   ├── exceptions.py             # 业务异常 ApiException（message + code + status_code）
│   │   ├── security.py               # 密码哈希（pbkdf2-sha512）/ JWT 编解码
│   │   ├── timeutil.py               # datetime -> ISO8601 毫秒 + Z
│   │   └── utils.py                  # 通用工具（客户端 IP 等）
│   │
│   ├── api/                          # 协议层：只做参数提取、鉴权依赖与 service 调用
│   │   ├── router.py                 # 路由聚合（统一挂 /api 前缀，/health 除外）
│   │   ├── deps.py                   # 鉴权依赖：商家 / 管理员 / 角色守卫
│   │   └── v1/                       # 按业务域一文件
│   │       ├── auth.py, merchant.py, task.py, category.py, fee.py, event.py
│   │       ├── feedback.py, shop.py, feishu.py, trademark.py, tour.py, test.py
│   │       └── admin_auth.py, admin_account.py, admin_merchant.py
│   │
│   ├── services/                     # 业务规则层（业务语义唯一 owner）
│   │   ├── auth.py, merchant.py, task.py, task_progress.py
│   │   ├── category.py, category_requirement.py, fee.py
│   │   ├── event.py, event_core.py, feedback.py, shop.py
│   │   ├── trademark.py, tour.py, feishu.py, ai.py, admin_account.py
│   │
│   └── db/                           # 数据访问层
│       ├── engine.py                 # SQLAlchemy engine / SessionLocal（pool_pre_ping、utf8mb4）
│       ├── session.py                # FastAPI 依赖 get_db
│       ├── base.py                   # DeclarativeBase
│       └── models/                   # ORM 模型：一表一文件，按实际库列名映射
│
├── alembic/                          # 迁移环境（env.py）
├── alembic.ini
├── scripts/                          # 校验/对账脚本
├── tests/                            # pytest 用例 + conftest 隔离夹具
├── pyproject.toml / uv.lock
├── run_uvicorn_guard.cmd             # 本地启动守卫
└── .env（未提交）/ .env.example
```

### 目录规则

| 规则 | 说明 |
|------|------|
| 一个业务域 = 一个 service 文件 + 对应路由文件 | 如 `services/shop.py` ↔ `api/v1/shop.py`；路由只做协议映射与依赖注入 |
| 业务语义禁止落在协议层 | `api/v1/*.py` 不写业务规则与 SQL，只调用 `services/*` |
| ORM 模型按表归属 | 一表一文件，位于 `app/db/models/`；跨域数据访问走 service 方法，不在路由里直接引用别的域模型 |
| 模型模块命名 | 与表名同名（如 `merchant_stage_progress.py`）；类名为 PascalCase（`MerchantStageProgress`） |
| 新模型注册 | 必须在 `app/db/models/__init__.py` 的 import 列表与 `__all__` **同时**登记（既有回归用例守护） |
| 公共代码放 core/ | 不属于任何业务域的配置、响应、异常、鉴权、工具放 `app/core/` |
| 列名策略 | ORM 按**实库列名**映射：snake_case 表用 snake_case；camelCase 表（`admin_account`/`first_level_task`/`second_level_task`/`merchant_task_progress`）用 camelCase。**统一 snake_case 属新决策，未经拍板不得擅自改列名** |
| 结构声明与真源对齐 | ORM 的索引/唯一约束声明必须与 `project/scripts/schema.sql` 及实库一致（见 §8.3） |

### 文档章 -> api-py 代码路径对照

| 文档章 | api-py 代码路径 |
|--------|----------------|
| §三 目录规范（分层） | `api-py/app/`：`core/`（公共）、`api/`（协议）、`services/`（业务）、`db/`（数据）；`api-py/tests/`、`api-py/alembic/` |
| §四 统一响应格式 | `app/core/response.py`（`success`/`error`/`api_response`）、`app/main.py`（全局异常处理器）、`app/core/exceptions.py` |
| §5.1 鉴权 | `app/api/deps.py`（`get_current_merchant`/`get_current_admin`/`require_roles`）、`app/core/security.py`、`app/core/config.py`（双 secret） |
| §8.3 数据库/迁移/结构校验 | `app/db/engine.py`、`app/db/session.py`、`app/db/models/*.py`、`alembic/env.py`、`alembic.ini` |

---

## 四、统一响应格式

### 4.1 类型定义

```python
# 统一响应（契约，与语言无关；实现见 app/core/response.py 的 success/error/api_response）
# 成功: { "code": 0,   "message": "success", "data": ... }
# 失败: { "code": 400, "message": "...",     "data": null }

# 列表响应数据（契约）
ListData = { "list": [], "total": 0, "page": 1, "page_size": 20 }

# 分页查询参数（契约）
PaginationQuery = { "page": 1, "page_size": 20 }   # page 默认 1；page_size 默认 20，最大 100
```

### 4.2 成功场景

场景 A：对象（详情、创建、更新）

`json
{
  "code": 0,
  "message": "success",
  "data": {
    "merchant_id": "M001",
    "nickname": "测试商家",
    "current_stage": "onboarding"
  }
}
`

场景 B：列表（分页查询）

`json
{
  "code": 0,
  "message": "success",
  "data": {
    "list": [
      { "id": 1, "name": "二手手机" },
      { "id": 2, "name": "二手电脑" }
    ],
    "total": 128,
    "page": 1,
    "page_size": 20
  }
}
`

场景 C：空列表

`json
{
  "code": 0,
  "message": "success",
  "data": { "list": [], "total": 0, "page": 1, "page_size": 20 }
}
`

场景 D：无返回值（删除、状态变更）

`json
{
  "code": 0,
  "message": "success",
  "data": null
}
`

### 4.3 失败场景

| 场景 | HTTP 状态码 | code | message 示例 |
|------|------------|------|-------------|
| 参数错误 | 400 | 400 | "授权码不能为空" |
| 未登录/Token 过期 | 401 | 401 | "未登录或 Token 已过期" |
| 无权限 | 403 | 403 | "无权限访问" |
| 资源不存在 | 404 | 404 | "商家不存在" |
| 频率限制 | 429 | 429 | "操作过于频繁，请稍后再试" |
| 服务器异常 | 500 | 500 | "服务器内部错误" |
| 第三方服务异常 | 502 | 502 | "第三方服务异常" |
| 服务暂不可用（**503 新增分段，#PB-23**） | 503 | 503 | ① "当前发送量已达上限，请稍后再试"（登录验证码全局日上限 / 人机校验成本闸；`logger.error` 告警）；② **"登录服务暂不可用，请稍后重试或联系管理员"**（**图形认证凭证未配置 = 服务侧配置故障**，#PB-23-R3；与 `services/feishu.py::FEISHU_LOGIN_UNAVAILABLE_MESSAGE` **同句同源**，缺哪个变量只进 `logger.error`） |

> 手机号 + 短信验证码登录（API-21）的**完整文案表**见 §5.2：400「手机号格式不正确」/「请先完成安全验证」/「验证码不正确或已过期」、403「账号已被禁用，请联系平台」、429「发送过于频繁，请在 N 秒后重试」/「今日发送次数已达上限，请明天再试」/「发送过于频繁，请稍后再试」/「验证尝试次数过多，请重新获取验证码」、502「短信服务暂不可用，请稍后重试」、503（本行）。


> **账号绑定（API-22）与登记唯一性（API-20 扩展）文案（#PB-36；owner = 服务层单一真源，前端只展示后端 `message`）**：
>
> | 场景 | HTTP 状态码 | code | message |
> |------|------------|------|---------|
> | 登记：`jd_merchant_id` 已被别的活跃账号登记 / 已有活跃绑定组 | 400 | 400 | **"该商家已被登记"** |
> | 绑定：发起方未登记 `jd_merchant_id` | 400 | 400 | "该商家尚未登记京麦商家ID，无法绑定" |
> | 绑定：目标账号已在其它活跃组（含**并发**场景） | 400 | 400 | "该账号已绑定到其它商家" |
> | 绑定：该京麦商家ID 已被别的活跃组占用（**并发**建组，uk_group_active 1062） | 400 | 400 | **"该京麦商家ID已有绑定组，请刷新后重试"**（`bind_member` 唯一新增口径；#PB-37 D） |
> | 绑定：目标是自身 | 400 | 400 | "不能绑定自身" |
> | 解绑：绑定关系不存在 | 404 | 404 | "绑定关系不存在" |
> | 绑定/解绑：商家不存在（含软删） | 404 | 404 | "商家不存在"（复用既有文案） |
>
> **成功响应（API-22；信封 `{code: 0, message: …, data: {…}}`，`message` 必须是中文专句，不得返回通用 `success`）**：
>
> | 端点 | HTTP | code | message |
> |------|------|------|---------|
> | `POST /api/admin/merchant/{merchantId}/bindings` | 201 | 0 | **"绑定成功"**（`services/merchant_binding.py::BIND_SUCCESS_MESSAGE`） |
> | `DELETE /api/admin/merchant/{merchantId}/bindings/{memberMerchantId}` | 200 | 0 | **"已解绑"**（`RELEASE_SUCCESS_MESSAGE`） |

失败响应格式：

`json
{
  "code": 400,
  "message": "授权码不能为空",
  "data": null
}
`

#### 4.3.1 参数校验失败与框架级错误文案（#PB-18 / #T-3 R6 统一口径；#PB-24-1-R1 口语化）

实现位置：`app/core/error_handlers.py::register_exception_handlers`（**唯一注册点**，路由内不得自行处理这些异常）。

| 场景 | HTTP 状态码 | code | message 口径 |
|------|------------|------|-------------|
| 参数校验失败（`RequestValidationError`） | 400 | 400 | **固定一句口语化中文：「提交的内容有误，请检查后重试」**（`app/core/error_handlers.py::VALIDATION_MESSAGE`）——**不回显字段名**（`totalCount`/`jd_merchant_id` 这类英文字段名对商家用户没有意义，用户裁决 2026-09-15）、**不暴露校验规则**；排障信息不丢（完整 `loc`/`type`/`msg` 只进日志） |
| 路由不存在 | 404 | 404 | 「接口不存在」 |
| 方法不允许 | 405 | 405 | 「请求方法不允许」 |
| 其它框架 HTTP 异常 | 原状态码 | 原状态码 | 沿用 `detail`（业务 404/403 等仍由 `ApiException` 给出业务文案，如「商家不存在」） |
| 未知异常 | 500 | 500 | 「服务器内部错误」（堆栈只进日志） |

硬口径：

- **不回显字段名与内部路径**：用户可见 message **既不出现字段名**（原「：字段 <字段名>」后缀已按用户裁决移除），**也不出现 `body.`/`query.`/`path.`/`header.`/`cookie.` 等 Pydantic/FastAPI Loc 前缀**。
- **接口专用校验文案**：对**高频且用户可自行修正**的字段，允许（且鼓励）在接口真源登记**专句**替代通用句；专句必须回答「该怎么填」。首个专句：`POST /api/shop/star|product-count|health-score` 的 `dataDate` → 「数据日期不正确，请填写如 2026-08-05 这样的日期」（单一真源 `app/services/shop.py::DATA_DATE_INVALID_MESSAGE`，见 API-13）。API-13 另登记两条 Excel 导入专句（表头无法识别 / 文件日期跨度不支持）与逐行问题清单文案；API-14/API-15 登记数据看板 `time_range` 非法入参专句（两者共用同一常量）；**API-21 登记手机号登录专句**「手机号格式不正确」（`app/services/phone_auth.py::PHONE_INVALID_MESSAGE`，服务层 owner）与「请先完成安全验证」（`app/services/captcha.py::CAPTCHA_REQUIRED_MESSAGE`）——**文案与实现同源，本处只做指路、不复制**。
- **完整校验细节只进日志**：`logger.warning` 记录 `loc`/`type`/`msg`（单次最多 20 条，有界）；**必须丢弃 Pydantic 的 `input`/`ctx`**，避免把请求体中的 password/token 等敏感值写入日志。
- **响应信封与状态码语义不变**：仍为 `{code, message, data}` 三字段、`data` 失败时为 `null`、HTTP 状态码保持既有分段（前端依赖该信封）。
- **文案一律中文**（与项目其它用户可见文案一致）。

## 五、API 接口规范

### 5.1 认证机制

- **认证方式**：JWT（JSON Web Token，python-jose 签发/校验）
- **Token 位置**：`Authorization: Bearer <token>`
- **Token 有效期**：7 天（`JWT_EXPIRES_IN` / `ADMIN_JWT_EXPIRES_IN`）
- **Token 内容**：商家 `{ merchant_id, role, iat, exp }`；管理员 `{ sub, role, iat, exp }`
- **密钥隔离**：商家 token 与管理员 token 使用**两个独立 secret**（`JWT_SECRET` / `ADMIN_JWT_SECRET`），非 dev 环境启动期强制校验二者不相同且非公开兜底值
- **登录方式（#PB-23）**：除飞书 OAuth（API-01，保留不删）外，新增**手机号 + 短信验证码**（API-21）——验证码由**阿里云号码认证（PNVS）生成与校验**（`SendSmsVerifyCode` / `CheckSmsVerifyCode`），我方 `ReturnVerifyCode=false`、**不接收不落库不打印明文码**；登录即注册（允许任意手机号）、登录入口拦截 `status != 1`（403）、频控矩阵 C1~C10 全部落库计数（无 Redis）。
- **角色类型**：merchant（商家）、admin（管理员，角色口径见 `project/docs/任务管理后台开发标准.md`）
- **实现位置**：`app/api/deps.py`（`get_current_merchant` / `get_current_admin` / `require_roles`）
- **管理员登录失败锁定**（真源 `project/docs/任务管理后台开发标准.md` §5.2「连续5次失败锁定30分钟」）：
  - 口径：同一用户名连续失败达 `ADMIN_LOGIN_MAX_ATTEMPTS`（默认 **5**）即锁定 `ADMIN_LOGIN_LOCK_MINUTES`（默认 **30 分钟**）；**锁定期内即使口令正确也拒绝**；登录成功清零该账号计数。阈值/时长走环境变量可配。
  - 响应：锁定期间返回 **429**，message 形如「登录失败次数过多，账号已锁定，请在 N 秒后重试」（含剩余锁定秒数，取值 **∈ [1, 配置窗口]**；取整由 `app/services/auth.py::_lock_seconds_left` 统一实现并抹掉浮点尾差，#PB-34）；未达阈值仍为 401「用户名或密码错误」。
  - 实现位置：`app/services/auth.py`（服务层单一真源，路由层不散落 if；存储类 `_LoginAttemptStore`）。
  - **边界（重要）**：该实现为**单进程内存态**——uvicorn 多 worker 或多实例部署时各进程各算一份、锁定不共享，进程重启后计数与锁定全部丢失；有容量上限 `MAX_TRACKED_LOGIN_KEYS=1000` 与过期清理（禁止无界增长）。**未来多点部署必须改为落库方案**（或引入本项目当前未使用的 Redis）。
- **管理员登录请求限流**（真源 `project/docs/任务管理后台开发标准.md` §7.1「Rate Limiting：登录接口限制每分钟10次」）：
  - 口径：滑出窗口内同一 **IP** 与同一 **用户名** 各最多 `ADMIN_LOGIN_RATE_MAX`（默认 **10**）次登录请求，窗口 `ADMIN_LOGIN_RATE_WINDOW_SECONDS`（默认 **60 秒**）；两个维度是**两把独立预算**，任一超限即拒绝。
  - 响应：超限返回 **429**，message 形如「登录请求过于频繁，请在 N 秒后重试」（含需等待秒数，取值 **∈ [1, 窗口长度]**）；被拒请求不登记，避免持续攻击把窗口无限延后。
  - 与失败锁定的关系：限流对**全部请求**（含成功）按窗口计数、不锁定；失败锁定只对**失败**按**用户名**连续计数并锁定 30 分钟；两者都在 `app/services/auth.py` 服务层，路由层无 if。
  - 实现位置：`app/services/auth.py`（存储类 `_LoginRateLimiter`）；边界同上（**单进程内存态**，多 worker/多实例不共享、重启即失；有容量上限与过期清理，需跨进程一致时须落库）。

### 5.2 接口清单

#### API-01：飞书登录

```
POST /api/auth/feishu/callback
```

| 维度 | 内容 |
|------|------|
| 功能 | 商家通过飞书 OAuth 授权后，后端换取用户信息，创建/更新商家记录，返回 JWT Token |
| 请求参数 | code (飞书授权码，必填，string) |
| 响应 | { token: string, merchant: MerchantInfo } |
| 涉及表 | merchant（INSERT 或 UPDATE） |
| 权限校验 | 无需（公开接口） |
| 参数校验 | code 不能为空 |
| 异常情况 | ① 飞书授权码无效 → 401 "授权失败" ② 飞书 API 调用失败 → 502 "第三方服务异常" ③ 商家 status=0 → 403 "账号已被禁用" |
| 凭证不合规（#PB-31 用户裁决） | 后端配置缺失/占位 → **502「登录服务暂不可用，请稍后重试或联系管理员」**（单一真源 `app/services/feishu.py::FEISHU_LOGIN_UNAVAILABLE_MESSAGE`）：**登录页用户文案不得出现环境变量名、不得出现「未配置/占位」等运维语**；判定依据（`FEISHU_APP_ID` 缺失、`FEISHU_APP_SECRET` 缺失/占位；占位清单单一真源 `app/core/config.py::FEISHU_SECRET_PLACEHOLDERS`）**只写 `logger.error`**（`app_id=missing/set, app_secret=missing/placeholder/set, required_env=[...]`，不回显任何密钥材料），运维可查、用户不可见；**触发条件与行为不变**（配置不合规即 502、绝不降级 mock） |
| V1 例外登记（#PB-26） | ⚠️ V1 未实现 · 例外登记（2026-09-15）· 移除条件=实现『禁用商家』功能时同步实现鉴权侧拦截（`app/api/deps.py::get_current_merchant`）并撤销测试侧 xfail 标记（`api-py/tests/test_merchant_status_guard.py`） |
| 业务逻辑 | 1. 取 app_access_token（见下）2. 用 code 换 user access_token 3. 用 access_token 获取用户信息 4. 查 merchant 表，存在则更新 last_active_at，不存在则 INSERT 5. 生成 JWT 返回 |
| 飞书调用链（**2026-09-14 生产实测口径 / #PB-14**） | ① `POST /open-apis/auth/v3/app_access_token/internal` body `{app_id, app_secret}`（20s 超时）→ `app_access_token`；② `POST /open-apis/authen/v1/oidc/access_token` **必须带请求头 `Authorization: Bearer <app_access_token>`**，body `{grant_type:"authorization_code", code, client_id, client_secret}` → `user access_token`；③ `GET /open-apis/authen/v1/user_info`（Bearer = user access_token）→ `{open_id, union_id, name, avatar_url}`。 |
| 错误码含义（排障用） | **缺 ① 的 Bearer 头时 ② 返回 `code=20014`「The app access token passed is invalid」且拿不到 user access_token**（根因，非权限/应用配置/前端授权地址问题）；**`code=20003` = 授权码无效/已过期（生产实测：用户点登录时命中；飞书授权码一次性，重复使用或超时即报此码）**；① 返回 `code!=0` → 应用凭证无效/配置错误；③ 返回非 0 → user access_token 无效或接口权限不足。 |
| 错误码→用户文案映射（单一真源） | 服务层 `app/services/feishu.py::OIDC_ERROR_MESSAGES`（纯函数 `_oidc_failure_message`，路由不得自行拼装）：**`20003` → 「登录链接已失效，请重新点击飞书登录」（不展示裸码）**；**其它未列出的码保持附码**「飞书授权失败，请重新登录（飞书错误码 N）」（排障需要）；响应无 `code` 时用不着码的友好文案。 |
| 可诊断性 | 飞书返回的 `code`/`msg` 一律 `logger.warning/error` 记录（**`msg` 缺失时也显式记 `msg=None`**，不静默丢字段）；**授权码类错误（`AUTH_CODE_ERROR_CODES`，当前 = `{20003}`）额外附排障提示「(授权码一次性,通常为已使用或已过期)」**；用户信息失败文案为「飞书登录获取用户信息失败（飞书错误码 N）」。**日志与文案均不得包含 app_secret / access_token / 授权 code 原文**（测试已断言授权 code 不出现在日志中）。 |
| app_access_token 缓存 | 进程内缓存单条目（`_AppAccessTokenCache`，`threading.Lock`）：提前 300s（`APP_TOKEN_REFRESH_MARGIN_SECONDS`）视为过期并重新获取，飞书未返回 `expire` 时兜底 3600s；**上界**=应用级凭证仅一份故天然有界；多 worker/多实例各持一份，每进程首次登录各换一次，不影响正确性；获取失败不入缓存（下次重试）。 |

#### API-02：获取商家信息

```
GET /api/merchant/info
```

| 维度 | 内容 |
|------|------|
| 功能 | 商家登录后获取自己的基本信息 |
| 请求参数 | 无（从 JWT 提取 merchant_id） |
| 响应 | { merchant_id, nickname, avatar, merchant_name, current_stage, status } |
| 涉及表 | merchant（SELECT） |
| 权限校验 | 需要 JWT Token |
| 参数校验 | 无 |
| 异常情况 | ① Token 过期 → 401 "请重新登录" ② 商家不存在 → 404 "商家不存在" |
| 业务逻辑 | 根据 JWT 中的 merchant_id 查询 merchant 表 |

#### API-03：获取任务进度

```
GET /api/task/progress
```

| 维度 | 内容 |
|------|------|
| 功能 | 商家打开任务中心时，获取已完成任务与阶段二/数据专区解锁态 |
| 请求参数 | 无（从 JWT 提取 merchant_id） |
| 响应 | { completedTasks: string[], stage2_unlocked: boolean, data_center_unlocked: boolean, phase1_remaining_task_ids: string[] } |
| 涉及表 | merchant_task_progress（读已完成任务）、merchant（读 current_stage / data_center_unlocked） |
| 权限校验 | 需要 JWT Token |
| 参数校验 | 无 |
| 异常情况 | ① Token 过期 → 401 ② 商家被禁用 → 403 |
| V1 例外登记（#PB-26） | ⚠️ V1 未实现 · 例外登记（2026-09-15）· 移除条件=实现『禁用商家』功能时同步实现鉴权侧拦截（`app/api/deps.py::get_current_merchant`）并撤销测试侧 xfail 标记（`api-py/tests/test_merchant_status_guard.py`） |
| 业务逻辑 | ① completedTasks = 该商家 merchant_task_progress 中 status='completed' 的 taskId；② stage2_unlocked = current_stage='shop_setup'（含运营一键解锁）或阶段一启用任务全部完成；③ phase1_remaining_task_ids = 阶段一尚未完成的启用任务（status=1 且 default_completed≠1）；④ data_center_unlocked = merchant.data_center_unlocked=1（永久）或 listing 阶段启用任务全部完成 |
| 历史脉络 | V1 阶段任务定义在前端硬编码，后端只返回 merchant.current_stage；当前实现已由后端按 task 表返回已完成任务与解锁态（字段口径见「API-03/API-04 扩展」） |

#### API-04：更新任务进度

```
POST /api/task/progress
```

| 维度 | 内容 |
|------|------|
| 功能 | 商家完成/取消任务时，将进度同步到后端并派生解锁态 |
| 请求参数 | { taskId: string, status: 'pending' \| 'completed' } |
| 响应 | { success: true, stage2_unlocked: boolean, data_center_unlocked: boolean } |
| 涉及表 | second_level_task（校验任务启用态）、merchant_task_progress（写/更新进度）、merchant_stage_progress（解锁态落库）、merchant（UPDATE current_stage / data_center_unlocked） |
| 权限校验 | 需要 JWT Token；阶段二任务（brand/listing/optimize/activity）需阶段二已解锁，数据专区任务（shopdata）需数据专区已解锁，否则 403 |
| 参数校验 | ① taskId 不能为空 ② status 必须是 pending \| completed（否则 400） |
| 异常情况 | ① Token 过期 → 401 ② taskId 不存在 → 400 "任务不存在" ③ 任务已停用（status≠1）→ 400 ④ default_completed=1 的任务置为 pending → 400 ⑤ 商家被禁用 → 403 |
| V1 例外登记（#PB-26） | ⚠️ V1 未实现 · 例外登记（2026-09-15）· 移除条件=实现『禁用商家』功能时同步实现鉴权侧拦截（`app/api/deps.py::get_current_merchant`）并撤销测试侧 xfail 标记（`api-py/tests/test_merchant_status_guard.py`） |
| 业务逻辑 | ① 按 taskId 查 second_level_task 并校验启用态；② 按 stageId 判定阶段二/数据专区写权限；③ upsert merchant_task_progress（status / completedAt）；④ status='completed' 时落库数据专区解锁并幂等派生阶段二解锁（merchant.current_stage='shop_setup'，不回滚）；⑤ 同步 merchant_stage_progress |
| 幂等说明 | 重复提交同一 taskId 仅更新状态；阶段二解锁为单向（取消任务不回锁，运营一键解锁不被覆盖）；前端仍可用 localStorage 做即时响应，后端做异步同步 |

#### API-05：获取类目列表

```
GET /api/category/list
```

| 维度 | 内容 |
|------|------|
| 功能 | 前端类目选择器使用，返回一级类目和二级类目树 |
| 请求参数 | parent_id?: number（可选，筛选指定一级类目下的二级） |
| 响应 | [{ id, name, parent_id, children: [{ id, name }] }] |
| 涉及表 | category（SELECT） |
| 权限校验 | 需要 JWT Token |
| 参数校验 | parent_id 如果传了必须是正整数 |
| 异常情况 | 无特殊异常，空列表返回 [] |
| 业务逻辑 | 查 category 表，WHERE deleted_at IS NULL AND is_active=1，按 parent_id 分组 |
| 性能考虑 | 类目数据变更频率极低，直连 MySQL 查询即可（api-py 当前未使用 Redis，不做缓存层） |

#### API-06：获取资费信息

```
GET /api/fee/detail
```

| 维度 | 内容 |
|------|------|
| 功能 | 选择类目后查询对应资费，包含基础资费和品牌特殊资费 |
| 请求参数 | category_id: number（必填）, brand_name?: string（可选） |
| 响应 | { category_name, operation_rate, transaction_rate, deposit_gmv_lt_5w, deposit_gmv_5w_10w, deposit_gmv_10w_30w, deposit_gmv_gte_30w, is_brand_override: boolean } |
| 涉及表 | fee_config（SELECT）+ fee_brand_override（LEFT JOIN） |
| 权限校验 | 需要 JWT Token |
| 参数校验 | ① category_id 必填，正整数 ② brand_name 可选，字符串 |
| 异常情况 | ① category_id 不存在 → 404 "类目不存在" ② 该类目无资费配置 → 404 "暂无资费信息" |
| 业务逻辑 | 1. 先查 fee_brand_override 是否有该品牌覆盖 2. 如果有，用覆盖的费率 + 基础的保证金 3. 如果没有，用 fee_config 的基础数据 |
| 性能考虑 | 联合查询，数据量小（304条），无需缓存 |

#### API-07：保存商家经营类目

```
POST /api/merchant/category
```

| 维度 | 内容 |
|------|------|
| 功能 | 任务 T1.1.2 商家选择经营品类（1-3个）后保存 |
| 请求参数 | { categories: [{ category_id: number, is_primary: boolean }] } |
| 响应 | `{ success: true, count: number }`；**成功状态码 201**（装饰器 `status_code=201`，OpenAPI 声明与运行时一致，见 #PB-12 追加项） |
| 成功文案 | 保存成功后前端提示「**经营类目已保存**」——**本行即该文案的唯一真源**（后端只返回 `count`，不返回提示语；前端文案改动须先改本行） |
| 涉及表 | merchant_category（INSERT/DELETE） |
| 权限校验 | 需要 JWT Token |
| 参数校验 | ① categories 必填，数组 ② 数组长度 1-3（**先去重再判**）③ is_primary 只能有一个为 true ④ category_id 必须在 category 表中存在 |
| 异常情况 | ① 数量超出 1-3 个 → 400 "请选择1-3个类目" ② category_id 不存在 → 400 "类目不存在" ③ 重复选择 → 去重处理 ④ is_primary 多于一个 → 400 "只能选择一个主营类目" ⑤ 缺/空 categories → 400（共用①文案） |
| 业务逻辑 | 1. 删除该商家旧的 merchant_category 记录 2. 批量插入新记录 3. 记录事件到 event_log |
| 实现状态 | **已实现**（2026-09-10 / #PB-11）：`app/services/merchant_category.py` + `POST /api/merchant/category`（`app/api/v1/merchant.py`，POST 返回 201，响应 `{success,count}`）。补充口径：**先去重再判 1-3**（重复选择属"去重处理"，不因重复项误判超限）；多个 is_primary → 400「只能选择一个主营类目」；category 存在性按 `deleted_at IS NULL`；删除+插入+event_log **同一事务**提交（失败整体 rollback）；埋点 `event_type='category_select'`（取自前端 `src/utils/track.ts` 既有枚举，不新造类型）。 |

#### API-07（查询侧）：获取商家已保存经营类目

```
GET /api/merchant/category
```

| 维度 | 内容 |
|------|------|
| 功能 | 商家端 T1.1.2 回显此前保存的经营类目（面板刷新/重新进入时恢复选择态） |
| 请求参数 | 无（merchant_id 取自 JWT） |
| 响应 | `{ success: true, categories: [{ category_id: number, is_primary: boolean }] }`；**成功状态码 200**；无记录时 `categories: []`（`code:0`，非 404） |
| 涉及表 | merchant_category（SELECT） |
| 权限校验 | 商家 JWT Token（`get_current_merchant`）；无/无效 token → 401 |
| 排序 | `is_primary DESC, category_id ASC`（主营在前，其余按类目 id 稳定排序） |
| 类目名称 | **不在本接口返回**：名称唯一真源是 `category` 表，前端经 API-05 类目列表获取，避免同一事实出现两份可能漂移的副本 |
| 失败文案 | 无专属失败文案：401 用通用「未登录或 Token 已过期」，500 用通用「服务器内部错误」（见 §4.3） |
| 实现状态 | **已实现**（2026-09-11 / #PB-12）：`app/services/merchant_category.py::list_categories` + `GET /api/merchant/category`（`app/api/v1/merchant.py`）。 |

#### API-08：上报埋点事件

```
POST /api/event/report
```

| 维度 | 内容 |
|------|------|
| 功能 | 前端行为埋点上报（PV/UV、任务点击、完成等） |
| 请求参数 | { event_type: string, page_name?: string, task_key?: string, stage_key?: string, element?: string, meta?: object } |
| 响应 | { success: true } |
| 涉及表 | event_log（INSERT） |
| 权限校验 | 可选（未登录也可上报 PV） |
| 参数校验 | ① event_type 必填，必须在枚举范围内 ② meta 如果传了必须是合法 JSON |
| 异常情况 | ① event_type 不在枚举范围 → 400 "事件类型无效" ② 写入失败 → 200（埋点不影响主流程，静默失败） |
| 业务逻辑 | 直接 INSERT event_log 表，获取 IP 和 UA 从请求头中提取 |
| 性能考虑 | 高频写入场景，建议批量写入（每 5 秒一批）或异步队列 |

#### API-09：获取飞书顾问二维码

```
GET /api/feishu/advisor-qr
```

| 维度 | 内容 |
|------|------|
| 功能 | 任务 T1.3.8 "添加商家顾问催审" 中展示企微二维码 |
| 请求参数 | 无 |
| 响应 | { qr_url: string, talk: string } |
| 涉及表 | 无（V1 用静态配置） |
| 权限校验 | 需要 JWT Token |
| 参数校验 | 无 |
| 异常情况 | 本接口只返回 `qr_url`；**图片本身由下述静态端点提供**，图片未配置时该静态端点返回 404（本接口仍 200，前端需自行展示兜底） |
| 业务逻辑 | V1 返回固定配置（`qr_url = /api/static/advisor-qr.jpg` + 话术），V2 从数据库读取 |

#### API-09（静态资源）：商家顾问企微二维码图片

```
GET /api/static/advisor-qr.jpg
```

| 维度 | 内容 |
|------|------|
| 功能 | 提供商家顾问企微二维码图片本体（前端 `<img src>` 直接引用，见 `project/src/api/stage2.ts` / `project/src/pages/index/index.vue`） |
| 请求参数 | **无（路由不接受任何路径/查询参数）** |
| 响应 | 200 + 图片字节；`Content-Type` 按扩展名推断（`.jpg` → `image/jpeg`）；`Cache-Control: public, max-age=3600` |
| 权限校验 | **无需登录**（图片作为 `<img src>` 无法携带 Authorization；缺文件时返回 404 而非 401） |
| 文件路径 | 仅来自配置 `ADVISOR_QR_FILE`（默认 `static/advisor-qr.jpg`，**相对 api-py 根目录**）；**只服务这一个固定文件，禁止任何由请求决定的路径拼接**；配置解析为纯函数 `resolve_advisor_qr_path()`，越界（如 `../`）直接拒绝 |
| 异常情况 | ① 文件不存在 → **结构化 404**「顾问二维码未配置」；② 配置越界/非普通文件/不可读 → **结构化 500**「顾问二维码不可用」，**响应不回显绝对路径**（细节只进日志） |
| 实现位置 | `app/api/v1/static_assets.py`（唯一实现；**不挂目录静态服务**，避免目录穿越面） |
| 待办 | 仓库内**尚无真实二维码图片**（用户未提供）；部署时把企微二维码放到 `api-py/static/advisor-qr.jpg`（该目录已用 `.gitkeep` 占位，真实图片不入库） |

#### API-10：发送飞书通知（内部调用）

```
POST /api/feishu/send
```

| 维度 | 内容 |
|------|------|
| 功能 | 后端主动向商家推送飞书消息（定时任务触发） |
| 请求参数 | { merchant_id: string, template_type: string, extra?: object } |
| 响应 | { success: true, notification_id: number } |
| 涉及表 | merchant（SELECT feishu_user_id）+ feishu_notification（INSERT） |
| 权限校验 | 内部接口，仅后端定时任务调用，做 IP 白名单 |
| 参数校验 | ① merchant_id 必填 ② template_type 必须在枚举范围 |
| 异常情况 | ① 商家未绑定飞书 → 400 "商家未绑定飞书" ② 飞书 API 调用失败 → 502 + 记录 error_msg ③ 频率超限（2天1次）→ 跳过，不报错 |
| 业务逻辑 | 1. 查 merchant 获取 feishu_user_id 2. 检查 feishu_notification 表最近一次推送时间 3. 调飞书 API 发送卡片消息 4. INSERT feishu_notification 记录 |
| 频率控制 | 查 feishu_notification WHERE merchant_id=? AND template_type='task_reminder' ORDER BY sent_at DESC，如果距今 < 48h 则跳过 |
| 实现状态 | **服务层已实现**（2026-09-10 / #PB-11）：`app/services/feishu.py::send_notification`（频控 + 发送 + 落库，sender 可注入）；**HTTP 路由与自动触发点待定**——真源未定义触发点，本单不擅自加定时任务/后台 worker。 |
| 绑定列修正 | 本行原写「SELECT feishu_user_id」与实况不符：实测 `merchant.feishu_user_id` 全表**0 行非空**，登录链路（`services/auth.py`）只写 `feishu_open_id`，且 `_send_card` 的 receive_id_type 为 open_id → 实现改为取 **`feishu_open_id`**（§9.7 已登记）。 |
| 模板枚举 | `welcome` / `task_reminder` / `first_order_countdown` / `stage_complete`（措辞取自 §6.5 推送时机）+ `fee_sync` / `fee_sync_failed`（既有 `automation/src/notify.js` 在用，登记以免误拒）；标题即模板名，正文由调用方经 `extra.content` 提供（本服务不创作营销文案）。 |
| 失败语义 | 发送失败：落库 `status='failed'` + `error_msg`，服务层**不抛异常**（通知属降级面，见历史 SEC 结论），返回 `success=false`；HTTP 层接线时按本表契约映射 502。 |
| 欢迎卡片幂等标志 | `merchant.welcome_sent` 的语义 = **已成功发送**：仅当 `_send_card` 返回 `True` 时置 1；**发送失败不置位**（保持 0，返回 `{sent:false, first:true}`，下次登录可重试）；已为 1 时跳过且**不调用发送**（`{sent:false, first:false}`）。**#PB-19 修正**：此前无论成败都置 1，导致一次发送失败后该商家永远收不到欢迎卡片。 |
| 卡片发送（唯一发送实现） | 依赖 `lark-oapi >= 1.4`（实测 **1.7.3**）：`CreateMessageRequestBody.builder().receive_id(open_id).msg_type("interactive").content(卡片 JSON 字符串).build()` → `CreateMessageRequest.builder().receive_id_type("open_id").request_body(body).build()` → **`client.im.v1.message.create(request)`**（是 `im.v1.message`；SDK 上不存在 `im.message`，用错即 `'ImService' object has no attribute 'message'`）。成功判定 `resp.success()`（退化到 `code == 0`）；失败记飞书 `code`/`msg` 并返回 `False`，**不抛异常**。`welcome_on_first`（欢迎卡片）/`stage_complete`（阶段完成）/`send_notification`（API-10）**共用** `app/services/feishu.py::_send_card`，无第二套发送路径。 |

#### API-11：获取埋点统计数据（管理端）

```
GET /api/event/stats
```

| 维度 | 内容 |
|------|------|
| 功能 | 管理后台查看 PV/UV、任务完成率、飞书打开率等 |
| 请求参数 | start_date: string, end_date: string, event_type?: string, group_by?: 'day' \| 'week' |
| 响应 | [{ date, count, unique_count }] |
| 涉及表 | event_log（SELECT + GROUP BY） |
| 权限校验 | 需要管理员 JWT（与商家 Token 区分角色） |
| 参数校验 | ① 日期格式 YYYY-MM-DD ② 日期范围不超过 90 天 |
| 异常情况 | ① 日期范围超 90 天 → 400 "查询范围不能超过90天" |
| 性能考虑 | event_log 按月分区，查询走 idx_created_at 索引 |

#### API-17：管理端商家与任务进度（`/admin/merchant` 一族）

> 2026-09-14 / #PB-22 补齐登记：该族接口自 NestJS 时代即在管理后台「商家管理」页使用，但本文档此前 **0 命中**，形成「无明确契约 + 两侧各自假设」——前端无参调用 `GET /progress`，后端却把 `merchantId` 写成必填，页面列表恒空（§9.7）。

```
GET  /api/admin/merchant                          # 商家主表列表（分页 + 关键词检索）
GET  /api/admin/merchant/progress                 # 商家任务进度（merchantId 可选；不传 = 全部商家）
GET  /api/admin/merchant/progress/{merchantId}    # 指定商家进度
POST /api/admin/merchant/{id}/unlock-phase1       # 阶段一解锁（幂等永久；:id 即 merchantId）
```

| 维度 | 内容 |
|------|------|
| 功能 | 管理后台「商家管理」页：商家列表 + 任务进度聚合，并支持运营一键解锁阶段一 |
| 请求参数 | `GET /merchant`：`keyword?`、**`stage?`（阶段精确筛选）**、**`status?`（状态精确筛选）**、`page?`（默认 1）、`page_size?`（默认 20）；`GET /merchant/progress`：**`merchantId?` 可选——不传或传空 = 全部商家**，传入 = 仅该商家；`GET /merchant/progress/{merchantId}`：路径参数必填；`POST /merchant/{id}/unlock-phase1`：路径参数 `id`（= merchantId）必填 |
| 关键词检索口径（#PB-29，2026-09-15） | `keyword` 对 `merchant_id` / `nickname` / `jd_merchant_id` / `shop_name` **4 字段做 OR 模糊包含匹配**（`LIKE '%kw%'`）：完整商家ID、京麦商家ID、店铺名片段、昵称片段均可命中；后两列可为 NULL，NULL 既不误命中也不报错；`page_size` 上界 100、`deleted_at IS NULL`、`created_at` 倒序等既有行为不变。**未新增索引**（EXPLAIN 实测 `type=ref` 走 `idx_deleted_at`，`LIKE '%…%'` 前置通配本就用不上索引，当前表量级无需加；若将来要前缀匹配/大表优化，另立需求与 DDL 单） |
| 阶段/状态筛选口径（#PB-24，2026-09-16） | `stage` 精确匹配 `merchant.current_stage`、`status` 精确匹配 `merchant.status`，**只接受已登记取值**：`stage ∈ {onboarding, shop_setup}`（入驻准备 / 开店搭建）、`status ∈ {0, 1, 2}`（0 禁用 / 1 正常 / 2 已退出）；传其它值 → **400**，文案复用统一校验出口 `app/core/error_handlers.py::VALIDATION_MESSAGE`「提交的内容有误，请检查后重试」（**不回显取值原文**；取值与已登记集合只进日志，与「校验明细只进日志」同一口径）；**空串 / 纯空白 = 不筛选**（前端「全部」选项常提交空串）；`stage` + `status` + `keyword` 与分页、`deleted_at IS NULL`、`created_at` 倒序 **全部 AND 组合**，`total` 为筛选后的行数；响应结构与 **9 字段投影**（**#PB-25 起含 `status`**：0 禁用 / 1 正常 / 2 已退出；仍**不含 `phone`**）。实现：`app/services/merchant.py::list_all`（取值校验唯一 owner）+ `REGISTERED_STAGES` / `REGISTERED_STATUSES` |
| 响应 | 进度行 `[{ id, merchantId, taskId, status, completedAt, createdAt, updatedAt }]`；解锁 `{ success: true, stage2_unlocked: true }` 且 HTTP **201**；主表列表 = `{ list: [{ merchant_id, nickname, merchant_name, current_stage, status, jd_merchant_id, shop_name, last_login_at, created_at }], total, page, page_size }`（**9 字段投影**，#PB-24 补登记、**#PB-25 补 `status`**；`created_at` 倒序） |
| 权限校验 | 读接口（前三个）= **需登录**（`Depends(get_current_admin)`，`viewer` 亦可读；依据 `任务管理后台开发标准` §6 该行 + §7.2「商家/任务/埋点等平台数据登录管理员均可读」）；解锁 = `Depends(require_roles("super_admin", "admin"))`，`viewer` → 403「无权限执行该操作」；未带/无效 token → 401 |
| 取数落层 | 全部行 = `app/services/task_progress.py::list_all`；单商家 = 同文件 `find_by_merchant`；解锁 = `unlock_phase1`（**路由不拼业务查询**，只做参数提取与投影） |
| 排序口径 | 「全部」固定 `merchantId, taskId` 升序（前端按 `merchantId` 聚合，顺序须可复现、可对账）；「单商家」沿用 `createdAt` 降序（既有口径不变，两者返回行集相同） |
| 全部查询上界 | `MAX_PROGRESS_ROWS = 5000`（模块常量，**不静默截断**）：取到 `上界+1` 行即返回 **400「结果过多，请按商家查询」**（结构化错误、`data:null`）。阈值依据：实测现状 126 行 / 5 商家（单商家最多 43 行）、启用二级任务 49 个 → 单商家最坏约 50 行，5000 行 ≈ 100 个满量商家（约 200 个当前均量商家），约 40× 余量；行体积约 200B → 上限响应约 1MB。超限后逃生通道 = 按 `merchantId` 查询（单商家查询无上界） |
| 异常情况 | 解锁时商家不存在 → 404「该商家不存在」；`merchantId` **不再必填**（#PB-22 之前缺失即 400「请求参数不合法：字段 merchantId」） |
| 实现位置 | `app/api/v1/admin_merchant.py`（路由）、`app/services/task_progress.py`（服务层） |

#### API-18：管理端 AI 分入口配置（AI 配置一族）

> 2026-09-14 / #P-9 登记（实现：#DB-12 建表 + #PB-21 服务层/接口/轮换脚本 + #AF-14 后台页；方案 `dev-docs/任务单/P7-AI-key分入口配置-方案.md` v1.2）。**仅 super_admin**：非 super_admin 完全不可见（管理端菜单 + 路由守卫 + 后端 403 三层，**后端 403 是唯一可信边界**）。

```
GET  /api/admin/ai-config/list            # 三入口配置总览
PUT  /api/admin/ai-config/{entry}         # 部分更新某入口配置
POST /api/admin/ai-config/{entry}/verify  # 用当前生效配置做连通性自检（不落库）
```

| 维度 | 内容 |
|------|------|
| 功能 | 管理后台维护 AI 三入口（`analysis` / `image_optimize` / `title_optimize`）各自的 `api_key / base_url / model / timeout_ms / max_tokens / daily_limit / enabled`；字段级优先级 = **DB 有值覆盖 env、NULL 回落 env** |
| 请求参数（PUT） | Pydantic `AiConfigPatchBody`：`api_key`(≤256) / `base_url`(≤255，pattern `^https?://`) / `model`(≤128) / `timeout_ms`(1000–600000) / `max_tokens`(1–32000) / `daily_limit`(0–100) / `enabled`(bool)。**字段省略 = 不修改**（`model_dump(exclude_unset=True)`） |
| 响应 | 单入口投影与 `GET list` 元素同形：`entry / enabled / apiKeySet / apiKeyMasked / apiKeyFingerprint / apiKeyStatus / baseUrl / model / timeoutMs / maxTokens / dailyLimit / effectiveSource{apiKey,baseUrl,model,timeoutMs,maxTokens,dailyLimit} / updatedBy / updatedAt` |
| 响应脱敏（硬口径） | **任何响应都不得返回密钥原文、密文、长度或 `AI_CONFIG_ENC_KEY` 任何形态（含其 hash）**；只回掩码（长度 ≥12 → 前 3 + `****` + 后 4，否则 `****`）、指纹（`sha256(原文)` 前 16 位 hex）与状态 |
| ```apiKeyStatus``` 枚举 | `ok`（库内存在**且可解密**的密钥）/ `decrypt_failed`（库内有密文但解不开，此时已回落 env）/ `none`（无密文行） |
| 权限校验 | 三端点均为 `Depends(require_roles("super_admin"))`；`admin` / `viewer` → **403**「无权限执行该操作」；未带/无效 token → **401** |
| 写入语义 | 省略 = 不修改；显式 `null` = 清除并回落 env（审计 `action=clear`）；**空串 = 400**；`api_key` 长度 8–256，掩码形态（`^.{0,8}\*{4}.{0,8}$`）或等于当前指纹 → **400**；`base_url` 空串由 Pydantic pattern 拦下（400，文案与 service 层空串文案不同） |
| 事务与审计 | 每个**变更字段**写一行 `admin_ai_config_audit`，与业务变更**同一事务**；未变更字段不写；审计只留掩码/长度/指纹，**绝不落密钥原文与密文** |
| ```/verify``` | 失败恒 **502**，message 尾附「（错误码 X）」；请求 `max_tokens=1`，超时 `min(cfg.timeout_ms, 15000)`（管理端等待上界）；**`max_tokens=1` 时的空响应视为连通成功**（部分供应商会返回空内容）；不落库 |
| 实现位置 | `app/api/v1/admin_ai_config.py`（路由）、`app/services/ai_config.py`（解析/合并/写入/审计）、`app/services/ai_crypto.py`（AES-256-GCM 封装）、`app/services/ai.py::verify_connection` |
| 测试 | `api-py/tests/test_admin_ai_config.py` |

**行为口径（#PB-21 待回写差异 10 条，逐条落点）**

| # | 口径 | 代码落点 |
|---|------|---------|
| 1 | `apiKeySet` / `apiKeyMasked` 语义 = 「库内存在**且可解密**的密钥」，**不等于当前生效密钥**（生效密钥可能来自 env 回落）；解密失败时 `apiKeySet=false`、`apiKeyMasked=null`、`apiKeyStatus='decrypt_failed'` | `app/services/ai_config.py:199-206` |
| 2 | 审计 `old_len` 由**密文长度**推导，不解密、不接触原文 | `app/services/ai_crypto.py:126-139`；`ai_config.py:333,352` |
| 3 | 旧密文不可解时，审计 `old_display` 回落为 `\"****\"` | `app/services/ai_config.py:358-366` |
| 4 | `/verify` 失败**恒 502**，message 尾附「（错误码 X）」 | `app/api/v1/admin_ai_config.py:63-65` |
| 5 | `/verify` 把 `max_tokens=1` 的空响应（`LLM_EMPTY_RESPONSE`）视为**连通成功**，不误报 | `app/services/ai.py:155-159` |
| 6 | `/verify` 超时上界固定 `min(cfg.timeout_ms, VERIFY_TIMEOUT_CEILING_MS=15000)` | `app/services/ai.py:139,145,153` |
| 7 | `base_url` 格式在 **Pydantic 层**约束（`^https?://`，空串走校验文案）；与 service 层「空串 400」文案不同 | `app/api/v1/admin_ai_config.py:27` vs `app/services/ai_config.py:268-269` |
| 8 | 空 patch（无字段）= no-op：**不产生审计行**；实现仍会 `commit`（若原无行会插入空行）并在 `finally` **无条件失效缓存** | `app/services/ai_config.py:290-316` |
| 9 | `analysis` 入口 `max_tokens` 默认 **4096**（env 无该项，历史硬编码值）；`daily_limit=0` = 不限 | `app/services/ai_config.py:34-35,149-152`；`app/services/ai.py:176` |
| 10 | 审计 `old/new_display` 对 `base_url` 做 userinfo 掩码（`scheme://user:pass@host` → `scheme://****@host`），不落凭据 | `app/services/ai_config.py:230-245` |

#### API-19：管理端既有端点族补登记（auth / account / stage / group / task / feedback）

> 2026-09-14 / #P-9 登记。这些端点自 NestJS 时代即在管理后台使用、api-py `app/api/router.py` 已注册，但本文档此前**未登记**（形成「有实现、无契约」）。**用户裁决（2026-09-14）：只登记、不删任何路由与页面**（背景：管理后台「阶段管理」页面不可达，用户选择「C —— 只登记，不删任何东西」，因为无法确认这些写接口是否仍有调用方）。「前端实际调用」列给出调用点证据（文件:行）。

| 端点族 | 方法 | 用途 | 角色要求 | 前端实际调用（调用点） |
|--------|------|------|---------|----------------------|
| `/api/admin/auth/login` | POST | 管理员登录 | 公开 | ✅ `admin/src/store/modules/auth.ts:13` |
| `/api/admin/auth/profile` | GET | 当前管理员信息 | 需登录 | ✅ `store/modules/auth.ts:33`、`pages/profile/index.vue:53` |
| `/api/admin/auth/change-password` | POST | 修改本人密码 | 需登录 | ✅ `pages/profile/index.vue:54` |
| `/api/admin/account/list` | GET | 管理员列表 | 需登录 | ✅ `pages/account/index.vue:162`、`pages/dashboard/index.vue:67` |
| `/api/admin/account/{id}` | GET | 管理员详情 | 需登录 | ✅ 已封装 `admin/src/api/account.ts:57` |
| `/api/admin/account/create` | POST | 创建管理员 | super_admin | ✅ `pages/account/index.vue:162`（`api/account.ts:62`） |
| `/api/admin/account/{id}` | PUT | 更新管理员 | super_admin | ✅ 同上（`api/account.ts:67`） |
| `/api/admin/account/{id}` | DELETE | 删除管理员 | super_admin | ✅ 同上（`api/account.ts:72`） |
| `/api/admin/account/{id}/reset-password` | POST | 重置密码 | super_admin | ✅ 同上（`api/account.ts:77`） |
| `/api/admin/account/generate` | POST | 生成管理员账号 | super_admin | ✅ 同上（`api/account.ts:82`） |
| `/api/admin/stage/list` | GET | 阶段列表（读**存活表** `stage_config`） | 需登录 | ✅ `api/stage.ts:29`；`store/modules/stage.ts:15` → `pages/first-level-task/index.vue:149,160`、`pages/second-level-task/edit.vue:127,134`；`pages/dashboard/index.vue:64` |
| `/api/admin/stage/{id}` | GET | 阶段详情 | 需登录 | ✅ 已封装 `api/stage.ts:34` |
| `/api/admin/stage/create` | POST | 创建阶段 | admin / super_admin | ⚠️ 已封装 `api/stage.ts:39` + store action `store/modules/stage.ts:27`，**当前无页面调用**（阶段管理页面不可达） |
| `/api/admin/stage/{id}` | PUT | 更新阶段 | admin / super_admin | ⚠️ 同上（`api/stage.ts:44`、`store/modules/stage.ts:37`） |
| `/api/admin/stage/{id}` | DELETE | 删除阶段 | admin / super_admin | ⚠️ 同上（`api/stage.ts:49`、`store/modules/stage.ts:49`） |
| `/api/admin/group/…`（list / create / {id} GET·PUT·DELETE） | GET/POST/PUT/DELETE | 一级任务配置 | 读 = 需登录；写 = admin / super_admin | ✅ `api/first-level-task.ts:28-48`；`store/modules/task.ts:18,30,42,54`；`pages/first-level-task/index.vue:148,159`、`pages/dashboard/index.vue:65` |
| `/api/admin/task/…`（list / create / {id} GET·PUT·DELETE） | GET/POST/PUT/DELETE | 二级任务配置（**#PB-39 起请求/响应含 `actionType`/`actionParam`**，枚举与参数规则见 §8.3.9） | 读 = 需登录；写 = admin / super_admin | ✅ `api/second-level-task.ts:44-64`；`store/modules/task.ts:67,79,91,103`；`pages/second-level-task/index.vue:74`、`edit.vue:126,128`、`pages/dashboard/index.vue:66` |
| `/api/admin/feedback` | GET | 反馈列表（状态/分类/日期筛选） | admin / super_admin | ✅ `pages/feedback/index.vue:104`（`api/feedback.ts:41`） |
| `/api/admin/feedback/{id}` | PATCH | 处理反馈（status + admin_reply） | admin / super_admin | ✅ 同上（`api/feedback.ts:46`） |

> 纪律：上表 ⚠️ 行（`stage` 写接口）**不得因「页面当前不可达」而删除路由或封装**——是否仍有调用方未经确认，按用户裁决保持现状；后续若确认无调用方，再走独立评估单。

#### API-20：商家登记信息（商家端；#PB-23 契约变更 + 补登记）

> 2026-09-14 / #PB-23：`PUT /api/merchant/registration` 由「只存档不校验」改为**带格式校验**（用户要求：京麦商家ID 仅数字、店铺名称 仅汉字）。该端点自 NestJS 时代即有实现、`project/src/api/merchant.ts` 在用，但本文档此前**未登记**（有实现、无契约），本单顺带补齐（§9.7）。

```
PUT /api/merchant/registration    # 保存登记（幂等覆盖 + 格式校验）
GET /api/merchant/registration    # 查询已登记值（进入引导弹窗前预填）
```

| 维度 | 内容 |
|------|------|
| 功能 | 阶段二进入前引导弹窗「京麦商家ID / 店铺名称」的保存与预填 |
| 请求参数 | `{ jd_merchant_id?: string 或 null, shop_name?: string 或 null }`；字段**缺省 = 不更新**（非「置空」） |
| 响应 | 保存 `{ success: true }`；查询 `{ jd_merchant_id, shop_name }`（未登记为 `null`） |
| 涉及表 | merchant（`jd_merchant_id VARCHAR(64)` / `shop_name VARCHAR(128)`，字段已存在，**无 DDL**） |
| 权限校验 | 商家 JWT（`get_current_merchant`）；无/无效 token → 401 |
| 格式校验（服务端边界；唯一 owner = `app/services/merchant.py::_normalize_registration`，路由不重复校验） | ① `jd_merchant_id`：**仅数字** `^[0-9]+$`（ASCII 半角；空格/字母/汉字/符号/全角数字一律拒绝）；② `shop_name`：**仅汉字** `^[\u4e00-\u9fa5]+$`（CJK 基本区；数字/字母/空格/符号拒绝）；③ 长度上界由 DTO 承载（`Field(max_length=64)` / `(max_length=128)`，与列一致），超长在进入服务层前即被拦；④ `null` **与空串同义 = 清空**（回落「未登记」），**必须放行** |
| 失败文案（接口级真源） | ① 字符集非法 → **400**「京麦商家ID仅支持数字」/「店铺名称仅支持汉字」（与前端本地文案 `project/src/constants/merchant.ts:25,28` 同措辞）；② 超长 → **400**「提交的内容有误，请检查后重试」（§4.3.1 通用句，**不回显字段名**；#PB-24-1-R1 起）。两者信封均为 `{code: 400, message, data: null}`，**均不回显用户输入原文** |
| 唯一性校验（**#PB-36 扩展**；落点 `app/services/merchant.py::save_registration`，判据 `app/services/merchant_binding.py::jd_merchant_id_is_taken`） | 触发条件：请求体**显式带** `jd_merchant_id`（`model_fields_set`）且值非空、且与本账号当前值**不同**（同值重提交 = 幂等，不触发）。命中任一判据 → **400「该商家已被登记」**，**写入不发生**（本账号原值保持）、**不回显占用方账号**。判据与通知见下方子块 |
| 业务逻辑 | 缺省字段不动；`null` / 空串写 `NULL`（清空）；合法字符串覆盖写；**幂等**（重复提交同值无副作用） |
| 空串口径（决策依据） | 空串按「清空」放行：前端**总是同时提交两个字段**（`project/src/pages/stage2/index.vue:556`），未填的那个是 `""`，而 `project/src/utils/validate.ts:23,26` 的前端校验把空值视为合法；若后端把空串判非法，「只填一项」的保存路径会 400（回归）。传 `null` 同样放行 |
| 已知边界 | `^[\u4e00-\u9fa5]+$` 不含扩展区生僻字（U+20000 段等）与全角数字——按用户裁决实现，未擅自放宽；如需放宽须走契约变更。前端输入层拦截与本地 toast 归 `#F-25`（已落地：`project/src/utils/validate.ts`、`project/src/constants/merchant.ts:25,28`、`project/src/pages/stage2/index.vue:520-552`；残留「不做校验/仅存档」注释仍待其收敛：`project/src/api/merchant.ts:2,19`、`project/src/pages/stage2/index.vue:218,536`） |
| 实现位置 | `app/api/v1/merchant.py`（路由）、`app/services/merchant.py`（`save_registration` / `_normalize_registration`）、用例 `tests/test_merchant_registration_validation.py` |

**重复登记拒绝与内部通知（#PB-36 / 方案 §5.1 + §5.3；API-20 扩展）**

| 项 | 口径 |
|----|------|
| 占用判据 ① | 别的**不在本账号所在组内**的未软删账号已登记同值（`merchant.deleted_at IS NULL`） |
| 占用判据 ② | 该值已有**活跃绑定组**（`merchant_binding_group.active_key = 1`），且**不是自己所在的组**（自己已被运营绑到该 ID 时允许登记同值） |
| ① 为何也排除同组账号 | 组键取自「发起绑定的那个商家的登记值」；若不排除，**组内非发起方永远无法登记本店 ID**（与 API-22 用例 18「组内登记同值允许」直接冲突） |
| 内部通知（新事件） | `event_type = jd_duplicate_registration`，写 `internal_notify_log`（`dedupe_key = "jd:<jd_merchant_id>"`）；正文四要素：申请账号（merchant_id）/ 手机号（`app/core/utils.py::mask_phone`）/ **申请商家ID（部分脱敏：保前 4 后 4，长度 < 8 时全 `****`；`mask_jd_merchant_id`）**/ 时间 |
| 幂等 / 频控 | **24h 去重窗口**：同一 `dedupe_key` 已有 `status=sent` 行 → 只 `logger.warning`，**不写行、不发送**；不同 ID 各自计数；**同一 ID 24h 内最多一条 sent 通知** |
| 发送时机 | **先返回 400、再异步发送**：通知由失败响应携带的 `BackgroundTasks` 执行。FastAPI 注入的 `BackgroundTasks` **只在正常返回时执行**（异常路径实测不执行），故由 `ApiException.background` 承载、统一错误出口 `app/core/error_handlers.py` 挂到失败响应上。通知内部任何异常只落 `status=failed` + `logger.warning`，**绝不改变 400 的返回** |
| 事件名长度约束 | `internal_notify_log.event_type` 为 **VARCHAR(32)** 且库开 `STRICT_TRANS_TABLES`；方案稿拟的 `merchant_id_duplicate_registration`（34 字符）**实测写入报 1406 Data too long**，故取语义等价的短名（方案 §4.2 明确「DDL 以 database 单落地为准」） |
| 实现位置 | `app/services/merchant.py::save_registration`（落点/文案）、`merchant_binding.py::jd_merchant_id_is_taken`（判据）、`internal_notify.py::notify_duplicate_registration`（通知）；用例 `tests/test_merchant_binding.py` 用例 18/19/20 |

#### API-21：手机号 + 短信验证码登录（商家端；#PB-23 / 方案 `dev-docs/任务单/phone-sms-login-design.md`）

> **编号说明**：总控任务单写的「API-20」**已被占用**（下方 §5.2 已有 `#### API-20：商家登记信息`），故本单登记为 **API-21**（已在 #PB-23 汇报中说明）。
> 口径要点：验证码**由阿里云号码认证（PNVS）生成与校验**，我方不接触明文（`ReturnVerifyCode=false`）；登录即注册（任意手机号）；防枚举（新老号码响应逐字段一致）。

```
POST /api/auth/phone/send-code   # 发送登录验证码（公开）
POST /api/auth/phone/login       # 验证码登录 / 自注册（公开）
```

| 维度 | 内容 |
|------|------|
| 请求体（send-code） | `{ phone: string(≤20), captcha_verify_param?: string(≤4096) }`——人机校验串是**不透明字符串，原样透传**给接缝 |
| 请求体（login） | `{ phone: string(≤20), code: string(≤10) }` |
| 响应（send-code，**200**） | `{ sent: true, cooldown_seconds, expires_in_seconds, code_length }`（取自 `LOGIN_CODE_COOLDOWN_SECONDS` / `LOGIN_CODE_TTL_MINUTES×60` / `LOGIN_CODE_LENGTH`）；**不含任何账号存在性信息** |
| 响应（login，**201**） | `{ token, merchant: { merchant_id, nickname, avatar, merchant_name, current_stage, status }, is_new_merchant }` |
| 涉及表 | merchant（SELECT/INSERT/UPDATE）、merchant_login_code（INSERT/UPDATE）、captcha_daily_counter（原子自增）、internal_notify_log（INSERT） |
| 鉴权 | 公开（无需 token），与既有 `/api/auth/*` 一致 |
| 专句（服务层 owner） | 手机号不满足 `^1[3-9]\d{9}$` → **400「手机号格式不正确」**（`app/services/phone_auth.py::PHONE_INVALID_MESSAGE`，见 §4.3.1 专句机制）；人机校验未通过 → **400「请先完成安全验证」**（`app/services/captcha.py::CAPTCHA_REQUIRED_MESSAGE`） |
| 人机校验（**单一接缝**；**官方《图形认证服务端集成》口径，#PB-23-R2**） | `app/services/captcha.py::verify_captcha_or_raise(captcha_verify_param, client_ip)`，调用点只有一处。请求 `POST {CAPTCHA_API_SERVER}/validate?captcha_id={CAPTCHA_APP_ID}`，**请求体必须是 `application/x-www-form-urlencoded`**（httpx `data=`；格式不对会报 `illegal gen_time`），参数 `lot_number`/`captcha_output`/`pass_token`/`gen_time`/`sign_token`；`sign_token = HMAC-SHA256(key=CAPTCHA_APP_KEY, message=lot_number)` 的 hexdigest；`captcha_id` **一律取服务端配置**（忽略前端回传值，防篡改）；**判定：仅 `status` 为 `success` 且 `result` 为 `success` 才通过**。**fail-closed（与官方 demo 的关键差异）**：HTTP 非 200 / 超时（`CAPTCHA_TIMEOUT_MS` 默认 3000ms）/ 连接异常 / 非 JSON 响应 / `status` 为 `error`（如 `-50005 illegal gen_time`）/ `result` 非 `success` → **一律 400「请先完成安全验证」，绝不发码、绝不降级放行**（官方 demo 异常时默认 `result=success` 属 fail-open，**不照抄**）；未配置 `CAPTCHA_APP_ID`/`CAPTCHA_APP_KEY`、参数缺失或格式非法时**不发起外部请求**；日志只记 `status`/`result`/`reason`/`code`/`msg` 与客户端 IP，**不回显 `captcha_verify_param` 原文与 appKey**。**凭证缺失单列 503 出口（#PB-23-R3）**：`_reject_not_configured()` → **503「登录服务暂不可用，请稍后重试或联系管理员」**（与 §4.3 第②条、`FEISHU_LOGIN_UNAVAILABLE_MESSAGE` 同句）+ `logger.error`（写明缺 `CAPTCHA_APP_ID` 还是 `CAPTCHA_APP_KEY`）——服务侧配置故障不伪装成「用户没做验证」（其余 fail-closed 分支仍为 400「请先完成安全验证」）。<br>服务端错误码（登记备查）：`-50000` runtime / `-50001` illegal risk_type / `-50002` param decrypt / `-50003` illegal verify（重复验证）/ `-50004` jsonp xss / **`-50005` illegal gen_time（传参格式问题）** / `-50101` not captcha_id / `-50102` illegal captcha_id / `-50103` not captcha / `-50104` captcha_id deleted / `-50105` captcha_id paused / `-50301`~`-50308`（流水号与 payload 相关） |
| 短信下发（**唯一出口**） | `app/services/sms_verify.py::send_verify_code` → `SendSmsVerifyCode`（**接入点 `ALIYUN_SMS_ENDPOINT=dypnsapi.aliyuncs.com`**，PNVS 专用；配成 `dysmsapi` 会 `InvalidAction.NotFound` → 502，#PB-23-R4 真机根因；SDK 异常必须落 `code`/`message`/`request_id` 便于排障）：`SignName=ALIYUN_SMS_SIGN_NAME`（`恒创联众科技`）、`TemplateCode=ALIYUN_SMS_TEMPLATE_CODE`（`100001`）、`CodeLength=LOGIN_CODE_LENGTH`、`CodeType=1`、`CountryCode=86`、`ValidTime=LOGIN_CODE_TTL_MINUTES×60`、`Interval=LOGIN_CODE_COOLDOWN_SECONDS`、`DuplicatePolicy=1`、**`ReturnVerifyCode=false`**（**验证码由阿里云生成，我方不接收/不落库/不打印**）；判据 `Code=="OK" and Success is True`，取 `Model.BizId` 落库；失败 → **502「短信服务暂不可用，请稍后重试」**（不含供应商名/错误码/环境变量名） |
| 验证码校验（**唯一出口**） | `app/services/sms_verify.py::check_verify_code` → `CheckSmsVerifyCode(PhoneNumber, VerifyCode, OutId)`：**仅 `VerifyResult` 为 `PASS` 才放行**；`UNKNOWN` → 400「验证码不正确或已过期」；供应商异常/未配置 → 502（**绝不放行**）；通过后该行置 `used_at`（一次性）。<br>**业务级「未通过」例外（实测口径，#PB-23-R4）**：输错码时 SDK 以 `ClientException(code=isv.ValidateFail, message="code: 400, 验证失败")` **抛出**（不是返回 `verify_result=UNKNOWN`）→ 该码映射为**「未通过」(`return False`)**，由上层计一次错次并返回 400 三态文案；**不得**当 502（否则用户看到「短信服务暂不可用」且 C8/C10 错次上限永不触发 ⇒ 防爆破失效）。其余错误码仍 502 |
| 频控矩阵 C1~C10（全部落库计数，无 Redis） | C1 同号冷却 60s → **429**「发送过于频繁，请在 N 秒后重试」（N∈[1,60]）；C2 同号 5/时 → 429（同上，N∈[1,3600]）；C3 同号 10/日 → **429**「今日发送次数已达上限，请明天再试」；C4 IP 20/时、C5 IP 60/日 → **429**「发送过于频繁，请稍后再试」（不带 N）；C6 全局 1000/日 → **503**「当前发送量已达上限，请稍后再试」（80% `logger.warning`、达上限 `logger.error`）；C7 人机校验成本闸 3000/日（`captcha_daily_counter` 用 `INSERT … ON DUPLICATE KEY UPDATE used = used + 1` **原子自增，在调用之前判定**，达上限 → 503 且**不调用**人机校验）；C8 单行失败次数达 `LOGIN_CODE_MAX_ATTEMPTS`（5）→ 该行 `used_at` 作废 + **429**「验证尝试次数过多，请重新获取验证码」；C9 有效期由阿里云 `ValidTime`（= `LOGIN_CODE_TTL_MINUTES`）承担；C10 同号 15 分钟内失败累计达 `LOGIN_CODE_VERIFY_WINDOW_MAX`（10）→ 429。<br>**口径说明**：C1~C6 的**被拒请求不写行**（拒绝不会延后窗口）；C10 的计数载体是窗口内 `SUM(attempts)`（`attempts` 仅在校验未通过时 +1）——当前表无独立「校验请求日志」，此为本单落地口径 |
| 处理顺序 | 参数 → 本地频控 C1~C6 → C7 成本闸 → 人机校验接缝 → 阿里云下发 + 落行（**本地闸在前**：被频控拦下时不调用人机校验、不消耗短信） |
| 自注册口径 | 无商家行 → INSERT `merchant`（`merchant_id = "p_" + 32 hex 随机`，G-1 不用手机号；`status=1`、`current_stage="onboarding"`、`nickname=脱敏手机号`）；命中 `uk_phone` 冲突（含**软删行仍占位**，G-3）→ **400「该手机号不可用，请联系平台」** |
| 登录入口状态拦截 | 已有商家 `status != 1` → **403「账号已被禁用，请联系平台」**（G-2：只拦登录入口；鉴权侧沿用 §6.1 的 V1 例外，不扩围） |
| 内部通知（旁路，独立通道） | 新商家注册 → `BackgroundTasks` 调 `app/services/internal_notify.py::notify_merchant_registered`（飞书 IM `im.v1.message.create`，`receive_id_type=open_id`，接收人 `INTERNAL_NOTIFY_RECEIVE_ID`）；**注册事务先 commit**，发送/落库任何异常都**不影响 201**；`internal_notify_log` 记 `sent/failed`；以 `(event_type="merchant_registered", merchant_id)` 保证**同一商家只通知一次**；正文只含**脱敏手机号** + merchant_id + 时间（**不含 token/密钥/完整手机号**）。**接收人 `INTERNAL_NOTIFY_RECEIVE_ID` 只由 `.env`/环境变量注入(源码默认空串,不硬编码 PII,#PB-37 A)**:留空 = 未配置 → 通知**显式跳过** + `logger.info`(`_notify_skip_reason`),不写行、不发送、不拒启动、不影响业务返回 |
| 实现位置 | `app/api/v1/auth.py`（路由）、`app/services/phone_auth.py`（业务规则/频控/文案单一真源）、`app/services/sms_verify.py`（PNVS 适配，唯一短信出口）、`app/services/captcha.py`（人机校验接缝）、`app/services/internal_notify.py`（内部 IM 通知）；用例 `api-py/tests/test_phone_login.py`（34 例） |
| 测试口径（硬性） | `SendSmsVerifyCode` / `CheckSmsVerifyCode` / **图形认证二次校验 HTTP（`captcha.httpx.post`）** / IM 发送**全部打桩**：测试不发真实短信、不调用任何云产品（内部 IM 通道默认被打桩，任何用例都不得打真实飞书）；用例另断言二次校验请求**是 form-urlencoded 而非 JSON**、URL 带服务端配置的 `captcha_id`、`sign_token` 与独立计算的 HMAC-SHA256 向量逐字符一致 |

#### API-22：管理端账号绑定（`/admin/merchant/{merchantId}/bindings` 一族；#PB-36 / 方案 `dev-docs/任务单/merchant-account-binding-design.md`）

> **产品语义**：同一京麦商家主体在平台有多个账号时，由**运营手工绑定**连成一个「店」，**只共享进度**（阶段 / 任务完成状态）；账号级标记（新手引导、欢迎消息、`merchant.data_center_unlocked` 持久化标记）**不共享**。用户已拍板 5 条：① 只共享进度；② 管理后台手工绑定（不做商家自助、不做邀请码）；③ 组内成员**权限等同（无主账号）**；④ 支持解绑；⑤ 登记时 `jd_merchant_id` 已被别的账号登记/绑定 → 拒绝 + 内部通知（见 API-20 扩展）。
> **数据模型**：`merchant_binding_group` + `merchant_binding_member`（§8.3.8；schema v1.10 / #DB-19）。绑定与解绑**一律不回写** `merchant.jd_merchant_id / current_stage / status`；解绑只把成员行 `active_key` 置 NULL（行即审计，**不删任何进度行**）；活跃成员 < 2 时**同事务关闭组**，并**同事务退役该组剩余的全部活跃成员行**（#PB-37 E：否则会留下「组已关闭 + 成员行仍 active_key=1」的自相矛盾状态，该账号永久占用 `uk_member_active` 槽位而**再也无法被绑定**）。

```
GET    /api/admin/merchant/{merchantId}/bindings                     # 绑定详情（同店账号）
POST   /api/admin/merchant/{merchantId}/bindings                     # 绑定成员（幂等）
DELETE /api/admin/merchant/{merchantId}/bindings/{memberMerchantId}  # 解绑成员
```

| 维度 | 内容 |
|------|------|
| 功能 | 管理后台「商家进度」页详情抽屉的「同店账号」区：成员列表 + 绑定/解绑（不另建页面、不改路由/菜单） |
| 权限校验 | GET = **需登录**（`Depends(get_current_admin)`，与 API-17 列表同档，`viewer` 可读）；POST / DELETE = `Depends(require_roles("super_admin", "admin"))`（与 `unlock-phase1` **同档**），`viewer` → **403「无权限执行该操作」**；无/无效 token → 401 |
| 请求（POST） | body `{ member_merchant_id: string(1..64) }`；**不暴露内部 binding id** |
| 响应（GET） | `{ jd_merchant_id, group_id, members: [{ merchant_id, nickname, status, current_stage, bound_at, bound_by, is_self }] }`；**未绑定 → `group_id: null` 且 `members` 仅含自身**（`bound_at`/`bound_by` 为 null）。**不返回手机号**；成员按 `bound_at, id` 升序（可复现） |
| 响应（POST，**201**） | 信封 `{ code: 0, message: "绑定成功", data: { success: true, group_id, members: [...] } }`——`message` 为**中文专句**（管理后台直接用作成功 toast，返回通用 `success` 会暴露给运营）；**幂等**：目标已在同组 → 返回现状、**不重复写行** |
| 响应（DELETE，200） | 信封 `{ code: 0, message: "已解绑", data: { success: true } }`（同上，`message` 为中文专句） |
| 失败文案（7 条，原文见 §4.3） | 400「该商家已被登记」/「该商家尚未登记京麦商家ID，无法绑定」/「该账号已绑定到其它商家」/「不能绑定自身」/「**该京麦商家ID已有绑定组，请刷新后重试**」；404「绑定关系不存在」/「商家不存在」 |
| 并发冲突处理（#PB-37 D） | 唯一键即串行化点，**不加锁、不重试**：写入阶段的 `IntegrityError`(1062) → `rollback()`(**不留半写行**)→ **重读当前绑定状态**判定原因 → 结构化 400（目标账号已进别组 → 「该账号已绑定到其它商家」；否则 → 「该京麦商家ID已有绑定组，请刷新后重试」，`logger.warning` 留痕）。改造前该场景为 **HTTP 500「服务器内部错误」** |
| 唯一性约束（**数据库层**，非仅应用层） | 「一个 `jd_merchant_id` 只能一个活跃组」= `uk_group_active(jd_merchant_id, active_key)`；「一个账号只能一个活跃组」= `uk_member_active(merchant_id, active_key)`；`active_key` = 1 活跃 / NULL 已退役（MySQL 唯一索引允许多 NULL → 历史行可无限保留）。**实测**：手工插入第二条活跃组 → 1062 |
| 组键来源 | 发起绑定那个商家的 `merchant.jd_merchant_id`；**为空 → 400 拒绝**（未登记无从确认同店） |
| **解绑语义（#PB-37 E）** | ① 被解绑成员行：`active_key→NULL` + `released_at/released_by`（**不删行**，`bound_at/bound_by` 永久保留）；② 若关组（活跃成员 < 2）：**同事务**把该组剩余 `active_key=1` 的成员行**全部退役**（同样只置 NULL + 留痕）⇒ 库内**不存在**「组 `active_key IS NULL` 且其成员仍有 `active_key=1`」的状态（不变量，可复查 SQL 见 §8.3.8）。**用户可见后果**：店内只有 2 个账号时，解绑其中任何一个 ⇒ **绑定关系整体解除**，另一个账号也不再共享本店进度（随即回到「1 人组 = 未绑定」）；**进度行不删、不清零**，各自回落 |
| 审计 | **不新建审计表**：成员行自带 `bound_by/bound_at/released_by/released_at`，组行自带 `created_by/closed_at/closed_by` |
| 实现位置 | `app/api/v1/admin_merchant.py`（路由，只做参数提取与投影）、`app/services/merchant_binding.py`（**唯一接缝**：组解析 / 唯一性 / 关组规则）；用例 `tests/test_merchant_binding.py` |

**进度共享读取口径（API-22 生效后的全局口径；实现 = `app/services/merchant_binding.py` + `app/services/task_progress.py`）**

| 项 | 口径 |
|----|------|
| 参与并集的账号 | `resolve_group_merchant_ids(db, merchant_id)`：本账号 + 同组其它活跃成员；**无绑定 → `[merchant_id]`**（与改造前逐字段等价） |
| 任务完成集合 | **组内并集** `completedTasks = ⋃(各活跃成员 status='completed' 的 taskId)`，**按 taskId 去重**；`phase1_remaining_task_ids = 阶段一启用任务 − 并集` |
| `completedAt` | 同一 taskId 取组内**最早**完成时间（店铺级事实，**单调**：后续成员补做/重做不把时间往后推） |
| 阶段解锁 | **组内 OR**：任一活跃成员 `current_stage='shop_setup'` 或任务派生解锁 ⇒ 整组解锁（`/api/task/stages` 的锁定壳、写路径返回的 `stage2_unlocked`、写入门禁**三处同口径**） |
| 数据专区 | **双层语义**：① `merchant.data_center_unlocked` 持久化标记 = **账号级、不共享**；② listing 任务完成派生的部分 = **进度、按并集共享**。最终 `data_center_unlocked = 本账号 persisted OR 组内 listing 并集派生` |
| 写入与门禁 | 写入仍只写**当前操作账号**（唯一键 `(merchantId, taskId)` 天然隔离）；**门禁判定按组内并集** —— 否则「A 已解锁阶段二、同组 B 提交阶段二任务仍 403」 |
| 已知语义后果（必须知晓） | 「取消完成」只作用于**自己的行**：组内另一成员仍 completed 时该任务在组内仍显示完成，**两人都取消**才回落 pending；解绑后各账号回到「只看自己」 |
| 管理端「一键解锁」 | **不改**：仍写单个 `merchant` 行；因读取按组 OR，效果**自然覆盖全组**（不做「写多行」放大） |
| 管理端原始进度 | `GET /admin/merchant/progress`（`task_progress.list_all` / `find_by_merchant`）**保持原始行**（谁完成），**不按组聚合** |
| 并集/组 SQL 位置约束 | **只允许出现在** `merchant_binding.py` 与 `task_progress.py`；路由、投影层（`services/task.py`）、前端一律消费**已解析结果** |
| 并发语义 | 两个账号同时提交同一 taskId → 写**两行**（不同 `merchantId`，唯一键不冲突）；并集读取是纯读。**无需加锁、不做数据复制、无 Redis/常驻任务** |

### 5.3 阶段二接口（#B-003 新增）

> 阶段隔离规则：商家完成阶段一（onboarding/application/review/opening）全部启用任务后，`merchant.current_stage=shop_setup`，阶段二接口开放；未解锁访问阶段二接口返回 403 "阶段二未解锁"。判定源为 `merchant_task_progress`（completed）+ `default_completed=1`，幂等派生。

#### API-12：商标注册号搜索（阶段二 T2.1.2）

```
GET /api/trademark/search?keyword=小米
```

| 维度 | 内容 |
|------|------|
| 功能 | 输入品牌名关键词，模糊搜索商标注册号列表 |
| 响应 | `[{ brand_name, registration_number }]`，最多 50 条 |
| 涉及表 | trademark_registry（SELECT） |
| 权限校验 | 需要 JWT Token + 阶段二已解锁（否则 403） |
| 参数校验 | keyword 必填，字符串，最小长度 1 |

#### API-13：店铺数据上传（阶段二 T2.5；#PB-24-0/-1/-2 口径回写 2026-09-15）

> 本节是表单与 Excel 上传的**唯一真源**（口径与实现同源：`app/services/shop.py`；方案 `dev-docs/任务单/PB24-日期与数值校验方案.md` §8）。**`timeRange` 表单参数已于 2026-09-15 移除**（#F-30 死参数，客户端从未真正用上），`time_range` 改为**按文件日期跨度推导**（API-13.3）。

```
POST /api/shop/star              # 店铺星级表单
POST /api/shop/product-count     # 商品数量表单
POST /api/shop/health-score      # 商品信息健康分表单
POST /api/shop/trade             # 交易数据 Excel（multipart）
POST /api/shop/traffic           # 流量数据 Excel（multipart）
POST /api/shop/product           # 商品数据 Excel（multipart）
```

| 维度 | 内容 |
|------|------|
| 功能 | 商家上传店铺经营数据（3 个表单 + 3 类 Excel） |
| 表单入参 | `star` / `product-count` / `health-score`：各计数字段（Pydantic `le=4294967295`，即 `INT UNSIGNED` 上界）+ `dataDate` |
| Excel 入参 | `multipart/form-data`：`file` 必传（≤10MB，仅 `.xlsx`）；**不接收 `timeRange`**（已移除）；`merchant_id` 一律取自 JWT，禁止客户端传入 |
| 响应 | 表单：`{ success: true }`；Excel：`{ success, count, total_rows, skipped, normalized, issues[], issues_truncated }` —— **有写入 HTTP 201**、`count=0`（全为坏行）**HTTP 200**，字段口径见 API-13.4 |
| 涉及表 | shop_star_data / shop_trade_data / shop_traffic_data / shop_product_data / shop_product_count / shop_health_score |
| 权限校验 | 商家 JWT（`get_current_merchant`）+ 阶段二已解锁（否则 403） |
| 表单校验文案（400） | 日期非法 → 专句**「数据日期不正确，请填写如 2026-08-05 这样的日期」**（`DATA_DATE_INVALID_MESSAGE`）；整数越界等其它模型校验失败 → 通用句**「提交的内容有误，请检查后重试」**（§4.3.1，**不回显字段名**） |
| 数据日期口径 | 表单与 Excel 走**同一 owner**（`parse_data_date` / `data_date_span`，见 API-13.1）：Excel 侧失败 = **跳过该行 + 进清单**；表单侧失败 = **400** |
| 数值口径 | 非负 + 不超列真实上界 + 超精度显式 `ROUND_HALF_UP`（见 API-13.2）：Excel 侧越界 = **跳过该行 + 进清单**；表单侧越界 = **400** |
| `time_range` 来源 | 由文件日期跨度推导（见 API-13.3）：**不再由客户端传入**，也不再是白名单校验点 |
| 写入策略 | Excel 行级：坏行跳过 + 逐行问题清单；成功行按 `merchant_id + data_date + time_range` 幂等 upsert，**整批一个事务**（循环内不 commit，先 `flush` 再统一 commit，避免同一文件内的重复键 `1062` 打崩整批） |
| 未映射的列（用户裁决 2026-09-15） | 「未导入的列**不要提示用户**」：只写日志（有界），**不进响应契约**（**没有** `unmapped_headers` 字段） |
| 实现位置 | `app/api/v1/shop.py`（路由：只做参数提取与 status_code 投影）、`app/services/shop.py`（解析/校验/写入的唯一 owner）；用例 `tests/test_shop_date_kernel.py`、`tests/test_shop_excel_upload_guard.py`、`tests/test_shop_input_guard.py` |

##### API-13.1 数据日期解析与归一（唯一 owner `app/services/shop.py::data_date_span`）

| 接受形态（Excel 单元格实测量级） | 说明 |
|------|------|
| W1 真日期单元格 | `datetime` / `date`（商智导出在 Excel 中即为日期格式） |
| W2 `YYYY-M-D` | 如 `2026-8-5`（补零归一） |
| W3 `YYYY/M/D` | 如 `2026/8/5` |
| W4 `YYYY.M.D` | 如 `2026.8.5` |
| W5 8 位紧凑 | `20260805`（字符串 / 整数 / 整数值浮点三种载体均可） |
| W6 带时间后缀 | 如 `2026-08-05 00:00:00` |
| W7 日期区间 | `起~止`（商智 7 天导出的单元格形态，多种分隔符）→ **取结束日** |

| 口径 | 内容 |
|------|------|
| 落库形态 | 一律 `YYYY-MM-DD`（`date.isoformat()`），列真源 `DATE` |
| 显式归一（算成功，不算坏值） | 区间取结束日、`2026/8/5` / `2026.8.5` / `20260805` 等非规范形态 → 该行**照常写入**，进清单 `date_normalized`（`action=normalized`） |
| 判失败（**跳过该行**，绝不兜底成「今天」） | 见 API-13.5 的 9 个日期类 reason：缺日期 / 无法识别 / **歧义**（如 `05/08/2026`、`26-08-05` 无法确定年月日顺序——**用户裁决：判失败**）/ 两位年份 / 缺年份 / 不完整 / 非法日历日（如 `2026-02-30`）/ 表格序列号（如 `45000`） |
| 允许范围 | `MIN_DATA_DATE` ~ 今天 + `MAX_DATA_DATE_TOLERANCE_DAYS`，越界记 `date_out_of_range` |
| 「无数据」标记 | 11 种标记（`-`、`—`、`–`、`−`、`－`、`--`、`/`、`\`、`N/A`、`NA`、`n/a`，strip 后比较）→ 该列写 **NULL**：不是坏值、**不跳行、不进清单** |
| 旧实现纠偏 | 原实现把空白/坏日期静默写成「今天」，可能覆盖当天数据；现按「跳过该行 + 进清单」处理（用户裁决：跳过坏行 + 返回逐行问题清单） |

##### API-13.2 Excel 数值取值域与量化

| 口径 | 内容 |
|------|------|
| 列类型真源 | `project/scripts/schema.sql` —— 模块常量 `EXCEL_UNSIGNED_INT_COLUMNS` / `EXCEL_DECIMAL_COLUMNS` 与之一一对应；**未登记的列不判域** |
| 非负（用户裁决 2026-09-15） | 计数 / 金额 / 比率 / 时长**一律不得为负**（明确含「成交单量、成交金额不能为负」）→ `negative_not_allowed` |
| 上界 | `INT UNSIGNED` → `4294967295`；`DECIMAL(M,D)` → `10^(M-D) - 10^(-D)`；超出 → `out_of_range` |
| 小数位 | 超出列 `scale` 的值**显式**按 `ROUND_HALF_UP` 量化（与 MySQL 取整口径一致，`_quantize_to_scale`），**不再交给 MySQL 隐式四舍五入** → 进清单 `scale_rounded`（`action=normalized`，该行仍写入） |
| 无法解析 | 非空且非无数据标记、但解析不出数字 → `not_a_number`（跳过该行） |

##### API-13.3 `time_range` 派生（#PB-24-2；替代原 `timeRange` 入参）

| 文件日期跨度（含首尾） | `time_range` 桶 |
|------|------|
| 1 天 | `yesterday`（单日**沿用该桶**：看板查询枚举即 `yesterday`/`7d`/`30d`，不新增第 4 个桶） |
| 2–10 天 | `7d` |
| 11–31 天 | `30d` |
| 其它（含「起晚于止」） | **400**「文件的日期跨度不支持，请按单日、近 7 天或近 30 天导出后重试」（`TIME_RANGE_UNSUPPORTED_MESSAGE`；日志 `reason=invalid_time_range`，**不进 `issues[]`**） |

- 派生源 = 文件内**首个可解析日期行**的跨度（同一份导出内跨度一致）。
- 动机：**当日导出不再被存进 `7d` 桶** —— 原实现由前端传 `timeRange`，Excel 场景实际恒落 `7d`/`30d`，看板按桶取数会把单日数据混进 7 天口径；改为按文件实际跨度归档后，桶与文件内容一致。

##### API-13.4 Excel 导入响应契约（#PB-24-2）

| 字段 | 类型 | 口径 |
|------|------|------|
| `success` | bool | 恒 `true`（仅在写库成功后返回） |
| `count` | int | **成功写入（upsert）的行数**。注意：同一文件内 `(merchant_id, data_date, time_range)` 重复时按 upsert 覆盖，故库内实际行数可能少于 `count` |
| `total_rows` | int | 参与处理的数据行数（**不含表头**，全空行不计） |
| `skipped` | int | 被跳过的行数（坏行 + 日期缺失行） |
| `normalized` | int | 至少有一处**显式归一**（日期归一 / 小数位四舍五入）但仍写入的行数 |
| `issues` | array | 逐行问题清单，**最多 200 条**（`MAX_ISSUES`） |
| `issues_truncated` | bool | `issues` 是否被截断（`true` 时计数仍为全量） |

`issues[]` 元素（6 字段）：

| 字段 | 类型 | 口径 |
|------|------|------|
| `row` | int | **Excel 物理行号**（表头 = 第 1 行，数据首行 = 2）——与用户用 Excel 打开看到的行号一致 |
| `field` | str | 出问题的列（英文列名，用于排障） |
| `value` | str | 原值回显，截断至 40 字符（`ISSUE_VALUE_MAX_CHARS`；只取日期/数值列，不含其它列内容） |
| `reason` | str | 见 API-13.5 枚举 |
| `action` | str | `skipped`（该行已跳过）/ `normalized`（已归一写入） |
| `message` | str | 用户可读中文文案（单一真源 `ISSUE_MESSAGES`，≤40 字、不含英文字段名） |

边界与状态码：

- **清单上界**：`MAX_ISSUES = 200`；截断时 `count`/`total_rows`/`skipped`/`normalized` **仍为全量**，完整清单写日志（`_log_issues`）。
- **全部行皆坏 → HTTP 200 + 完整清单**（不再 400 丢清单）；**有写入 → HTTP 201**。任何输入都不得 500。
- 文件级 **400 且不写库**：表头完全无法识别（`HEADER_UNRECOGNIZED_MESSAGE`「文件表头无法识别，请使用商智导出的原始文件」）/ 日期跨度不支持 / 无数据行 / MIME 非 `.xlsx` / 文件解析失败 / sheet 数 > 10 / 数据行 > 5000（既有上界不变）。

##### API-13.5 逐行问题清单 reason 枚举（15 项；唯一真源 `ISSUE_REASONS` / `ISSUE_MESSAGES`）

| reason | action | 用户可见文案 | 触发条件 |
|--------|--------|-------------|---------|
| `missing_date` | skipped | 该行缺少数据日期，已跳过 | 日期列整列未映射或该行为空 |
| `unparseable_date` | skipped | 日期格式无法识别，已跳过该行 | 形态不在 API-13.1 接受列表内 |
| `ambiguous_date_format` | skipped | 日期无法确定年月日顺序，已跳过该行 | 如 `05/08/2026`、`26-08-05`（用户裁决：判失败） |
| `two_digit_year` | skipped | 日期用了两位年份，已跳过该行 | 如 `26/8/5` |
| `missing_year` | skipped | 日期缺少年份，已跳过该行 | 如 `8/5` |
| `incomplete_date` | skipped | 日期不完整，已跳过该行 | 如 `2026-08` |
| `invalid_calendar_date` | skipped | 日期不存在，已跳过该行 | 如 `2026-02-30` |
| `date_serial_number_not_supported` | skipped | 日期疑似表格序列号，请设为日期格式后重导 | 如裸数字 `45000` |
| `date_out_of_range` | skipped | 数据日期超出允许范围，已跳过该行 | 超出 API-13.1 允许范围 |
| `date_normalized` | normalized | 日期已按规范格式记录 | 区间取结束日 / 非规范形态（**这不是错误**） |
| `not_a_number` | skipped | 数值无法识别，已跳过该行 | 非空、非标记、解析不出数字 |
| `negative_not_allowed` | skipped | 数值不能为负，已跳过该行 | 计数/金额/比率/时长为负 |
| `out_of_range` | skipped | 数值超出允许上限，已跳过该行 | 超出列真实上界 |
| `scale_rounded` | normalized | 小数位已按该列精度四舍五入 | 超出列 `scale`，已显式量化后写入 |
| `invalid_time_range` | （不进清单） | 文件日期跨度不支持，请按单日、7 天或 30 天导出 | **仅文件级 400 的日志 reason**（整份文件被拒，无逐行语义） |

#### API-14：店铺数据聚合（阶段二数据看板）

```
GET /api/shop/summary?time_range=yesterday|7d|30d
```

| 维度 | 内容 |
|------|------|
| 功能 | 按商家聚合 6 张 shop_* 表，返回各类型已上传指标（数据看板） |
| 响应 | `{ time_range, star, trade, traffic, product, product_count, health_score }`；各类型无数据时为 `null`（空结构） |
| 涉及表 | shop_star_data / shop_trade_data / shop_traffic_data / shop_product_data / shop_product_count / shop_health_score（SELECT） |
| 权限校验 | 需要 JWT Token + 阶段二已解锁（否则 403） |
| 参数校验 | `time_range` **可选**（默认 `7d`；前端始终显式传，保留默认更宽容且不破坏既有调用），取值 `yesterday`/`7d`/`30d`；非法值 → **400 中文专句**「时间范围不支持，请使用 昨天 / 近7天 / 近30天」（单一真源 `app/services/shop.py::TIME_RANGE_INVALID_MESSAGE`，**不回显英文枚举原文**，见 §4.3.1）。校验在路由边界、**先于阶段二门禁**：非法入参恒 400，不因商家未解锁而变 403 |
| 聚合口径 | trade/traffic/product 按 time_range 匹配最新一条；star/product-count/health-score 无 time_range 列，返回最新一条 |

#### API-03/API-04 扩展

- `GET /api/task/stages`：按商家进度返回；未解锁时阶段二 stage 返回锁定壳（`locked:true`、`firstLevelTasks:[]`），解锁后返回 33 个任务（4/14/3/6/6）。
- `GET /api/task/progress`：响应 `stage2_unlocked` / `phase1_remaining_task_ids` / `data_center_unlocked` 的口径见上方 API-03 主体（此处原为扩展补记，保留以便追溯）。
- `POST /api/task/progress`：`pending`（取消完成）、task 启用态校验与解锁派生的完整规则见上方 API-04 主体（同上，保留追溯）。
- **`GET /api/task/stages` 的二级任务投影（#PB-39 / schema v1.11，2026-09-16）**：二级任务新增 **`actionType`**（行为语义，10 值枚举，默认 `none`）与 **`actionParam`**（行为参数，**不透明标识**）两字段，位置紧随 `actionUrl`（与 DB 列序一致）。投影来自 **`app/services/task.py::second_level_dict` 单一处** ⇒ 商家端与管理端任务配置**同时生效**；枚举语义、参数规则与列定义见 **§8.3.9**。既有字段与本接口其它口径**一个不改**（纯增量）。
- 解锁判定统一口径：`stage2_unlocked` 与 `merchant.current_stage='shop_setup'` 对齐（含运营一键解锁场景——运营写 `current_stage=shop_setup` 但不写完成记录时，前端以 `/api/merchant/info` 的 `current_stage` 为权威，`stage2_unlocked` 返回同值；任务路径回滚不覆盖运营手动解锁）。

#### API-16：获取类目入驻资质要求（商家端 T1.1.2）

```
GET /api/category/requirement/{categoryId}
```

| 维度 | 内容 |
|------|------|
| 功能 | 商家端任务 T1.1.2「了解类目要求」：按一级类目查询该类的入驻资质要求与限制条件。 |
| 响应 | `data` 为 `category_requirement` 记录（camelCase），含 `id/categoryId/shopType/shopNameRule/requirements/reviewFocus/contactEmail/isActive/createdAt/updatedAt/deletedAt/category`；无记录时 `data:null`（`code:0`，非 404）。 |
| 涉及表 | category_requirement（SELECT，按 category_id 查单条） |
| 权限校验 | 商家 JWT Token（`get_current_merchant`）；无/无效 token → 401。 |
| 参数校验 | categoryId 必填，正整数（bigint）。 |
| 业务逻辑 | 默认查 `is_active=1` 一条；`requirements` 列为 JSON，返回对象；`category` 关联返回类目对象（id/name/parentId 等）。 |
| 备注 | 修正历史缺陷：原前端 T1.1.2 误调 `/api/admin/category-requirement`（admin 守卫），商户 token 必然 401。本接口为**商家侧**正确形态，前端 `TaskCard` 改走此接口。 |

---

## 六、业务规则

### 6.1 飞书登录规则

| 规则 | 说明 |
|------|------|
| 登录方式 | 仅支持飞书 OAuth 授权登录，不支持账号密码 |
| Token 有效期 | 7 天，过期需重新授权 |
| 商家身份 | 首次登录自动创建 merchant 记录，status 默认为 1（正常） |
| 禁用处理 | status=0 的商家登录时返回 403，不生成 Token |
| V1 例外登记（#PB-26） | ⚠️ V1 未实现 · 例外登记（2026-09-15）· 移除条件=实现『禁用商家』功能时同步实现鉴权侧拦截（`app/api/deps.py::get_current_merchant`）并撤销测试侧 xfail 标记（`api-py/tests/test_merchant_status_guard.py`） |

### 6.2 任务进度规则

| 规则 | 说明 |
|------|------|
| 任务定义 | V1 阶段任务定义在前端硬编码，后端只管 current_stage |
| 进度存储 | V1 前端 localStorage 即时响应 + 后端异步同步 |
| 阶段推进 | 任务完成后检查是否所有必做任务都完成，是则自动推进 current_stage |
| 支线任务 | 支线任务状态由 branch_checked JSON 字段存储 |

> ⚠️ 上表为 **V1 历史口径**（前端硬编码任务定义已作废）。**当前**任务进度/解锁的唯一实现与口径见 §5.2 **API-22 末表**（`app/services/task_progress.py` + `app/services/merchant_binding.py`）：
>
> | 规则（#PB-36 账号绑定生效后） | 说明 |
> |------|------|
> | 完成集合 | **组内并集**（按 taskId 去重）；无绑定 = 只有自己（与绑定功能上线前等价） |
> | 完成时间 | 同一 taskId 取组内**最早**（单调，不回退） |
> | 阶段解锁 | 组内 **OR**（`current_stage` / 任务派生 / 锁定壳 / 响应字段同口径，解锁永久不回滚） |
> | 写入门禁 | 按**组内并集**判定；写入只写当前操作账号 |
> | 数据专区 | 账号级持久化标记**不共享** + listing 任务并集派生**共享**（两层取 OR） |

### 6.3 类目资费查询规则

| 规则 | 说明 |
|------|------|
| 类目层级 | 两级结构：parent_id=0 为一级，parent_id>0 为二级 |
| 资费优先级 | 品牌特殊资费 > 基础资费，查询时先查 fee_brand_override |
| 保证金一致性 | 特殊资费的保证金与基础资费一致，不单独存储 |
| 缓存策略 | 不缓存（api-py 当前未使用 Redis）：类目列表与资费数据均直连 MySQL 查询 |

### 6.4 埋点规则

| 规则 | 说明 |
|------|------|
| 事件类型 | 必须在枚举范围内，不在范围内的拒绝写入 |
| 商家关联 | 未登录时 merchant_id 为空，不影响 PV 统计 |
| 写入策略 | V1 同步写入，V2 改为异步批量写入 |
| 静默失败 | 埋点写入失败不影响主流程，返回 200 |

### 6.5 飞书推送规则

| 规则 | 说明 |
|------|------|
| 推送频率 | 同一模板类型，同一商家，最多每 2 天推送 1 次 |
| 推送时机 | 入驻当天、任务未完成提醒、首单倒计时、阶段完成祝贺 |
| 失败处理 | 推送失败记录 error_msg，不影响其他业务 |
| 频率控制 | 通过 feishu_notification 表查询最近推送时间判断 |

---

## 七、V1 vs V2 后端边界

| 能力 | V1 后端做什么 | V1 前端做什么 | V2 迁移 |
|------|-------------|-------------|---------|
| 任务定义 | 不管，返回 current_stage | 从 mock-data 读取任务列表 | 后端新增 task_config 表 |
| 任务进度 | 存储到数据库 + 事件埋点 | localStorage 即时响应 | 去掉 localStorage |
| 类目数据 | MySQL 查询 | 从 API 拉取 | 不变 |
| 资费数据 | MySQL 查询 | 从 API 拉取 | 不变 |
| 飞书推送 | 定时任务 + 消息推送 | 不管 | 不变 |
| 埋点 | 接收上报 + 统计 | 前端埋点 SDK | 增加更细粒度事件 |

**V1 核心原则：后端做数据存储和外部对接（飞书），任务逻辑仍由前端驱动。V2 再把任务配置和状态管理迁移到后端。**

---

## 八、变更管理规则

### 8.1 技术栈变更流程

如果要更换语言、框架或核心 SDK，必须：

1. 说明变更原因（性能瓶颈、团队变动、生态变化等）
2. 评估影响范围（哪些模块受影响、迁移成本）
3. 修改本文档对应章节
4. 更新 AGENTS.md 的文档索引
5. 提交 Git 并在 commit message 中说明

### 8.2 API 变更流程

新增或修改 API，必须：

1. 在本文档第五章添加或修改对应 API 定义
2. 说明变更原因和影响
3. 更新前端 API 层代码
4. 提交 Git

### 8.3 数据库 / 迁移 / 结构校验

**表结构真源**：`project/scripts/schema.sql`（表结构唯一真源；ORM 声明必须与之及实库一致）。
**迁移工具**：Alembic（`api-py/alembic/`、`api-py/alembic.ini`）。

#### 8.3.1 硬性禁令：禁止用 autogenerate 生成迁移并执行

> **Alembic 仅用于结构一致性校验（`uv run alembic current`，以及只读的 `compare_metadata` 对账）；禁止使用 `alembic revision --autogenerate` 生成迁移脚本，禁止 `alembic upgrade` 对库执行改结构。**

理由（2026-09-11 只读对账实测口径：`remove_index` 0、`remove_table` 0、`remove_table_comment` 23、`modify_comment` 205、`modify_nullable` 32）：

1. **ORM 仍未声明全部列注释与可空性**：只读对账仍报 `remove_table_comment` 23 项（全部 23 张表的表注释）、`modify_comment` 205 项、`modify_nullable` 32 项。autogenerate 会把「ORM 未声明的实库对象」判定为多余对象，一旦执行即**误删实库注释、并把可空性改回 ORM 口径**（索引与表的缺口已分别由 #PB-6/#PB-11 与 #DB-7 清零，见 §8.3.3）。
   - 历史口径留存：2026-09-10 首次对账时该三项分别为 `remove_index` 31 / `remove_table_comment` 12 / `modify_comment` 172 / `modify_nullable` 29 / `remove_table` 4，是当初立此禁令的直接依据。
2. **真源新增表若不同步补 ORM 模型，autogenerate 会生成 `drop_table`**：当前真源 **25 张表**（v1.7 新增 AI 配置两表，见 §8.3.6）已与实库、ORM 元数据**三者一致**（`scripts/check_schema.py` 建议态 advisories = 0 实测），但该保护依赖「新增真源表必须同时补模型」的纪律（见 §8.3.4 第 3 步）。
3. **`compare_type=True` 已可用（#PB-13 / P4 R1~R2 修复，2026-09-11）**：原先因 ORM 元数据存在 6 个无长度 `String` 列（`category_requirement.review_focus`、`event_log.meta`、`first_level_task.description`、`second_level_task.description`、`second_level_task.detail`、`stage_config.description`）而直接抛 `sqlalchemy.exc.CompileError: VARCHAR requires a length on dialect mysql`；6 列已全部改为 `Text`（前 5 列在此前批次，`event_log.meta` 由 #PB-13），实测 `compare_type=True` 可跑通。
   - 同时 18 个 `DATETIME(6)` 列已按真源补 `fsp=6`，ORM↔实库**时间精度差异现在可被自动发现**（实测 54 项 `modify_type` 中与 datetime 相关的为 **0**，即 18 列精度声明与实库完全一致）。
   - 新暴露的 54 项 `modify_type` 属 **ORM 声明与真源的类型差异**（非本轮引入）：`tinyint`→`INTEGER`/`SMALLINT` 14 项、`decimal(*)`→`FLOAT` 24 项、`date`→`VARCHAR(10)` 6 项、`decimal(3,1)`→`VARCHAR(16)` 4 项、`varchar(16)`→`VARCHAR(10)` 3 项、`varchar(32)`→`VARCHAR(16)` 1 项、`json`→`TEXT` 1 项（`event_log.meta`，见 §5.2/§9.7）；这些不影响 `compare_type=False` 的口径与门禁，列后续批次处理。
   - **禁令不变**：即便 `compare_type=True` 现已可跑通，autogenerate 仍会因第 1 条（注释/可空性未收敛）生成破坏性迁移，**禁止生成并执行**。

#### 8.3.2 允许的校验方式

```bash
# 结构一致性校验（只读：不生成迁移文件、不修改数据库结构）
uv run alembic current
```

#### 8.3.3 ORM 收敛计划（只补声明，不做 DDL）

| 批次 | 内容 | 状态 |
|------|------|------|
| 第一批（#PB-6 第 2 项推进） | ORM 索引/唯一键声明收敛：11 张表 23 个普通索引 `Index(...)` 补齐（`remove_index` 31 → 8）+ `fee_config.uk_category` 唯一键补齐（+1 项，`remove_index` 9 → 8；schema v1.4 / #DB-2）+ `feishu_notification` 5 个索引（#PB-11，2026-09-10）。**当前 `remove_index` = 0** | 已完成（2026-09-11 复测） |
| 第二批（#PB-6 第 2 项推进） | 列注释（`modify_comment` 205 / `remove_table_comment` 23）与可空性（`modify_nullable` 32）对齐（数值随 #DB-5 补齐库内注释而上升，属预期） | 待推进 |
| 批 4（#PB-13 / P4 R1~R3） | ORM 声明层收口：18 个 `DATETIME(6)` 列补 `DATETIME(fsp=6)`（10 个模型文件，类型取自 `sqlalchemy.dialects.mysql`）+ `event_log.meta` 无长度 `String`→`Text`（消除 `compare_type=True` 的 CompileError 根因）+ 两个 ORM 测试 docstring 口径更新（v1.6 / 17 个唯一键 / 28 个索引） | 已完成（2026-09-11）；`compare_type=True` 实测可跑通并新暴露 54 项类型差异（属下一批） |
| 第三批（#PB-6 第 2 项推进） | 无 ORM 模型表处置：`merchant_category` / `feishu_notification` **已补模型（#PB-11，2026-09-10）**；`stage` 已由 #DB-7 完成双表收敛并从真源与实库移除（schema v1.6，24→23 表）；`migrations` 残留表亦已不在实库。**当前建议态 advisories = 0**，本批次视为完成；后续新增真源表须同步补模型 | 已完成（2026-09-11 复测） |

#### 8.3.4 结构变更流程

任何数据库结构变更必须：

1. 修改 `project/scripts/schema.sql`（表结构真源）；
2. 由 database Agent 在库上执行（含备份与回滚口径）；**api-py 不通过 Alembic autogenerate 改库**；
3. ORM 声明同步对齐真源（仅补声明，不做 DDL）；
4. 同步更新本文档（§三 目录规范 / 本章）；
5. 提交 Git（提交授权见 `AGENTS.md` 第十四节）。
6. **列注释（`column_comment`）属结构门禁项** —— 修改真源 `project/scripts/schema.sql` 的**列注释**时，必须**同批**把对应的 `ALTER TABLE … MODIFY COLUMN … COMMENT …` 纳入部署执行面；只改真源而不随批落 DDL ⇒ 上线后生产 `check_schema.py` 必红（**实证**：`#DB-24` 只改真源注释、未随批落 DDL ⇒ `#OPS-50` 上线后生产结构门禁 `column_comment:2` 失败）。流程侧自检清单见 `dev-docs/部署规则.md` §十。

#### 8.3.5 数据导入/迁移的字符集硬口径（防双重编码乱码）

> **任何数据导入/迁移，导出与导入两端都必须显式指定 `--default-character-set=utf8mb4`；导入完成后必须运行 `api-py/scripts/check_data_encoding.py`，期望命中 0。**

- 背景（#DB-10，2026-09-14）：生产库曾出现 **5 列 79 行**双重编码乱码（如 `admin_account.realName` 存成 `è¶…çº§ç®¡ç†å‘˜`，应为 `超级管理员`）。根因是**用非 utf8mb4 客户端字符集导入 UTF-8 数据**；服务器上已存在 9-04 的 `pre_mojibake_fix_*` 备份 → **修过又复发**，故必须固化为脚本门禁而不是一次性人工检查。
- 乱码形态经字节级证实是 **CP1252 而非 latin1**（`0x85/0x91/0x98` 等为 CP1252 特有映射，超出 latin1 范围）→ 只用 `latin1` 规则会**全部漏检**（#DB-10 实测命中 0 行）。巡检脚本按「先 CP1252 编回、未定义位置回退 latin1 序值，再 UTF-8 解码；解码成功且与原值不同且含 CJK」判定。
- 命令（只读，不改数据）：
  ```bash
  cd api-py && uv run python scripts/check_data_encoding.py            # 命中>0 → 退出码 1（门禁）
  cd api-py && uv run python scripts/check_data_encoding.py --report-only   # 仅报告，退出码恒 0
  ```
- 退出码：**0 无命中 / 1 有命中 / 2 环境或输入错误**（DB 不可达等，绝不静默跳过）；命中敏感列（口令/盐/密钥/票据）时只报计数、不回显值。
- **不得误修**：#DB-10 已确认 `second_level_task.actionUrl` 中 4 行 `?` 属**正常 URL 查询串**，非乱码（脚本对含 `?` 的 URL 与正常中文均不误判，见 `api-py/tests/test_data_encoding.py`）。

#### 8.3.6 AI 分入口配置表与密钥加密口径（v1.7 / #DB-12 + #PB-21）

**新增两张表**（真源 `project/scripts/schema.sql` v1.7 段 25 / 26；列定义以真源为准）：

| 表 | 关键列 | 说明 |
|----|--------|------|
| `ai_entry_config`（25） | `entry`（`UNIQUE KEY uk_entry`）、`enabled`、`api_key_ciphertext VARCHAR(512)`、`api_key_fingerprint VARCHAR(32)`、`base_url`、`model`、`timeout_ms`、`max_tokens`、`daily_limit`、`updated_by`、`created_at`/`updated_at DATETIME(6)` | 一入口一行；字段 NULL = 回落 env 同名项；**无任何明文 key 列** |
| `admin_ai_config_audit`（26） | `entry`、`field`、`action`、`old_display`/`new_display`、`old_len`/`new_len`、`old_fp`/`new_fp`、`admin_id`、`admin_username`、`ip`、`created_at DATETIME(6)` | 每次修改**按变更字段**各一行；密钥类只留掩码/长度/指纹，**绝不落密钥原文与密文** |

**密钥加密口径（用户 2026-09-14 裁决「全阶段加密，不使用明文」；实现 `app/services/ai_crypto.py`）**

| 项 | 口径 |
|----|------|
| 算法与格式 | **AES-256-GCM**（12 字节随机 nonce、16 字节 tag）；密文列格式 `v1:` + base64(`nonce(12) ‖ tag(16) ‖ ciphertext`)，**单列自包含**（不拆 nonce/tag 列）；前缀仅表达算法/封装版本 |
| 加密密钥 | env `AI_CONFIG_ENC_KEY`：**64 位 hex（32 字节）**，生成 `openssl rand -hex 32`，每环境独立、禁止跨环境复用；校验规则 `^[0-9a-fA-F]{64}$` |
| 轮换槽位 | `AI_CONFIG_ENC_KEY_PREVIOUS`（仅轮换窗口期使用）：解密按 **主密钥 → 前一密钥** 顺序尝试，**加密恒用主密钥**；因此**不需要** `enc_key_version` 列 |
| **不进启动校验** | `AI_CONFIG_ENC_KEY` **不纳入** `validate_startup_settings`（`app/core/config.py`）：缺失/非法**不阻断启动**、不做启动期 DB 探测 |
| 降级四态 | 库中有密文但密钥缺失 `enc_key_missing` / 换错 `auth_tag_mismatch` / 占位非法 `enc_key_invalid` / 密文格式非法 `format_invalid` → **一律视为未配置、回落 env**，记结构化 warning，`apiKeyStatus='decrypt_failed'`，**绝不 500** |
| 写入遇密钥问题 | **400**「加密密钥未配置或非法，无法保存密钥」，不写库、不写审计 |
| 缓存纪律 | 进程内缓存只持有**密文行快照**；密钥原文仅在单次解析/单次调用期间存在于内存（不落日志、不进接口、不进审计） |
| 轮换 | `api-py/scripts/rotate_ai_config_key.py`（显式 `--old-key/--new-key/--dry-run`，逐行独立事务 + `SELECT … FOR UPDATE`，幂等：主密钥可解即跳过）；**不建议停机**（先上 `PREVIOUS` 再重加密）；线上运维步骤见 `dev-docs/部署上线前必做清单.md` 条目 3b |
| 门禁 | 新表 DDL 与实库一致由 `uv run python scripts/check_schema.py` 硬校验（表数 23 → 25） |
#### 8.3.7 手机号登录相关表（v1.9 / #DB-13 + #DB-14 + #PB-23）

| 表 / 键 | 口径 |
|---------|------|
| `merchant_login_code`（**8 列**） | `id, phone, biz_id, out_id, ip, attempts, used_at, created_at`。语义 = **「发送/校验审计 + 频控计数」行**（PNVS 口径）：`biz_id` 取自 `SendSmsVerifyCode` 响应、`out_id` 为我方透传 ID（校验时回传）、`attempts` = 该行**校验失败次数**（C8 达上限即置 `used_at` 作废）；索引 `idx_phone_created` / `idx_ip_created` / `idx_created`。**不存任何验证码材料**（无 `code_hash` / `code_salt` / `expires_at`——自建验证码口径已由 #PB-23 steer ② 废止） |
| `internal_notify_log`（9 列） | `id, channel, event_type, merchant_id, target_type, target, status, error_message, created_at`；内部通知可观测/可手工重试，与面向商家的 `feishu_notification` 分表；索引 `idx_event_created` / `idx_merchant`。写入方 `app/services/internal_notify.py`（旁路，失败不影响 201） |
| `captcha_daily_counter`（4 列） | `day(主键), used, created_at, updated_at`；C7 人机校验成本闸的**按天聚合**计数（`INSERT … ON DUPLICATE KEY UPDATE used = used + 1` 原子自增）；1 行/天、天然有界、无需清理任务 |
| `merchant.uk_phone` | `UNIQUE KEY uk_phone (phone)`：登录键必需的完整性约束；**软删商家仍占用该键**（G-3 → 二次注册命中 1062 → 400「该手机号不可用，请联系平台」）；唯一索引允许多 NULL，不阻塞存量无手机号行 |
| 表数 | 25 → **28**（`merchant_login_code` 段 27 / `internal_notify_log` 段 28 / `captcha_daily_counter`），真源 `project/scripts/schema.sql` v1.9；结构与实库一致性由 `scripts/check_schema.py` 硬校验 |
| 行数上界 | 登录码行按日增（受 C6 全局日上限约束）并保留 7 天（运维 cron `DELETE … WHERE created_at < NOW() - INTERVAL 7 DAY`）；内部通知按事件量增长（仅新商家注册一次）；成本闸 1 行/天 |

#### 8.3.8 账号绑定相关表（v1.10 / #DB-19 + #PB-36）

> 方案：`dev-docs/任务单/merchant-account-binding-design.md`；表结构真源 `project/scripts/schema.sql` **v1.10**（段 30/31 + 段 28 就地补列补索引）。**DDL owner = database（#DB-19 已落地）**，本段只登记口径。

| 表 / 键 | 口径 |
|---------|------|
| `merchant_binding_group`（7 列） | `id, jd_merchant_id, active_key, created_by, created_at, closed_at, closed_by`。代表「一个被运营确认同一店铺的账号集合」；`jd_merchant_id` 弱关联 `merchant.jd_merchant_id`（**无外键**）。`uk_group_active(jd_merchant_id, active_key)` 保证「一个京麦ID 只能一个活跃组」；关闭时 `active_key→NULL`（多 NULL 兼容）→ 历史组行可保留 |
| `merchant_binding_member`（8 列） | `id, group_id, merchant_id, active_key, bound_by, bound_at, released_at, released_by`。`uk_member_active(merchant_id, active_key)` 保证「一个账号只能在一个活跃组」；**解绑不删行**：`active_key→NULL` + `released_at/by` 留痕（该行即审计） |
| 组维护规则 | **创建**：首次绑定时建组（组键 = 发起方 `merchant.jd_merchant_id`，为空 → 400）；**关闭**：活跃成员 **< 2** 时**同事务**关闭（`active_key→NULL` + `closed_at/by`）**并同事务退役该组剩余的全部活跃成员行**（#PB-37 E） |
| 不变量（可复查，#PB-37 E） | 库内**不得存在**「`merchant_binding_group.active_key IS NULL` 且其成员里仍有 `active_key=1`」的状态——该状态会让相关账号永久占用 `uk_member_active` 槽位、**再也无法被重新绑定**。复查 SQL：`SELECT g.id FROM merchant_binding_group g JOIN merchant_binding_member m ON m.group_id = g.id AND m.active_key = 1 WHERE g.active_key IS NULL`（期望 **0 行**） |
| `internal_notify_log.dedupe_key`（v1.10 就地补列） | `VARCHAR(128) NULL` + 索引 `idx_event_dedupe(event_type, dedupe_key, created_at)`。取值：`merchant_registered → merchant_id`；**`jd_duplicate_registration → "jd:<jd_merchant_id>"`**（24h 去重窗口）。既有 `merchant_registered` 幂等判据 `(event_type, merchant_id, status='sent')` **保持不变**（向后兼容：旧行为不需要该列即可工作） |
| 事件枚举（`event_type`，VARCHAR(32)） | `merchant_registered`（新商家注册）／**`jd_duplicate_registration`**（京麦ID 重复登记申请）。**长度约束**：列宽 32 + `STRICT_TRANS_TABLES` ⇒ 事件名必须 ≤32 字符（方案稿 34 字符名实测报 1406，见 API-20 扩展） |
| 表数 | 28 → **30**（段 30 `merchant_binding_group` / 段 31 `merchant_binding_member`），与实库、ORM 模型（`app/db/models/merchant_binding_{group,member}.py`）一致 |
| 孤儿巡检 | `merchant_binding_member.merchant_id` 被 `check_orphan.py` **动态发现**并纳入（按 `information_schema` 扫描，禁硬编码表名）；绑定时校验目标账号存在且未软删 ⇒ 期望 **0 孤儿**；出现孤儿即 `exit 1`（可见、不静默） |
| 行数上界 | 组/成员行随运营手工操作增长（量级 = 账号数）；解绑**不删行** → 历史行单调累积（可审计，无清理需求） |
| 不回写声明 | 绑定/解绑**不回写** `merchant.jd_merchant_id` / `current_stage` / `status`；进度共享靠**读取期并集**实现（**不做数据复制**，用户口径） |

#### 8.3.9 任务行为语义字段 `actionType` / `actionParam`（v1.11 / #DB-23 + #PB-39）

> 设计单：`dev-docs/任务单/action-type-design.md`（已评审，含裁决记录）；表结构真源 `project/scripts/schema.sql` **v1.11**（段 12 `second_level_task` 就地补两列，**未新建表**）。**DDL owner = database（#DB-23 已落地）**，本段只登记口径与列定义。动因：任务卡「点击后做什么」原由前端按 `taskId` 字面量硬编码（10 处判断 / 13 个任务），改号必须改前端；本字段把行为语义交给后端声明。

| 项 | 口径 |
|----|------|
| `actionType` 列 | `VARCHAR(32) NOT NULL DEFAULT 'none'`（位于 `actionUrl` 之后、`actionParam`/`tag` 之前）。**未声明 = `none`**，`ADD COLUMN` 时全表自动落 `none`（可回滚、可幂等） |
| `actionParam` 列 | `VARCHAR(64) DEFAULT NULL`。**只是不透明标识**（非 JSON / 非条件 / 非组件名 / 非文案），**仅** `data_form` / `data_upload` 使用 |
| `actionType` 枚举（10 值，`none` 为默认） | `none`=无特殊行为（无 `actionUrl` 仅埋点；有 `actionUrl` 打开外链）／`advisor_qr`=弹商家顾问企微二维码／`category_picker`=卡内经营类目选择器／`fee_picker`=卡内资费选择器 + `fee` 锚点定位／`trademark_lookup`=商标注册号查询表单／`title_optimize`=AI 标题优化面板／`image_optimize`=图片优化区块／`advisor_entry`=顾问入口区块／`data_form`=数据分析专区表单录入（`actionParam` ∈ `star`/`product-count`/`health-score`）／`data_upload`=数据分析专区文件上传（`actionParam` ∈ `trade`/`traffic`/`product`） |
| **参数规则（服务端强校验）** | `data_form` / `data_upload` **必须**带非空 `actionParam`；其余 8 个行为 **必须为空/NULL**。违反 → **400**，文案复用统一校验出口 `app/core/error_handlers.py::VALIDATION_MESSAGE`「提交的内容有误，请检查后重试」（**不新造文案**）。owner = `app/services/admin_task_config.py::_assert_action_pair`（部分更新按**与库内值合并后的有效组合**判定）；路由 `app/api/v1/admin_task.py` 的 `ActionType` Literal 只做枚举形状校验（同一套校验通道，无第二套） |
| 省略语义 | 创建：省略 `actionType` → 落默认 `none`；省略 `actionParam` → `NULL`。更新：省略 = 不改；`actionParam` 显式 `null` = 清空（切换到非 `data_*` 时必须显式清空，否则 400） |
| 移除 `actionUrl` 语义不变 | `actionUrl` **不是** `actionType` 取值（它是独立的 URL 字段，TaskCard 已按「有 URL 就打开」处理）；`actionType='none'` 且 `actionUrl` 非空 ⇒ 打开外链 |
| 回填（#DB-23 已执行，51 行） | 默认全表落 `none`（含 2 行 `status=0`，不按 status 过滤）；例外 **13 行**按现存前端行为逐条回填（`T1.1.2`/`T1.1.3`/`T1.3.8`/`T2.1.2`/`T2.1.4`/`T2.3.1`/`T2.3.2` + 专区分发 6 行）；校验 `SELECT actionType, actionParam, COUNT(*) … GROUP BY 1,2` = **10 组 / 51 行** |
| 边界（不做） | 不做规则引擎/可配置脚本（`actionType` 是**capability token**，只声明「需要哪种交互」，**不描述交互长什么样**）；不改 `type` / `completionType`（其陈旧枚举另立极小单）；不新增用户可见文案；不改进度/解锁口径 |
| 上线顺序（硬约束） | **DB → PB →（AF / FE 可并行）→ T**：FE 依赖后端返回 `actionType`，若 FE 早于 DB/PB 上线则所有行为退化为 `none`（按钮不失效，但二维码/类目/资费入口静默消失） |
| 实现位置 | `app/db/models/second_level_task.py`（两列）、`app/services/task.py::second_level_dict`（**单一投影**）、`app/services/admin_task_config.py`（参数规则 owner + 创建/更新接线）、`app/api/v1/admin_task.py`（`ActionType` Literal + DTO 字段）；用例 `api-py/tests/test_task_action_type.py` |

#### 8.3.10 二级任务 `type` / `completionType` 枚举对齐（#PB-40）

> 背景（**阻塞级**）：开发库存在越界取值，而后端 `Literal` 只有 3 值 ⇒ 这 8 条任务从管理后台保存**必 400**（编辑表单把库内旧值原样回传；#AF-20 已用真实 UI + API 逐项证实）。总控裁决（2026-09-16）：**扩展枚举到现实值、不改数据**（不把 8 行规范成 3 值——那等于改写业务配置并牵动既有测试）。

| 列 | 列定义 | 现实取值（开发库 `SELECT DISTINCT`，合计 51 行） | 说明 |
|----|--------|--------------------------------------------|------|
| `type` | `VARCHAR(16) NOT NULL` | `mandatory` 12 / `suggested` 1 / `guide` 30 / **`form` 4** / **`jump` 1** / **`upload` 3**（**6 值**） | 主轴 = **运营重要度**（必做/建议/引导）。`form`/`jump`/`upload` 是 **旧轴遗留**（`actionType` 之前的行为轴）：**保留**以便存量行可原样保存，**不再新增**；**行为语义一律以 `actionType`（§8.3.9）为准** |
| `completionType` | `VARCHAR(16) NOT NULL` | `system_check` 4 / `manual_submit` 9 / `click_read` 31 / **`form_submit` 4** / **`file_upload` 3**（**5 值**） | `form_submit`/`file_upload` 同为旧轴遗留，保留理由同上 |

| 项 | 口径 |
|----|------|
| 越界行（8 条，**数据一行不动**） | `T2.1.2`(form/form_submit)、`T2.1.3`(jump/click_read)、`T2.5.1`/`T2.5.5`/`T2.5.6`(form/form_submit)、`T2.5.2`/`T2.5.3`/`T2.5.4`(upload/file_upload)。其中 **6 条正是 #PB-39 接入 `actionType` 的 `data_*` 任务** ⇒ 修复前**无法从管理后台编辑** |
| 校验口径（两道） | ① 路由 `TaskType` / `CompletionType` Literal 补齐到现实值（DTO 层，非法 → **400** + 统一文案 `VALIDATION_MESSAGE`）；② 服务层 `app/services/admin_task_config.py::_assert_task_enums` **再兜一道**（列上无 CHECK 约束，任何调用方都不得把越界值写进库）。两处取值必须 = 开发库 `SELECT DISTINCT` |
| 防漂移（硬，**#PB-40-R1 订正口径**） | `api-py/tests/test_task_enums_aligned.py::assert_db_values_covered` 断言 **库内取值 ⊆ 枚举**（`SELECT DISTINCT` − 允许值必须为空）——这才是「会导致该任务保存 400」的方向，命中即失败并**指名**越界取值；**反向（枚举值暂时没有任何行使用）不失败**，只记一行「未被任何行使用的取值」（`logger.info` + `[enum-report]`），避免「某唯一行被删/被改」造成**假红**（本项目已多次吃假红阻塞全链的亏，如 ORM 期望清单漂移）。另有：② `Literal == 服务层元组`（同源一致性，**相等**断言保持不变）；③ 「8 条越界行现值组合原样回传 → 200，且真实行前后快照逐字段一致（未 UPDATE、`updatedAt` 未变）」；④ 未知值 → 400（HTTP + 服务层守卫） |
| 与 `actionType` 的关系 | `type` 的 `form/upload/jump` **不是**行为真源；行为真源 = `actionType`（§8.3.9）。本段保留它们只为「存量数据可原样保存」，避免后人把旧轴当行为契约 |
| 实现位置 | `app/api/v1/admin_task.py`（两个 Literal）、`app/services/admin_task_config.py`（`TASK_TYPES` / `COMPLETION_TYPES` + `_assert_task_enums`）；用例 `api-py/tests/test_task_enums_aligned.py`（4 例） |
| 已对齐（实测核对 2026-09-16） | `project/scripts/schema.sql` **v1.11** 段 12 的列注释**已经写全现实取值并注明旧轴遗留**：`type`（L306）「任务类型/重要度(mandatory=必做/suggested=建议/guide=引导;另存旧轴遗留值 form/jump/upload——属交互形态的旧轴残留,行为语义一律以 actionType 为准,勿再新增此类值)」、`completionType`（L307）「完成方式(system_check=系统校验/manual_submit=人工提交/click_read=点击阅读;另存旧轴遗留值 form_submit=表单提交/file_upload=文件上传——行为语义同样以 actionType 为准)」⇒ **DDL 注释侧无需再改** |
| 本轮未做（待办） | 管理后台「任务配置」页下拉仍是 3 值 → **`#AF-21`**（后端已能原样保存现实值，前端下拉补齐后 UI 才与库一致）；前端商家端不涉及本枚举 |

---


## 九、工程纪律

> 本章是后端开发的强制约束，不可跳过。

### 9.1 核心原则

**优先复用框架能力，不重复造轮子。**

FastAPI / Pydantic / SQLAlchemy 已提供的能力，禁止自己实现。新增任何东西之前，先查对应官方文档确认是否已有方案。

### 9.2 新增依赖规则

| 场景 | 规则 |
|------|------|
| 新增 Python 依赖 | 必须先说明为什么既有依赖（含标准库与 FastAPI 生态）不够用，再添加；经 `uv add` 写入 `pyproject.toml` 并登记到 §2.2 |
| 替换现有依赖 | 必须说明原依赖的问题和新依赖的优势，评估迁移成本 |
| 禁止行为 | 不准装"看起来有用但用不到"的依赖；不准因为别人项目用了就跟风装；不准回引历史已移除依赖（Redis、slowapi、passlib 等） |

**审批流程：** 提出 → 说明原因 → 评估影响 → 更新 `api-py/pyproject.toml` + 本文档 §2.2 → 提交

### 9.3 目录调整规则

| 场景 | 规则 |
|------|------|
| 新增业务域 | 按本文档第三章目录规范：`app/services/<domain>.py` + `app/api/v1/<domain>.py`，不得随意新增顶层目录 |
| service 拆分/合并 | 必须说明业务原因（如文件过大、职责不清），不得因"感觉应该拆"就拆 |
| 文件移动 | 必须更新所有 import 路径，确保 `uv run python -m compileall` 与 pytest 通过 |
| 禁止行为 | 不准在 `app/api/v1/` 内写业务规则或 SQL；不准绕过 `app/services/` 直接操作 ORM |

### 9.4 错误码规则

| 场景 | 规则 |
|------|------|
| 使用标准 HTTP 错误码 | 优先使用 400/401/403/404/500/502，不自创 |
| 自定义业务错误码 | 必须在本文档第五章错误码规范中登记，说明用途 |
| 禁止行为 | 不准在代码中硬编码魔法数字作为错误码；不准不同接口返回不同格式的错误响应 |

**错误码新增流程：** 提出 → 说明业务场景 → 登记到本文档 → 实现 → 提交

### 9.5 框架更换规则

| 场景 | 规则 |
|------|------|
| 更换后端框架 | 必须提供性能/团队/维护性的量化对比，不能因为"感觉更好"就换 |
| 更换 ORM | 必须说明 SQLAlchemy 2.0（同步）的具体瓶颈，评估所有 ORM 模型与查询的迁移成本 |
| 更换数据库 | 必须说明 MySQL 无法满足的具体场景，提供数据量/并发量的证据 |
| 审批门槛 | 框架更换属于高风险变更，需要全团队确认 + 本文档更新 + Git commit 说明 |

### 9.6 框架最佳实践清单

以下为 FastAPI / SQLAlchemy 强制遵守的最佳实践：

| 编号 | 实践 | 说明 |
|------|------|------|
| P1 | 路由函数不超过 20 行 | 超过则抽取到 `app/services/` |
| P2 | Service 单向依赖 | 禁止循环依赖 |
| P3 | ORM 模型不跨域直接引用 | 跨域数据访问走 service 方法 |
| P4 | 异常统一走全局异常处理器 | 抛 `ApiException`（`app/core/exceptions.py`），禁止手工拼错误响应 |
| P5 | 配置走 pydantic-settings | 禁止硬编码数据库连接、密钥；禁止 `os.environ` 散落代码 |
| P6 | 请求/响应必须有 Pydantic 校验 | 每个 body/query/param 都要有类型注解或 Pydantic 模型 |
| P7 | 路由不写业务逻辑 | 路由只做参数提取、鉴权依赖与 service 调用 |
| P8 | 不用的能力不安装 | WebSocket、GraphQL、Redis 缓存等未用能力不装 |
| P9 | 新增依赖必须说明原因 | 不能因为"可能用到"就装 |
| P10 | 所有变更必须更新本文档 | 语言/框架/依赖/目录/错误码的变更，先改文档再改代码 |

### 9.7 变更记录

| 日期 | 变更内容 | 原因 | 影响范围 |
|------|---------|------|---------|
| 2026-07-20 | 初始定稿 | 项目启动 | 全局 |
| 2026-08-06 | 新增阶段二接口（trademark/shop）与阶段隔离规则；API-03/04 扩展解锁字段 | 阶段二重开发 #B-003 | 商家端任务/阶段二模块 |
| 2026-08-06 | 新增第十章 AI 经营分析（API-15）与 ai_analysis_log 限流/审计表 | 数据看板 AI 解读提前到当前阶段 #B-006 | 阶段二数据看板 |
| 2026-08-07 | AI 结果缓存、限流口径（仅成功计数）、AI_TIMEOUT_MS 与体验/成本评估 | 避免重复调用与 token 成本 #B-007 | 阶段二数据看板 AI 分析 |
| 2026-09 | 新增 API-16 获取类目入驻资质要求（商家侧）；修正 T1.1.2 原误调 /api/admin/category-requirement 的历史缺陷 | 商户端 T1.1.2「了解类目要求」在 NestJS/Python 均因 admin 守卫+商户 token 无法获取；按契约登记为商家侧接口 | 商家端任务 T1.1.2 |
| 2026-09-10 | 全文技术口径由 NestJS/TypeORM/Redis 同步为 `api-py`（Python 3.12 + FastAPI + SQLAlchemy 2.0 + PyMySQL）：§一/§二/§三/§5.1/§8.3/§九/§10.2；新增 §8.3「数据库 / 迁移 / 结构校验」并写入 **Alembic 仅校验、禁止 autogenerate 执行**的硬性禁令 | 本文件是后端唯一真源，但第 1/2/3/9.8 章仍为 NestJS 口径，形成内部矛盾，会使「指向当前真源」的指引二次漂移；原 NestJS `backend/` 已作废 | 全局（技术口径）；接口清单、业务规则、错误码语义不变 |
| 2026-09-10 | 接入 `merchant_category`（API-07 `POST /api/merchant/category`：1-3 个 / is_primary 唯一 / 类目存在性 / 去重 / 覆盖式写入 + event_log 同事务）与 `feishu_notification`（API-10 服务层 `send_notification`：task_reminder 48h 频控 + 发送 + 落库，sender 可注入；HTTP 路由/触发点待定）；补两个 ORM 模型（含 feishu_notification 的 5 个既有索引声明，不改库结构） | 用户口径「这两张表应该有用，做一下接入」；真源已有合同但 api-py 无实现，且两表此前无 ORM 模型（autogenerate 会判 drop_table） | `api-py/app/db/models/merchant_category.py`、`api-py/app/db/models/feishu_notification.py`、`api-py/app/services/merchant_category.py`、`api-py/app/services/feishu.py`、`api-py/app/api/v1/merchant.py`、`api-py/tests/test_merchant_category_api.py`、`api-py/tests/test_feishu_notification_service.py` |
| 2026-09-14 | 新增静态单文件端点 `GET /api/static/advisor-qr.jpg`（无需登录、路径仅来自 `ADVISOR_QR_FILE` 配置、无路径参数故无目录穿越入口、`Cache-Control: public, max-age=3600`）；未配置 → 结构化 404「顾问二维码未配置」，不可用/配置越界 → 结构化 500 且不回显绝对路径；新增 `api-py/static/.gitkeep` 占位与 `.env.example` 注释项 | 前端 `<img src="/api/static/advisor-qr.jpg">`（stage2.ts / index.vue）与 API-09 的 `qr_url` 都指向该路径，但 api-py 从未挂载任何静态资源、仓库内也没有图片 → 生产实测 404，该功能从未真正可用（NestJS 时代同样缺失） | `api-py/app/api/v1/static_assets.py`、`api-py/app/api/router.py`、`api-py/app/core/config.py`、`api-py/tests/test_static_advisor_qr.py`、§5.2 API-09 |
| 2026-09-14 | 修正欢迎卡片幂等标志语义：`merchant.welcome_sent` 仅在 `_send_card` 成功时置 1，**发送失败不置位**（保持 0 以便重试，返回 `{sent:false, first:true}`），已置位仍跳过；同时给出存量脏数据（`welcome_sent=1` 但从未成功发送）的幂等复位 SQL 建议（本单未改数据） | 原实现无论成败都置 1；生产 2026-09-14 首个真实商家登录时发送失败但标志被置 1，导致该商家永远不会再收到欢迎卡片（重试被幂等跳过） | `api-py/app/services/feishu.py`、`api-py/tests/test_welcome_idempotency.py`、§5.2 API-10 |
| 2026-09-14 | 统一错误文案（#T-3 R6）：新增 `app/core/error_handlers.py` 作为**唯一错误出口**，校验失败统一为中文「请求参数不合法：字段 <字段名>」且**不泄露 `body./query./path.` 等 Loc 前缀**，完整校验细节（`loc`/`type`/`msg`）只进日志并**丢弃 `input`/`ctx`**（防 password 等敏感值入日志）；404 →「接口不存在」、405 →「请求方法不允许」；响应信封与状态码语义不变（§4.3.1） | 生产公开面验收 R6：线上 message 中英混用，校验错误返回 `body.password: String should have at least 6 characters`，404 返回英文 `Not Found` | `api-py/app/core/error_handlers.py`、`api-py/app/main.py`、`api-py/tests/test_error_messages.py`、§4.3.1 |
| 2026-09-14 | 修复飞书卡片发送调用形态：由不存在的 `client.im.message.create(...)` 改为 SDK 实测形态 `CreateMessageRequestBody.builder()...build()` + `CreateMessageRequest.builder()...build()` + **`client.im.v1.message.create(request)`**；成功判定用 `resp.success()`，失败记飞书 `code`/`msg` 并返回 `False`（降级面，不抛异常）；保持 `_send_card` 为唯一发送实现（欢迎/阶段完成/API-10 共用） | 生产实测首个真实商家登录后日志报 `'ImService' object has no attribute 'message'` —— 该调用路径从未被真实验证过，欢迎卡片/阶段完成/任务提醒全部发送失败 | `api-py/app/services/feishu.py`、`api-py/tests/test_feishu_card_send.py`、§5.2 API-10 |
| 2026-09-14 | 飞书登录错误码用户可读映射：`20003`（授权码无效/已过期）→「登录链接已失效，请重新点击飞书登录」（不再展示裸码），其它未列出码保持附码；日志补强（`msg=None` 也显式记录、授权码类错误附「授权码一次性」提示、**不记授权 code 原文**）；映射实现为服务层纯函数 `_oidc_failure_message`（单一真源） | 生产实测用户点击登录时命中 `code=20003`，原文案只给裸码用户看不懂也不知如何处置（前端废码循环由 #F-17 修） | `api-py/app/services/feishu.py`、`api-py/tests/test_feishu_login_chain.py`、§5.2 API-01 |
| 2026-09-14 | 新增只读巡检脚本 `api-py/scripts/check_data_encoding.py`（CP1252→UTF-8 双重编码乱码检测，命中>0 退出码 1 可作门禁、`--report-only` 恒 0、环境错误 2、敏感列只报计数）+ 纯函数用例 `tests/test_data_encoding.py`；§8.3.5 固化「导入/迁移两端必须 `--default-character-set=utf8mb4` + 导入后跑该脚本」硬口径 | 生产曾出现 5 列 79 行双重编码乱码且**修过又复发**（9-04 已有 pre_mojibake_fix 备份），根因是非 utf8mb4 客户端字符集导入；乱码形态为 CP1252 而非常用 latin1 规则，需固化为可重复门禁 | `api-py/scripts/check_data_encoding.py`、`api-py/tests/test_data_encoding.py`、§8.3.5 |
| 2026-09-14 | 修复飞书登录 OIDC 换 token：**先取 app_access_token 并以其作 `Authorization: Bearer` 头**调用 `/authen/v1/oidc/access_token`；app_access_token 进程内缓存（300s 提前刷新余量、线程安全、单条目有界）；飞书 `code`/`msg` 落日志并把错误码附入可见文案；修正原「与 NestJS 实现等价」的错误注释（NestJS 版从未真实环境验证，同样缺该头） | 生产实测缺该头时飞书返回 `code=20014`「The app access token passed is invalid」，登录完全不可用；原实现只把错误吞成通用文案，排障只能手工复现 | `api-py/app/services/feishu.py`、`api-py/tests/test_feishu_login_chain.py`、§5.2 API-01 |
| 2026-09-14 | 补齐登记管理端 `/admin/merchant` 一族 4 个端点（主表列表 / 任务进度 / 指定商家进度 / 阶段一解锁）为 **API-17**（§5.2）：`GET /admin/merchant/progress` 的 `merchantId` 由**必填改可选**（不传或传空 = 全部商家），「全部」取数落 `task_progress.list_all`、固定排序 `merchantId, taskId`，新增上界 `MAX_PROGRESS_ROWS=5000`（超限结构化 400「结果过多，请按商家查询」，**不静默截断**，逃生通道为按 merchantId 查询）；读权限 = 需登录（viewer 可读，依 `任务管理后台开发标准` §6 + §7.2），解锁仍限 admin / super_admin | 管理后台「商家管理」页进入即 toast 400「请求参数不合法：字段 merchantId」且列表恒空：前端无参调用（`admin/src/api/task-progress.ts:19-22`、`admin/src/pages/merchant-progress/index.vue:108`）而后端把参数写成必填，且本文档对 `/admin/merchant` 一族 **0 命中**（无契约真源），两侧各自假设；#OPS-32 亦在 err 日志实测同一校验失败记录 | `api-py/app/api/v1/admin_merchant.py`、`api-py/app/services/task_progress.py`、`api-py/tests/test_admin_merchant_progress_api.py`、`project/docs/任务管理后台开发标准.md` §6、§5.2 API-17 |
| 2026-09-11 | ORM 声明层收口（P4 R1~R3）：18 个 `DATETIME(6)` 列补 `fsp=6`；`event_log.meta` 由无长度 `String()` 改 `Text`；测试 docstring 口径更新为 v1.6/17 键。**纯声明无 DDL** | `compare_type=True` 此前因 6 个无长度 String 列直接抛 CompileError，ORM↔真源时间精度差异无法被发现 | `api-py/app/db/models/*.py`（10 个）+ event_log.py、`api-py/tests/test_orm_{unique_constraints,indexes}.py` |
| 2026-09-11 | 补齐 API-07 查询侧 `GET /api/merchant/category`（回显已保存经营类目；形状与提交项对齐、名称仍以 `category` 表/API-05 为唯一真源）；登记该接口成功文案「经营类目已保存」与全部失败文案到 §5.2；`POST /api/merchant/category` 补 `status_code=201` 声明使 OpenAPI 与运行时一致 | #PB-11 只写不读属半截接入（面板刷新后看不到已存类目）；#OPS-10 实测 POST 声明与运行时不符 | §5.2 API-07、`api-py/app/services/merchant_category.py`、`api-py/app/api/v1/merchant.py` |
| 2026-09-10 | API-10 绑定列口径修正：`merchant（SELECT feishu_user_id）` → `SELECT feishu_open_id` | 实测 `merchant.feishu_user_id` 全表 0 行非空（登录链路只写 feishu_open_id，`merchant` 表 16 行中仅 1 行有 open_id），按原口径实现该接口对所有商家都会 400「商家未绑定飞书」 | §5.2 API-10 |
| 2026-09-10 | 管理端登录请求限流落地：同一 IP 与同一用户名在 `ADMIN_LOGIN_RATE_WINDOW_SECONDS`（默认 60 秒）内各最多 `ADMIN_LOGIN_RATE_MAX`（默认 10）次登录请求，超限 429 + 需等待秒数（被拒请求不登记）；与失败锁定语义独立（限流计全部请求、锁定只计失败） | 真源 `任务管理后台开发标准` §7.1 要求「登录接口限制每分钟10次」，api-py 此前无实现 | `api-py/app/services/auth.py`、`api-py/app/core/config.py`、`api-py/tests/test_admin_login_rate_limit.py`、`api-py/tests/conftest.py` |
| 2026-09-10 | 管理端登录失败锁定落地：连续 `ADMIN_LOGIN_MAX_ATTEMPTS`（默认 5）次失败锁定 `ADMIN_LOGIN_LOCK_MINUTES`（默认 30 分钟），锁定期内正确口令也返回 429 + 剩余秒数，成功登录清零；明确「单进程内存态、多点部署需落库」边界 | 真源 `任务管理后台开发标准` §5.2 要求该能力，api-py 此前无任何失败计数/锁定实现 | `api-py/app/services/auth.py`、`api-py/app/core/config.py`、`api-py/tests/test_admin_login_lockout.py` |
| 2026-09-10 | ORM 补齐 11 张表的 23 个普通索引 `Index(...)` 声明（名称与 `schema.sql`/实库一致，仅补声明、不做 DDL） | Alembic 只读对账 `remove_index` 31 项，autogenerate 会据此误生成 `drop_index` | `api-py/app/db/models/`、`api-py/tests/test_orm_indexes.py` |
| 2026-09-14 | 新增 **API-18 管理端 AI 分入口配置**（`GET /admin/ai-config/list`、`PUT /admin/ai-config/{entry}`、`POST /admin/ai-config/{entry}/verify`；仅 super_admin；掩码/指纹/状态投影、省略=不修改/null=清除回落 env/空串与掩码回写=400、verify 失败恒 502 且超时上界 15s）；同步登记 #PB-21 的 10 条行为口径 | P7 v1.1「全阶段加密」主线落地（#PB-21 / #AF-14），接口真源此前缺失 | §5.2 API-18；实现 `app/api/v1/admin_ai_config.py`、`app/services/ai_config.py`、`app/services/ai_crypto.py`；测试 `api-py/tests/test_admin_ai_config.py` |
| 2026-09-14 | §8.3 新增 **§8.3.6 AI 分入口配置表与密钥加密口径**：登记 `ai_entry_config`（含 `api_key_ciphertext`/`api_key_fingerprint`）与 `admin_ai_config_audit`（含 `old_fp`/`new_fp`）两表，以及 AES-256-GCM / `v1:`+base64(nonce‖tag‖ct) / `AI_CONFIG_ENC_KEY`(64 hex) / `AI_CONFIG_ENC_KEY_PREVIOUS` 轮换槽位 / 不进启动校验 / 降级四态回落 env / 写入遇密钥问题 400 | schema.sql v1.7（#DB-12）新增两表，原文档仅登记到 v1.6 的 23 张表 | `project/scripts/schema.sql` 段 25/26；`api-py/scripts/rotate_ai_config_key.py`；`dev-docs/部署上线前必做清单.md` 条目 3b |
| 2026-09-14 | 补登记管理端既有端点族（**API-19**）：`/admin/auth`、`/admin/account`、`/admin/stage`、`/admin/group`、`/admin/task`、`/admin/feedback`，逐族给出方法/用途/角色/前端调用点；其中 `stage` 写接口标注「已封装但当前无页面调用」 | 这些端点在管理后台实际使用且 `app/api/router.py` 已注册，但本文档此前 0 命中，形成「有实现、无契约」 | §5.2 API-19；`app/api/router.py`；`admin/src/{api,store,pages}` |
| 2026-09-14 | `PUT /api/merchant/registration` 由「只存档不校验」改为**带格式校验**并补齐契约（**API-20**）：`jd_merchant_id` 仅数字 `^[0-9]+$`、`shop_name` 仅汉字 `^[\u4e00-\u9fa5]+$`（服务层唯一 owner `_normalize_registration`），长度上界由 DTO 承载（≤64 / ≤128，与列一致），`null` 与空串同义 = 清空放行；非法 → 400「京麦商家ID仅支持数字」/「店铺名称仅支持汉字」（超长 → 「请求参数不合法：字段 …」），**一律不回显用户输入原文** | 用户 2026-09-14 要求这两个字段做格式校验（商家ID 仅数字、店铺名称 仅汉字），而该接口原口径是「只存档不校验」且本文档**未登记**（有实现、无契约）；老前端总是同时提交两个字段（未填为空串），故空串必须按清空放行，避免「只填一项」的既有保存路径回归 | `api-py/app/services/merchant.py`、`api-py/app/api/v1/merchant.py`、`api-py/tests/test_merchant_registration_validation.py`、§5.2 API-20 |
| 2026-09-15 | 校验失败文案口语化（**#PB-24-1-R1**）：通用句由「请求参数不合法：字段 <字段名>」改为固定**「提交的内容有误，请检查后重试」**（`app/core/error_handlers.py::VALIDATION_MESSAGE`；**移除英文字段名后缀**，排障靠 `validation_log_detail` 日志）；移除随之失效的 `field_name()`/`LOC_PREFIXES` 与其单测；新增首个**接口专用句**：`POST /api/shop/star|product-count|health-score` 的 `dataDate` 非法 → 「数据日期不正确，请填写如 2026-08-05 这样的日期」（单一真源 `app/services/shop.py::DATA_DATE_INVALID_MESSAGE`）；同步 §4.3.1 口径与 API-13/API-20 文案行 | 用户裁决「文案换成更口语化的」：`totalCount`/`jd_merchant_id` 这类英文字段名对商家用户没有意义；日期是高频且可自行修正的错误，通用句无法告诉用户「该怎么填」 | `api-py/app/core/error_handlers.py`、`api-py/app/services/shop.py`、`api-py/tests/test_error_messages.py`、`api-py/tests/test_merchant_registration_validation.py`、§4.3.1、§5.2 API-13 / API-20 |
| 2026-09-15 | 真源登记「商家 status 拦截」为 **V1 例外**（#PB-26）：在 API-01 异常情况 / API-02 / API-04 / §6.1 禁用处理 4 处就地加同一句 ⚠️ 例外标注（移除条件=实现「禁用商家」功能时同步在 `app/api/deps.py::get_current_merchant` 实现鉴权侧拦截，并撤销 `api-py/tests/test_merchant_status_guard.py` 的 xfail 标记）。现状依据：`deps.py:33-45 get_current_merchant` 只验 JWT、**不查库**；`deps.py:48-79 get_current_admin` 查库并校验 `status=1` → **两端不对称**；测试侧已由 #T-3 以 `xfail(strict=True)` 登记（若拦截被提前实现则 XPASS → 套件变红，强制撤销标记） | 用户 2026-09-15 裁决「商家 status 拦截**不做**，记一下，如果后续做了禁用商家功能，那这个也一并做上」 | `project/docs/后端技术方案.md` §5.2 API-01/API-02/API-04、§6.1、§9.7；测试侧 `api-py/tests/test_merchant_status_guard.py`（#T-3 已登记） |
| 2026-09-15 | **API-13 口径回写**（#PB-24-0/-1/-2）：新增 API-13.1~13.5 五个子节——① 数据日期接受形态（7 类）与显式归一（区间取结束日 / 非规范形态记 `date_normalized`）；② 数值非负 + 列真实上界 + 超精度显式 `ROUND_HALF_UP`；③ `time_range` 按文件跨度派生（1 天→`yesterday`、2–10→`7d`、11–31→`30d`，其它 400）并**移除 `timeRange` 入参**；④ Excel 导入响应契约（`count`/`total_rows`/`skipped`/`normalized`/`issues[]`/`issues_truncated`，`row` = Excel 物理行号，`MAX_ISSUES=200` 截断后计数仍全量，有写入 **201** / 全坏行 **200**）；⑤ 15 项 `reason` 枚举与用户可见文案；顺带登记 `GET /api/admin/merchant` 的 `keyword` 为 4 字段 OR 模糊匹配（#PB-29，**未加索引**） | 文件级 400 与逐行清单此前只存在于方案与代码里，接口真源缺载 → 存在双真源风险；`timeRange` 为 #F-30 已证死参数；`keyword` 只匹配 2 字段时运营按京麦商家ID/店铺名搜不到商家 | `project/docs/后端技术方案.md` §4.3.1（仅指路）、§5.2 API-13 / API-17；实现 `api-py/app/services/shop.py`、`api-py/app/api/v1/shop.py`、`api-py/app/services/merchant.py` |
| 2026-09-15 | 修掉两处「真源 vs 实现」漂移（**#PB-30**）：① `GET /api/shop/summary` **补 `time_range` 枚举校验**（原实现有默认值、无校验，传 `abc` 也 200）→ 非法值 **400**，并把 API-14 口径改为 **`time_range` 可选（默认 `7d`）**；② `POST /api/shop/analysis` 的 400 文案由英文 NestJS 遗留（`time_range must be one of the following values: …`）改为**中文专句**「时间范围不支持，请使用 昨天 / 近7天 / 近30天」，与 summary **共用同一常量**（新增 `TIME_RANGE_VALUES` / `assert_time_range` / `TIME_RANGE_INVALID_MESSAGE`，位于 `app/services/shop.py`；analysis 仍为**必填 + 枚举**，行为不变） | ① 「用户可见文案一律中文、不回显英文枚举」（§4.3.1 硬口径）此前被违反；② API-14 记「必填 + 枚举 + 非法 400」而实现无校验 → 文档与实现不一致（由 #PB-28 派生视图核对发现、总控复核确认） | `project/docs/后端技术方案.md` §4.3.1 / §5.2 API-14 / §10.1 API-15 / §9.7；实现 `api-py/app/services/shop.py`、`api-py/app/api/v1/shop.py`；用例 `api-py/tests/test_shop_time_range_guard.py`；派生视图 `docs/前后端对接方案.md` |
| 2026-09-15 | 登录页提示白话化 + AI 报错文案对齐实现（**#PB-31**）：① 飞书凭证不合规时的用户可见文案由「飞书登录未配置(FEISHU_APP_ID/FEISHU_APP_SECRET 缺失或为占位)」改为白话**「登录服务暂不可用，请稍后重试或联系管理员」**（常量 `app/services/feishu.py::FEISHU_LOGIN_UNAVAILABLE_MESSAGE`），**环境变量名与 missing/placeholder 判定依据只进 `logger.error`**（不回显密钥材料）；占位清单改为复用 `app/core/config.py::FEISHU_SECRET_PLACEHOLDERS`（去掉就地内联的第二份），**触发条件与行为不变**；② §10.1 API-15「失败处理」按实现回写为**按错误码细分**（`LLM_TIMEOUT`→504、上游限流→429、其余→502；文案单一真源 `app/services/ai.py::error_message_for_code`），替换原单句「AI 分析暂不可用，请稍后重试」 | 用户 2026-09-15 裁决「管理后台的都不改，登录页的改成白话」「按建议来」；原 AI 502 文案真源与实现（按码细分：429/504/502）不一致 | `project/docs/后端技术方案.md` §5.2 API-01 / §10.1 / §9.7；实现 `api-py/app/services/feishu.py`（`ai.py` 未改）；用例 `api-py/tests/test_feishu_login_chain.py`；派生视图 `docs/前后端对接方案.md` |
| 2026-09-15 | **AI 经营分析输出中文化（#PB-32）**：新增指标中文名册 `app/services/metric_labels.py`（`SECTION_LABELS` 6 + `GENERIC_LABELS` 2 + `METRIC_LABELS` 42 + `TIME_RANGE_LABELS` 3，用词逐项对齐前端 `SHOP_METRIC_LABELS`/`SHOP_SUMMARY_TYPES`），送模型的汇总数据改为**只换键不换值**（`localized_summary`），`SYSTEM_PROMPT_ANALYSIS` 增加硬要求「内容文本一律中文指标名、禁止英文字段名与下划线命名」；真源新增 §10.6 名册表 / §10.7 边界说明。**响应结构、错误码、既有文案均未改**；实测真实调用 3 次无英文字段名残留，故**未加**后处理兜底 | 用户 2026-09-15：「AI 经营分析出来的内容里面有英文字段名，需要把英文字段名都调整成中文，例如 `health_score` 应该为健康评分」（根因：prompt 直接 JSON 化英文键，模型照英文键作答） | `project/docs/后端技术方案.md` §10.3 / §10.6 / §10.7 / §9.7；实现 `api-py/app/services/metric_labels.py`（新增）、`api-py/app/services/ai.py`；用例 `api-py/tests/test_ai_prompt_labels.py`（新增）；派生视图 `docs/前后端对接方案.md` |
| 2026-09-15 | **`health_score` 用词统一 + 标题优化同类治理（#PB-33）**：① `SECTION_LABELS.health_score` 由 #PB-32 暂定的「健康评分」改为**「商品信息健康分」**（用户裁决「前端看板那个区块标题是「商品信息健康分」 叫这个」），名册与前端 `SHOP_SUMMARY_TYPES` 现存 **0 处用词差异**，注释中「有意差异」说明已删净，`SYSTEM_PROMPT_ANALYSIS` 的示例名同步；② 新增 `TITLE_FIELD_LABELS`（9 键，`TitleOptBody` 穷尽）+ `localized_title_input()`，`optimize_title()` 入参**只换键**中文化，并新增 `SYSTEM_PROMPT_TITLE` 禁止 camelCase 字段名（**响应结构/错误码/既有文案不变**）；真源 §10.6 增补标题优化名册表、§10.7 由「未治理」改写为「已治理」 | 用户 2026-09-15 裁决「前端看板那个区块标题是「商品信息健康分」 叫这个」「optimize_title（AI 标题优化）同样修改」「其余显不出来」（`FEISHU_APP_ID` 占位判定 / API-01 历史陈旧行 / 输出偶现英文词「data」三条关闭不处理） | `project/docs/后端技术方案.md` §10.6 / §10.7 / §9.7；实现 `api-py/app/services/metric_labels.py`、`api-py/app/services/ai.py`；用例 `api-py/tests/test_ai_prompt_labels.py`；派生视图 `docs/前后端对接方案.md` |
| 2026-09-15 | 补登录「剩余秒数」取值契约（**#PB-34**）：失败锁定剩余秒数 **∈ [1, 配置窗口]**、限流需等待秒数 **∈ [1, 窗口长度]**；取整统一由 `app/services/auth.py::_lock_seconds_left` 实现并抹掉浮点尾差（原 `ceil(deadline - now)` 在 float64 上有 +1 ulp 正尾差，实测 `base=130398.254` 下 24.8% 时点得 1801，用户可见「请在 1801 秒后重试」）；新增回归用例 `api-py/tests/test_auth_lock_seconds.py`（假时钟钉大数量级 + 0.001 步长全窗口扫描） | 该取值是**用户可见契约**且已被用例钉死，不写进真源则下次「顺手把 ceil 改回去」无据可依（防漂移）；#PB-34 已由总控复核通过 | `project/docs/后端技术方案.md` §5.1 / §9.7；实现 `api-py/app/services/auth.py`（仅取整逻辑）；用例 `api-py/tests/test_auth_lock_seconds.py`（新增） |
| 2026-09-15 | AI 上游**空响应自动重试 1 次**（**#PB-35**）：`_post_chat` 拆为「重试外壳 + `_post_chat_once` 单次调用」，**仅** `LLM_EMPTY_RESPONSE` 重试，且**只用剩余超时预算**（`timeout_ms` 为总预算，硬上界总调用 ≤ 2 次、总耗时 ≤ `timeout_ms`；剩余 < `_EMPTY_RETRY_MIN_BUDGET_MS`=1000ms 不重试，直接按原错误码返回）；429/超时/网络/5xx/解析失败**一律不重试**；日志只记次数与原因码，不记上游返回原文与密钥。错误码与文案契约不变 | 上游大模型偶发返回空 content 造成 502「AI 分析结果异常，请稍后重试」（#PB-33 已 A/B 证为上游瞬时抖动）；用户 2026-09-15 裁决「按你的建议来」——让瞬时失败自愈，同时不放大上游压力、不拉长用户等待 | `project/docs/后端技术方案.md` §10.1 / §9.7；实现 `api-py/app/services/ai.py`；用例 `api-py/tests/test_ai_empty_retry.py`（新增） |
| 2026-09-16 | **新增 API-21 手机号 + 短信验证码登录（#PB-23）**：两个公开端点 `POST /api/auth/phone/send-code`（200）与 `POST /api/auth/phone/login`（**201**，登录即注册）；验证码走**阿里云号码认证（PNVS）** `SendSmsVerifyCode`/`CheckSmsVerifyCode`（`ReturnVerifyCode=false`，**我方不接触明文码**），人机校验走**单一接缝** `VerifyCaptcha`/`VerifyIntelligentCaptcha`（fail-closed）；频控矩阵 C1~C10 全部落库计数 + C7 成本闸 `captcha_daily_counter` 原子自增；新商家注册旁路内部 IM 通知（失败不影响 201）；真源新增 §4.3「503 分段」、§4.3.1 专句、§5.1 登录方式、§5.2 **API-21**、§8.3.7 三张新表、§2.2 两项依赖 | 商家登录需脱离企业身份（飞书自建应用只对企业成员开放），同时抗短信轰炸（按条计费 + 骚扰风险）：用户 2026-09-16 拍板「手机号 + 短信验证码 + 阿里云验证码 2.0」；总控 steer ② 将发/校验改为 PNVS（验证码由阿里云生成与校验） | `project/docs/后端技术方案.md` §2.2 / §4.3 / §4.3.1 / §5.1 / §5.2 / §8.3.7 / §9.7；实现 `api-py/app/services/{phone_auth,sms_verify,captcha,internal_notify}.py`、`api-py/app/api/v1/auth.py`、`api-py/app/core/{config,utils}.py`；用例 `api-py/tests/test_phone_login.py`（34 例）；派生视图 `docs/前后端对接方案.md` |
| 2026-09-16 | **图形认证服务端二次校验按官方文档改写（#PB-23-R2）**：`app/services/captcha.py` 由「captcha 产品 SDK（`VerifyCaptcha`/`VerifyIntelligentCaptcha`）」改为**官方 HTTP 二次校验接口** `POST {CAPTCHA_API_SERVER}/validate?captcha_id=<appId>`（请求体 **form-urlencoded**、5 个参数、`sign_token = HMAC-SHA256(appKey, lot_number)`、**仅 `status==success` 且 `result==success` 通过**）；**fail-closed**（非 200/超时/连接异常/非 JSON/`status=error`/`result!=success` 一律 400 且不发码，**不照抄官方 demo 的 fail-open**）；配置新增 `CAPTCHA_APP_ID`/`CAPTCHA_APP_KEY`/`CAPTCHA_API_SERVER`，删除 `CAPTCHA_SCENE_ID`/`CAPTCHA_ENDPOINT`；依赖移除 `alibabacloud_captcha20230305`（保留 PNVS 短信依赖） | 用户 2026-09-16 提供官方《图形认证服务端集成》文档并裁定「原 SDK 口径作废」；captcha OpenAPI 产品与号码认证的「图形认证」不是同一套 | `project/docs/后端技术方案.md` §2.2 / §5.2 API-21 / §9.7；实现 `api-py/app/services/captcha.py`、`api-py/app/core/config.py`；用例 `api-py/tests/test_phone_login.py`（图形认证 17 例） |
| 2026-09-16 | **收口两处（#PB-23-R3）**：① 删除旧产品残影配置 `CAPTCHA_PREFIX`（「验证码 2.0」`initAliyunCaptcha` 的 prefix 概念已否定，我方前端用 `initAlicom4 + captchaId`；`api-py/`+`project/`+`docs/` 内 grep 0 命中）；② **图形认证凭证缺失由 400 改为 503**：新增单列出口 `_reject_not_configured()` → **503 +「登录服务暂不可用，请稍后重试或联系管理员」**（与 `services/feishu.py::FEISHU_LOGIN_UNAVAILABLE_MESSAGE` **同句同源**）+ `logger.error`（点名缺失变量），语义上区分「服务侧配置故障」与「用户未通过校验」（其余 fail-closed 分支保持 400 +「请先完成安全验证」不变） | ① 旧产品残影污染当前合同（AGENTS §一）；② 生产忘配凭证会让商家误以为是自己没做验证、且易被监控漏掉（400 不表达服务侧故障） | `project/docs/后端技术方案.md` §4.3 / §5.2 API-21 / §9.7；实现 `api-py/app/core/config.py`、`api-py/app/services/captcha.py`；用例 `api-py/tests/test_phone_login.py`（图形认证 23 例） |
| 2026-09-16 | **PNVS 发码 endpoint 配错修复 + 异常可诊断性（#PB-23-R4）**：① `ALIYUN_SMS_ENDPOINT` 默认值由 `dysmsapi.aliyuncs.com` 改为 **`dypnsapi.aliyuncs.com`**（真机根因：`SendSmsVerifyCode` 是号码认证 PNVS 的 Action，打到短信服务产品会 `InvalidAction.NotFound` → 502；零成本探针「同请求只换 Host」已复现：旧 host `code=InvalidAction.NotFound` / `message=code: 404, Specified api is not found`，新 host 业务级响应 `code=isv.ValidateFail` / `message=code: 400, 验证失败`）；② `sms_verify.py` 两处异常分支由「只记类名」补为 **`error` + `code` + `message` + `request_id`**（不记 `exc_info`/密钥/完整手机号/验证码；用户文案与 502 语义不变）；③ **业务级「校验未通过」映射**：`ClientException(code=isv.ValidateFail)` → `check_verify_code` 返回 False（用户看到 400 三态文案，C8/C10 错次计数恢复生效），不再误判 502 | 用户真机点「获取验证码」→ 502，日志只有 `error=ClientException` 缺 message，排查耗时；输错码在真机走业务级异常分支，若不映射则「验证码不正确」永远显示成「短信服务暂不可用」且错次上限失效 | `project/docs/后端技术方案.md` §2.2 / §5.2 API-21 / §9.7；实现 `api-py/app/core/config.py`、`api-py/app/services/sms_verify.py`；用例 `api-py/tests/test_phone_login.py`（手机号登录 55 例） |
| 2026-09-16 | **补齐两处可观测性缺口（#PB-23-R5）**：① **内部通知失败原因结构化**：`app/services/internal_notify.py` 异常分支由仅记 `exception:<类名>` 改为 `_upstream_failure_detail(exc)`——保留类名兜底并补上游 `code`/`msg`（lark SDK 的 `ObtainAccessTokenException` 自带 `code=10014`/`msg=app secret invalid`），`_send_text` 失败返回值同样补 `msg`；两层截断（msg 段 ≤160、整行 ≤ `ERROR_MESSAGE_MAX_CHARS=255`，对齐 `internal_notify_log.error_message` 列宽）；仍不记密钥/token/完整手机号，通知失败依旧不阻塞 201。② **`api` 命名空间 INFO 日志可落盘**：新增 `app/main.py::_configure_logging()`（模块导入即调用、**幂等**：handler 带标记属性且只挂一个，重复导入/多 worker/测试重复 import 均不叠加；只调 `api`，不碰 uvicorn 与第三方、不开 DEBUG；保留 `propagate` 以兼容 pytest `caplog`），级别取新增配置 `LOG_LEVEL`（默认 `INFO`）。**日志落点**：`api` → stderr → dev 由启动重定向落 `%TEMP%\dev-api-py.*.log`、prod 由 systemd 收进 **journald**。此前全仓无 `basicConfig`/`dictConfig`/`addHandler`，`api` 只落到 `logging.lastResort`（WARNING+），`短信认证已下发`/`手机号登录成功`/`手机号自注册新商家` 等 INFO 业务行**全部丢失** | #T-5 真机联调暴露：飞书 `10014 app secret invalid` 被吞成 `exception:<类名>`，排障只能直连飞书接口；且生产 journald 中查不到任何 INFO 业务日志（可观测性缺口，非功能缺陷） | `project/docs/后端技术方案.md` §9.7；实现 `api-py/app/services/internal_notify.py`、`api-py/app/main.py`、`api-py/app/core/config.py`（`LOG_LEVEL`）；用例 `api-py/tests/test_phone_login.py`（手机号登录 58 例） |
| 2026-09-16 | **管理端商家清单：列表补阶段/状态筛选（#PB-24）**：`GET /api/admin/merchant` 新增两个**可选**查询参数 `stage`（精确匹配 `merchant.current_stage`）与 `status`（精确匹配 `merchant.status`），**只接受已登记取值**（`onboarding`/`shop_setup`；`0`/`1`/`2`），未登记 → **400** 且文案复用统一校验出口 `error_handlers.VALIDATION_MESSAGE`（**不回显取值原文**，取值与已登记集合只进日志）；**空串/纯空白 = 不筛选**（前端「全部」选项）；与既有 `keyword`（4 字段 OR 模糊）、`page`/`page_size`（上界 100）、`deleted_at IS NULL`、`created_at` 倒序 **全部 AND 组合**，`total` 为筛选后行数；响应结构与 **8 字段投影不变（不新增 `phone`）**（**注：投影字段数已于 #PB-25 由 8 改为 9，见下行**）、**无 DDL**、无其它接口/前端改动 | 管理后台新建「商家清单」页需按**阶段/状态**筛选（用户诉求；本单不做禁用商家功能）。取值为**已登记枚举**：若原样透传 SQL，传错值会静默返回空列表，把「参数传错」显示成「没有数据」，用户与排查者都无从判断 | `project/docs/后端技术方案.md` §5.2 API-17；实现 `api-py/app/api/v1/admin_merchant.py`、`api-py/app/services/merchant.py`（取值校验唯一 owner）；用例 `api-py/tests/test_admin_merchant_ops.py`；派生视图 `docs/前后端对接方案.md` |
| 2026-09-16 | **管理端商家清单：列表投影补 `status`（#PB-25）**：`app/services/merchant.py::list_all` 的投影由 8 字段扩为 **9 字段**——在 `current_stage` 后新增 `status`（整数 0 禁用 / 1 正常 / 2 已退出，与筛选参数同语义）；响应信封 `{list, total, page, page_size}` 与其余 8 字段**不变**，`created_at` 倒序不变；真源 API-17 响应形状行同步为 9 字段 | 前端 `#AF-14` 反馈的**真实契约缺口**：筛选（#PB-24）已实测生效，但列表「状态」列取不到数据（投影无 `status`），前端只能显示占位「—」。前端 `admin/src/api/merchant.ts` 已把 `status` 声明为**可选**，后端加字段即显示中文标签，故**不改前端**（属 #AF-14 交付面） | `project/docs/后端技术方案.md` §5.2 API-17 / §9.7；实现 `api-py/app/services/merchant.py`；用例 `api-py/tests/test_admin_merchant_ops.py`（投影键集由 8 键**收紧**为 9 键 + 三态逐条回读对账）；派生视图 `docs/前后端对接方案.md` |
| 2026-09-16 | **账号绑定：1 个京麦商家ID ↔ N 个商家账号，只共享进度（#PB-36）**：新增**唯一接缝** `app/services/merchant_binding.py`（`resolve_group_merchant_ids` / `get_bindings` / `bind_member` / `release_member` / `jd_merchant_id_is_taken`）；进度读取改**组内并集**（`completedTasks` 按 taskId 去重、`completedAt` 取**最早**、阶段解锁/锁定壳/写路径响应/写入门禁四处按**组 OR**、`data_center_unlocked` = 本账号 persisted OR listing 并集派生），**写入仍只写本账号**、解绑只改 `active_key` 且**不动任何进度行**；登记新增**重复登记拒绝**（两条占用判据 → 400「该商家已被登记」，不写库、不回显占用方）+ 新内部通知 **`jd_duplicate_registration`**（正文脱敏、24h 去重、**先 400 后异步**发送——由 `ApiException.background` 承载旁路任务，因 FastAPI 注入的 `BackgroundTasks` 在异常路径实测不执行）；新增 **API-22** 三端点（GET 需登录 / POST·DELETE `admin`+，幂等、不暴露内部 id、`viewer` → 403）；绑定/解绑**成功响应 message 为中文专句**「绑定成功」/「已解绑」（信封 `{code:0,message,data}`，供管理后台直接做成功 toast）；真源新增 §5.2 **API-22**（含进度共享全局口径表）、**API-20 扩展**（唯一性判据 + 通知子块）、§4.3 **6 条文案**、§6.2 当前口径、**§8.3.8**（两表 + `dedupe_key` + 事件枚举）。**无 DDL、无新配置项、无 Redis/常驻任务**（共享靠读取期并集） | 用户诉求：同一京麦主体多账号时进度各自独立（A 完成 B 看不到、同一店铺被重复从零做起），且 `jd_merchant_id` 可被别的账号重复登记而无任何提示。用户已拍板 5 条口径（只共享进度 / 管理后台手工绑定 / 权限等同无主账号 / 支持解绑 / 重复登记拒绝 + 内部通知）。**一处与方案稿的偏离需总控知悉**：`internal_notify_log.event_type` 为 `VARCHAR(32)` + `STRICT_TRANS_TABLES`，方案稿的 `merchant_id_duplicate_registration`（34 字符）**实测报 1406**，故按「DDL 以 database 单落地为准」（方案 §4.2）取同义短名 `jd_duplicate_registration`（一行常量可回退） | `project/docs/后端技术方案.md` §4.3 / §5.2 API-20+API-22 / §6.2 / §8.3.8 / §9.7；实现 `api-py/app/services/{merchant_binding,task_progress,task,merchant,internal_notify}.py`、`api-py/app/api/v1/admin_merchant.py`、`api-py/app/core/{exceptions,error_handlers,utils}.py`；用例 `api-py/tests/test_merchant_binding.py`（21 例）；派生视图 `docs/前后端对接方案.md` |
| 2026-09-16 | **后端收尾四件（#PB-37）**：**A** 移除 `config.py` 中 `INTERNAL_NOTIFY_RECEIVE_ID` 的**真实 open_id 默认值**(源码内硬编码 PII)→ **空串默认 + 只由 `.env`/环境变量注入**；留空 = 未配置 → 内部通知**显式跳过**(`internal_notify.py::_notify_skip_reason`,统一两条路径:开关关闭 / 接收人未配置)+ `logger.info`,不写行不发送、不拒启动、不影响业务返回；**B** `.env.example` 补齐 8 个缺失键(`ADMIN_LOGIN_MAX_ATTEMPTS`/`ADMIN_LOGIN_LOCK_MINUTES`/`ADMIN_LOGIN_RATE_MAX`/`ADMIN_LOGIN_RATE_WINDOW_SECONDS`/`IMAGE_OPT_TIMEOUT_MS`/`IMAGE_OPT_MAX_CONCURRENCY`/`TITLE_OPT_TIMEOUT_MS`/`TITLE_OPT_MAX_CONCURRENCY`,只写键名与默认值);**C** `merchant.py::list_all` docstring 由「8 字段投影」订正为 **9 字段**(#PB-25 起含 `status`);**E（阻断级修复）** `merchant_binding.py::release_member` 关组时**未退役最后一名活跃成员行** → 库内出现「组已关闭 + 该行仍 `active_key=1`」的自相矛盾状态,该账号永久占用 `uk_member_active` 槽位、**再也绑不回去**(实测:管理后台解绑后再绑被拒/500);现改为**关组同事务退役该组剩余全部活跃成员行**(只置 NULL + `released_at/by` 留痕,**不删行**),并补不变量复查 SQL(期望 0 行);用户可见后果:店内只有 2 个账号时解绑任一 ⇒ **绑定关系整体解除**(另一账号回到「1 人组 = 未绑定」),**进度行不删不清零**;**D** `merchant_binding.py::bind_member` 补**并发唯一键冲突**处理:捕获 `IntegrityError`(1062, `uk_group_active`/`uk_member_active`)→ `rollback()`(**不留半写行**)→ **重读当前绑定状态** → 结构化 400(新文案「**该京麦商家ID已有绑定组，请刷新后重试**」/ 复用「该账号已绑定到其它商家」),`logger.warning` 留痕;**不加锁、不重试**（设计 §3.2）。改造前该场景为 **HTTP 500** | A 源码硬编码 PII 违反「敏感字段不进代码默认值」,且运维无从发现通知其实没发;B 样板与 `config.py` 有 8 项差额,部署不知道可调项;C 文档串与实际投影冲突(#PB-25 后未订正);D 并发撞唯一键对运营表现为「服务器内部错误」,既不可解释也无排障线索 | `project/docs/后端技术方案.md` §4.3 / §5.2 API-21+API-22 / §9.7；实现 `api-py/app/core/config.py`、`api-py/app/services/{internal_notify,merchant,merchant_binding}.py`、`api-py/.env.example`；用例 `api-py/tests/test_merchant_binding.py`(26 例)；派生视图 `docs/前后端对接方案.md` |
| 2026-09-16 | **任务行为语义字段 `actionType` / `actionParam` 接入（#PB-39；schema v1.11 / #DB-23）**：① ORM `SecondLevelTask` 补两列（`actionType VARCHAR(32) NOT NULL DEFAULT 'none'` / `actionParam VARCHAR(64) NULL`，与真源逐字一致）；② **单一投影** `app/services/task.py::second_level_dict` 在 `actionUrl` 之后带出两字段（纯增量、既有字段与顺序一个不改）⇒ 商家端 `GET /api/task/stages` 与管理端任务配置**同时生效**；③ 校验：`actionType` 只接受 **10 值枚举**（路由 `ActionType` Literal，与 `TaskType`/`CompletionType` 同一套校验通道），**参数规则 owner 在服务层** `admin_task_config.py::_assert_action_pair`（`data_form`/`data_upload` 必须带非空 `actionParam`；其余必须为空/NULL；部分更新按**与库内值合并后的有效组合**判定），违反 → **400 复用统一校验出口文案**「提交的内容有误，请检查后重试」（不新造句子）；④ 真源新增 **§8.3.9**（列定义 + 10 值枚举语义 + 参数规则 + 回填 10 组/51 行 + 边界与上线顺序）、API-03/API-04 扩展补 stages 投影、API-19 二级任务配置行标注、§9.7 本行 | 用户 2026-09-16 原话「给任务加 actionType 语义字段」；动因 = 任务卡行为由前端按 `taskId` 字面量硬编码（10 处判断 / 13 个任务），**改任务号必须改前端**（`#DB-22` 挪「签署协议」时暴露）。设计单 `dev-docs/任务单/action-type-design.md` 已评审、三条待拍板已裁决（阶段二+专区一并纳入 / 同时加 `actionParam` / 陈旧 `type`·`completionType` 枚举另立小单） | `project/docs/后端技术方案.md` §5.2 API-03+API-19 / §8.3.9 / §9.7；实现 `api-py/app/db/models/second_level_task.py`、`api-py/app/services/{task,admin_task_config}.py`、`api-py/app/api/v1/admin_task.py`；用例 `api-py/tests/test_task_action_type.py`（7 例）；派生视图 `docs/前后端对接方案.md` |
| 2026-09-16 | **`type` / `completionType` 枚举对齐开发库现实值（#PB-40，阻塞级修复；数据一行不动）**：① `TaskType` 由 3 值补为 **6 值**（`mandatory`/`suggested`/`guide` + **`form`/`jump`/`upload`**）、`CompletionType` 由 3 值补为 **5 值**（`system_check`/`manual_submit`/`click_read` + **`form_submit`/`file_upload`**），严格等于开发库 `SELECT DISTINCT`（既有值顺序不变、新值追加在后）；② 服务层新增同源元组 `TASK_TYPES`/`COMPLETION_TYPES` + 兜底守卫 `_assert_task_enums`（DTO 之外任何调用方都写不进越界值；非法 → **400 复用统一文案**）；③ 新增用例 4 例：**防漂移**（**库内取值 ⊆ 枚举**——越界即失败并指名；枚举值未被使用只记报告、**不失败**，见 #PB-40-R1 口径订正）、**同源**（Literal == 服务层元组）、**8 条越界行往返**（各自现值组合原样回传 → **200**，且真实行前后快照逐字段一致）、**未知值 → 400**（HTTP 两条路径 + 服务层守卫）；④ 真源新增 **§8.3.10**（两列现实取值 + 旧轴遗留说明 + 两道校验 + 防漂移 + 待办：`schema.sql` 列注释仍 3 值需 database 纯注释 MODIFY）、§9.7 本行 | #AF-20 用真实 UI + API 逐项证实：这 8 条任务（含 #PB-39 刚接入 `actionType` 的 6 条 `data_*`）**从管理后台保存必 400**（编辑表单把库内旧值原样回传，后端 Literal 不认）⇒ 阻塞级，不再是「文档漂移以后再说」。总控裁决：扩展枚举到现实值，**不改数据**；`form/upload/jump` 属旧轴遗留，**保留但登记**，行为语义以 `actionType` 为准 | `project/docs/后端技术方案.md` §8.3.10 / §9.7；实现 `api-py/app/api/v1/admin_task.py`、`api-py/app/services/admin_task_config.py`；用例 `api-py/tests/test_task_enums_aligned.py`（4 例）；派生视图 `docs/前后端对接方案.md` |
| 2026-09-16 | **阶段一任务序号同步（#PL-11）**：「签署协议」由 `T1.5.1` 调整为 **`T1.3.5`**（归属组 `T1.5`→`T1.3`、阶段 `opening`→`application`，位置移到「完成实名认证」之前），其后 `T1.3.5/6/7` 顺延为 `T1.3.6/7/8`；`T1.5` 组收拢为 3 个连续任务（`T1.5.1` 联系人信息及地址维护 / `T1.5.2` 开通京东钱包结算账户 / `T1.5.3` 缴费）。同步 §5.2 **API-09** 处「任务 `T1.3.7` 添加商家顾问催审」→ **`T1.3.8`**（仅改号，功能描述不变） | 用户裁决：签署协议前置到「完成实名认证」之前 | 阶段一任务编号与商家端任务卡展示；**开发库已执行（#DB-22），生产未执行** |


### 9.8 框架最大化利用原则

> 后端开发必须遵守。优先复用 FastAPI / Pydantic / SQLAlchemy 推荐机制，确需自定义时必须说明原因并更新本文档。

#### 9.8.1 强制复用清单

以下能力优先使用框架原生机制，禁止自己造轮子：

| 能力 | 框架机制 | 禁止行为 |
|------|---------|---------|
| HTTP 状态码 | `fastapi.HTTPException` / 业务异常 `ApiException`（`app/core/exceptions.py`） | 禁止手工拼 `JSONResponse(status_code=...)` 表达业务错误，禁止硬编码数字 |
| 参数校验 | Pydantic v2 模型 + FastAPI 自动校验 | 禁止在路由/service 里手写大段 if/else 校验参数 |
| 错误处理 | 全局异常处理器（`app/main.py`：`ApiException` / `RequestValidationError` / `HTTPException` / `Exception` 兜底） | 禁止在路由/service 里 try/except 后手工返回错误格式 |
| 路由分组 | `APIRouter(prefix=...)` + `app/api/router.py` 聚合 | 禁止在 `app/main.py` 里逐个注册业务路由 |
| 中间件 | `app.add_middleware(...)`（CORS 等） | 禁止在业务代码里直接操作 ASGI 协议细节 |
| 日志 | 标准库 `logging`（模块级 logger） | 禁止使用 `print` 输出运行日志 |
| 依赖注入 | `Depends(...)`（`get_db` / 鉴权 / 角色守卫） | 禁止在路由内手工创建数据库会话或手工解析 token |
| 配置管理 | pydantic-settings（`app/core/config.py` 的 `get_settings()`） | 禁止 `os.environ[...]` 散落代码、禁止硬编码密钥 |
| API 文档 | FastAPI 内建 OpenAPI（`/docs`、`/redoc`，仅 `DEBUG=true` 开放） | 禁止手写 Swagger YAML/JSON |
| 认证 | `get_current_merchant` / `get_current_admin` 依赖 + `require_roles` 守卫 | 禁止在路由内手工解析 JWT Token |

#### 9.8.2 自定义封装审批流程

确需自定义时，必须完成以下流程：

1. **说明原因**：为什么框架原生机制不能满足需求
2. **评估影响**：自定义封装对现有代码的影响范围
3. **最小实现**：只封装必要的逻辑，不过度抽象
4. **更新文档**：在本文档中登记自定义封装的文件、职责、使用方式
5. **提交代码**：commit message 中说明自定义原因

#### 9.8.3 自定义封装登记表

以下为已批准的自定义封装：

| 文件 | 自定义内容 | 框架原生替代方案 | 为什么不用原生 | 登记日期 |
|------|-----------|----------------|--------------|---------|
| app/core/response.py | 统一响应 `{code,message,data}` 包装 | 无（FastAPI 不约束响应体结构） | 契约要求，对齐前端既有约定 | 2026-09-10 |
| app/core/exceptions.py | 业务异常 `ApiException`（message + code + status_code） | `fastapi.HTTPException` | 需要业务错误码与 HTTP 状态解耦，并由全局处理器统一转响应 | 2026-09-10 |
| app/main.py（异常处理器） | 校验失败只返回首个错误；未知异常兜底 500 | FastAPI 默认 `RequestValidationError` 响应体（含全部错误明细） | 契约要求不暴露全部校验规则 | 2026-09-10 |
| app/core/timeutil.py | datetime -> ISO8601 毫秒 + `Z` | 无 | 契约要求的时间格式（前端解析口径） | 2026-09-10 |
| app/api/deps.py | 商家/管理员双 secret 鉴权 + 角色守卫依赖 | `OAuth2PasswordBearer` / 通用 JWT 中间件 | 需商家与 admin token 双 secret 隔离，且管理员需按库校验 status | 2026-09-10 |
| app/db/models/*.py | ORM 显式声明索引名 `Index(...)` | 列级 `index=True`（自动命名） | 索引名必须与实库/`schema.sql` 一致，否则结构校验报 `remove_index` | 2026-09-10 |

#### 9.8.4 禁止行为

| 禁止行为 | 原因 |
|----------|------|
| 手工拼 `{"code": 500, "message": ...}` 返回 | 应抛出 `ApiException` / `HTTPException`，由全局异常处理器统一处理 |
| 在路由里写 if/else 校验参数 | 应使用 Pydantic 模型/类型注解，由 FastAPI 自动校验 |
| 在 service 里 try/except 后 return `{code, message}` | 应抛出异常，由全局异常处理器统一处理 |
| `print('xxx')` | 应使用 `logging.getLogger(...).info('xxx')` |
| 在路由内 `SessionLocal()` 手工建会话 | 应通过 `Depends(get_db)` 注入 |
| `os.environ["DB_HOST"]` 直接使用 | 应通过 `get_settings()` 读取 |

### 9.9 开发前置检查清单

> 后端开发必须先读取并遵守本文档。新增或修改后端功能前，必须完成以下检查。

#### 9.9.1 开发前必读

每次新增或修改后端功能前，必须读取本文档以下章节：

| 章节 | 检查内容 |
|------|---------|
| §三 目录规范 | 新文件放在哪个目录，是否符合"业务域 = service 文件 + 路由文件" |
| §四 统一响应格式 | 返回值格式是否符合 `{code, message, data}` 规范 |
| §五 API 接口规范 | 接口路径、参数、权限是否与文档一致 |
| §8.3 数据库/迁移/结构校验 | 是否只做结构校验（禁止 autogenerate 执行）；ORM 声明是否与真源对齐 |
| §9.6 框架最佳实践 | P1-P10 是否全部满足 |
| §9.8 框架最大化利用 | 是否优先复用框架机制 |

#### 9.9.2 新增功能检查清单

- [ ] 新文件放在 `app/services/` 与 `app/api/v1/` 下
- [ ] 路由不写业务逻辑
- [ ] Service 不循环依赖其他 Service
- [ ] ORM 模型不跨域直接引用
- [ ] 请求/响应有 Pydantic 模型或类型注解
- [ ] 异常抛 `ApiException`，不手工拼错误响应
- [ ] 日志用 `logging`，不用 `print`
- [ ] 配置从 `get_settings()` 读，不硬编码
- [ ] 返回值由统一响应助手包装，不手工拼 `{code, message}`
- [ ] 新增/调整的 ORM 声明已与 `project/scripts/schema.sql` 对齐（只读对账 `uv run alembic current`）

#### 9.9.3 变更审批清单

以下变更必须先说明原因，并同步更新本文档：

| 变更类型 | 必须更新的章节 |
|----------|--------------|
| 新增业务域 | §三 目录规范 |
| 新增 API | §五 接口清单 |
| 新增依赖 | §2.2 依赖清单 + §9.2 |
| 自定义封装 | §9.8.3 自定义封装登记表 |
| 目录调整 | §三 目录规范 |
| 框架更换 | §1 技术栈 + §9.5 |
| 错误码变更 | §4.3 失败场景 + §9.4 |
| 数据库结构 / ORM 结构声明 | §8.3 数据库 / 迁移 / 结构校验 |

---

## 十、AI 经营分析（#B-006 新增）

> **变更原因（文档先行）**：阶段二数据看板需要基于商家已上传的 `shop_*` 数据给出经营解读与建议。原方案 §2.2 已将 AI 大模型列为 V2 预埋；因阶段二 T2.5 数据上传已落地，本功能提前到当前阶段实现。本次为 **AI 尝试（调用大模型推理）**，非 AI 训练：不将商家数据用于训练。

### 10.1 接口定义（API-15）

```
POST /api/shop/analysis?time_range=yesterday|7d|30d
```

| 维度 | 内容 |
|------|------|
| 功能 | 基于该商家已上传的 shop_* 聚合指标，调用大模型生成经营分析 |
| 响应 | `{ summary: string, strengths: [{ point, reason }], weaknesses: [{ point, reason }], suggestions: [{ action, priority }] }` |
| 无数据 | 不调用大模型，返回 `{ summary: null, strengths: [], weaknesses: [], suggestions: [], message: "暂无已上传的经营数据，请先完成数据上传" }` |
| 失败处理 | **按错误码细分（#PB-31 按实现回写；文案单一真源 = `app/services/ai.py::error_message_for_code`，状态码映射 = 同文件 `_raise_from_code`，本文只登记、不另写一套）**：`LLM_TIMEOUT` → **504**「AI 分析超时，请稍后重试」；`LLM_HTTP_429`（上游限流）→ **429**「AI 服务繁忙，请稍后重试」；其余失败 → **502**，其中 `LLM_EMPTY_RESPONSE`/`LLM_PARSE_FAILED` → 「AI 分析结果异常，请稍后重试」、未配置 → 「AI 服务未配置，请联系管理员」、网络异常 → 「网络连接失败，请检查网络后重试」、未知兜底 → 「AI 分析失败，请稍后重试」。失败不阻塞看板（前端直接展示 `message`）；主图/标题优化同映射。**上游空响应（`LLM_EMPTY_RESPONSE`）自动重试 1 次**（#PB-35，实现在 `_post_chat` 外壳，三入口共用）：重试**只用剩余超时预算**，总耗时上界仍为入口 `timeout_ms`（硬上界：总调用 ≤ 2 次），剩余低于 `_EMPTY_RETRY_MIN_BUDGET_MS`（1000ms）即不重试、按原错误码返回；**其余错误码（429 / 超时 / 网络 / 5xx / 解析失败）一律不重试**。 |
| 权限校验 | 需要 JWT Token + 阶段二已解锁（否则 403）；仅返回该商家本人数据 |
| 参数校验 | `time_range` **必填**（不传即非法），取值 `yesterday`/`7d`/`30d`；非法值 → **400 中文专句**「时间范围不支持，请使用 昨天 / 近7天 / 近30天」（与 API-14 **共用同一常量** `app/services/shop.py::TIME_RANGE_INVALID_MESSAGE`，禁止两处各拼一句）；校验先于限流与阶段二门禁 |
| 限流 | 每商家每日 N 次成功调用（默认 3，`AI_DAILY_LIMIT` 可配），失败不计数、允许重试；缓存命中不计数；超出返回 429；手动触发为主，无自动任务 |
| 超时 | 单次调用超时 120s（推理模型响应较慢，实测约 30-40s），超时按 502 可读提示处理 |

### 10.2 供应商与配置

- 调用方式：OpenAI 兼容 `chat/completions`，由 `httpx` 直接 POST 实现（**未新增依赖**，见 `app/services/ai.py`）。
- 环境变量（写在 `api-py/.env`，gitignore 覆盖，代码与文档不回显密钥）：
  - `AI_API_KEY`：大模型 API Key
  - `AI_BASE_URL`：OpenAI 兼容网关地址（默认 `https://note3-prev-api.askdiandian.com/v1`）
  - `AI_MODEL`：模型名（默认 `dots3-note-prev`）
  - `AI_DAILY_LIMIT`：每商家每日分析次数上限（默认 3）
  - `AI_TIMEOUT_MS`：AI 调用超时毫秒数（默认 120000）
- 密钥管理：禁止硬编码、禁止入库、禁止写入日志。

### 10.3 提示词规则

- 角色：拍拍二手商家经营顾问。
- 输入：该商家聚合指标（星级 4 因子、交易、流量、商品、数量、健康分，字段与 summary 接口一致）；**送模型前键一律中文化**（#PB-32，名册见 §10.6），时间维度用中文口径（昨天/近7天/近30天）。
- 输出（JSON）：现状总结 `summary`；做得好 `strengths`（含依据 `reason`）；不足 `weaknesses`（含依据 `reason`）；可执行建议 `suggestions`（按优先级 `priority` 排序）。
- 仅发送该商家本人的聚合经营指标，不含明文 PII 与其他商家数据。

### 10.4 成本与限流说明

- 单次调用 token 估算：提示词（固定指令 + 指标数据）约 1-2k tokens，输出约 500-800 tokens，合计约 2-3k tokens/次。
- 每商家每日上限 N 次**成功**调用（默认 3），失败不计数、允许重试；缓存命中不计数；超出 429。实际费用按 LLM 供应商计费口径结算，日上限用于控制成本。
- 调用记录写入 `ai_analysis_log`（merchant_id、status、error_message、created_at，迁移新增），用于限流计数与审计。

### 10.5 AI 结果缓存与体验优化（#B-007）

- **结果缓存**：同一商家同一 `time_range` 当日重复请求直接命中缓存（进程内 Map，key=`merchantId:timeRange:日期`），不再重复调用大模型、不计数、无 token 成本。
- **失效策略**：① 当日有效，跨日自动失效（key 含日期）；② 该商家任一 `shop_*` 数据上传/更新后立即清除缓存（下次请求重新生成）；③ 进程重启缓存失效（单机部署可接受）。
- **流式输出评估**：暂不启用。理由：当前输出为结构化 JSON，需完整响应后解析；前端已有加载遮罩并接受 20-54s 等待；流式需前后端同时改造（SSE/流式解析），收益有限。列为后续优化项。
- **更快的模型评估**：当前 `dots3-note-prev` 为轻量档；实测分析耗时约 30-40s，主要耗时来自推理 token。可通过 `AI_MODEL` 切换更快模型，但需权衡分析质量；建议保留当前模型，延迟不可接受时再评估。
- **超时配置**：`AI_TIMEOUT_MS` 可调（默认 120000ms），超时按 502 可读提示处理。
- **成本口径**：单次调用 token = prompt + completion + reasoning（该模型返回 `reasoning_tokens`，实测简单请求 ~100 tokens、分析请求以数百到上千计）；费用按 LLM 供应商计费结算；每商家每日成功调用上限 + 缓存兜底，成本可控。

### 10.6 指标中文名册（#PB-32 经营分析 · #PB-33 标题优化；AI 输出不得出现英文字段名）

> 背景（用户 2026-09-15 / #PB-32）：「**AI 经营分析出来的内容，里面有英文字段名，需要把英文字段名都调整成中文，例如 `health_score` 应该为健康评分**」。根因（已复核）：`analyze()` 把 `GET /api/shop/summary` 的英文键原样 JSON 化塞进 user prompt（`app/services/ai.py:178`），模型照着英文键作答；`SYSTEM_PROMPT_ANALYSIS` 也未禁止英文字段名。
>
> **用词终局（#PB-33 用户裁决）**：`health_score` 的中文名**统一取「商品信息健康分」**——用户原话「前端看板那个区块标题是「商品信息健康分」 叫这个」；#PB-32 曾暂用的「健康评分」**已废**（引用保留仅为追溯历史）。

**单一真源**：`api-py/app/services/metric_labels.py`（`SECTION_LABELS` / `GENERIC_LABELS` / `METRIC_LABELS` / `TIME_RANGE_LABELS` / `TITLE_FIELD_LABELS`）。指标名用词逐项对齐**前端既有名册** `project/src/constants/stage2.ts::SHOP_METRIC_LABELS`（44 键，只读参考、不改前端）；区段名对齐同文件 `SHOP_SUMMARY_TYPES`，**`health_score` 亦已字面一致（「商品信息健康分」，#PB-33）——本名册与前端名册之间现存 0 处用词差异**。

| 键（后端字段名） | 中文指标名 | 类型 |
|------|-----------|------|
| `star` | 店铺星级 | 顶层区段键 |
| `trade` | 交易数据 | 顶层区段键 |
| `traffic` | 流量数据 | 顶层区段键 |
| `product` | 商品数据 | 顶层区段键 |
| `product_count` | 商品数量 | 顶层区段键 |
| `health_score` | 商品信息健康分 | 顶层区段键 |
| `data_date` | 数据日期 | 通用键 |
| `time_range` | 时间范围 | 通用键 |
| `shop_star` | 店铺星级 | 指标键 |
| `service_score` | 客服咨询因子 | 指标键 |
| `logistics_score` | 物流履约因子 | 指标键 |
| `after_sale_score` | 售后服务因子 | 指标键 |
| `product_score` | 商品体验因子 | 指标键 |
| `trade_amount` | 成交金额 | 指标键 |
| `trade_orders` | 成交单量 | 指标键 |
| `trade_customers` | 成交客户数 | 指标键 |
| `shop_visitors` | 店铺访客数 | 指标键 |
| `shop_page_views` | 店铺浏览量 | 指标键 |
| `trade_items` | 成交商品件数 | 指标键 |
| `conversion_rate` | 成交转化率 | 指标键 |
| `customer_unit_price` | 客单价 | 指标键 |
| `avg_stay_duration` | 平均停留时长 | 指标键 |
| `cart_customers` | 加购客户数 | 指标键 |
| `cart_items` | 加购商品件数 | 指标键 |
| `cart_conversion_rate` | 加购转化率 | 指标键 |
| `product_visitors` | 商品访客数 | 指标键 |
| `product_page_views` | 商品浏览量 | 指标键 |
| `product_avg_page_views` | 商品人均浏览量 | 指标键 |
| `product_avg_stay_duration` | 商品平均停留时长 | 指标键 |
| `uv_value` | UV价值 | 指标键 |
| `product_exposure_count` | 商品曝光次数 | 指标键 |
| `product_exposure_users` | 商品曝光人数 | 指标键 |
| `cart_amount` | 加购金额 | 指标键 |
| `trade_conversion_rate` | 成交转化率 | 指标键 |
| `active_spu_count` | 动销SPU数 | 指标键 |
| `spu_active_rate` | SPU动销率 | 指标键 |
| `item_unit_price` | 件单价 | 指标键 |
| `cart_spu_count` | 加购SPU数 | 指标键 |
| `spu_cart_rate` | SPU加购率 | 指标键 |
| `visit_spu_count` | 访问SPU数 | 指标键 |
| `listed_spu_count` | 上架SPU数 | 指标键 |
| `total_count` | 全部商品数量 | 指标键 |
| `on_sale_count` | 售卖中商品数量 | 指标键 |
| `off_sale_count` | 已下架商品数量 | 指标键 |
| `audit_count` | 商品审核中数量 | 指标键 |
| `avg_score` | 店铺平均信息分 | 指标键 |
| `score_gte_90_count` | 信息分≥90 商品数 | 指标键 |
| `score_78_90_count` | 信息分 78-90 商品数 | 指标键 |
| `score_60_77_count` | 信息分 60-77 商品数 | 指标键 |
| `score_lt_60_count` | 信息分 <60 商品数 | 指标键 |

时间维度取值（`TIME_RANGE_LABELS`）：`yesterday` → 昨天 / `7d` → 近7天 / `30d` → 近30天
**标题优化入参名册（`TITLE_FIELD_LABELS`，#PB-33）**

| 入参键（camelCase） | 中文名 | 用词来源 |
|------|--------|---------|
| `mode` | 模式 | 前端无同名标签，后端定名 |
| `category` | 类目 | 前端无同名标签，后端定名 |
| `brand` | 品牌 | 前端面板字段标签 |
| `model` | 型号 | 前端面板字段标签 |
| `features` | 产品特点 | 前端面板字段标签 |
| `condition` | 成色 | 前端面板字段标签 |
| `keyAttrs` | 关键属性 | 前端面板字段标签 |
| `saleAttrs` | 销售属性 | 前端面板字段标签 |
| `currentTitle` | 现有标题 | 前端面板字段标签（任务单示例曾写「当前标题」，同义词；此处以前端可见文案为准） |

- **键集合穷尽性**：= `app/api/v1/shop.py::TitleOptBody` 的 9 个字段；用例 `test_title_field_labels_cover_title_opt_body` 断言与名册差集为空（多余/漏登记均失败）。
- **只换键、不动结构与值**：`localized_title_input()` 逐键中文化；`mode` 的**取值**仍是 `generate`/`optimize`（值不变口径；如需连取值也中文化，另立单）。
- **系统提示**：`SYSTEM_PROMPT_TITLE`（新增）要求「输出中一律使用中文，禁止出现英文字段名或 camelCase 字段名（如 keyAttrs、currentTitle、saleAttrs）」；**JSON 键名固定 `spuTitle`/`skuTitle`/`notes`（响应契约，不得改）**。

**规则（实现口径）**

1. **只换键、不动结构与值**：送模型的汇总数据由 `localized_summary()` 逐键中文化（层级与数值不变，`null` 语义不变）；prompt 的时间维度文案用中文口径（`yesterday`→昨天 / `7d`→近7天 / `30d`→近30天）。
2. **硬要求进系统提示**：`SYSTEM_PROMPT_ANALYSIS` 明确「内容文本一律使用中文指标名；禁止出现英文字段名或下划线命名（如 `health_score`、`trade_amount`、`avg_score`、`shop_star`）」；`SYSTEM_PROMPT_TITLE` 同口径禁止 camelCase 字段名；**两份响应的 JSON 键名均为契约（`summary/strengths/…` 与 `spuTitle/skuTitle/notes`），不得改**（响应结构、错误码、既有文案均不变）。
3. **覆盖与对齐由用例守着**：`api-py/tests/test_ai_prompt_labels.py` —— ① 名册与 `get_summary` 实际键集合差集必须为空（当前 50 键）；② 名册与 `TitleOptBody` 字段集合差集必须为空（9 键）；③ 实际送模型的 system/user prompt 中，`snake_case` 命中为 0、标题优化 user prompt 中 camelCase **键位置**命中为 0 且 9 个 camelCase 字段名整体不出现（宽正则对取值里的品牌型号名如 `iPhone` 会误报，故以键位置为准）；④ 指标名与前端名册逐项一致、区段名（含 `health_score`）与前端 `SHOP_SUMMARY_TYPES` 字面一致。
4. **变更联动**：`shop_*` 汇总新增/改名字段时，必须同步本表与前端 `SHOP_METRIC_LABELS`；任一侧漏改，上述用例即变红。
5. **兜底**：2026-09-15 真实调用 3 次（`dots3-note-prev`）实测**无英文字段名残留**，故**未加**确定性后处理替换；若将来模型回退出现残留，再按本表加键→中文替换并在此登记。
6. **标题优化同源**：`optimize_title()` 与经营分析共用「只换键 + 系统提示硬要求」模式（#PB-33）；`ImageOptimize` 只送图片与一句指令、**不含字段键**，无需名册。

### 10.7 提示词与名册的边界（#PB-32 登记 · #PB-33 已治理）

- **标题优化（`optimize_title`）：#PB-33 已治理** —— 入参键经 `TITLE_FIELD_LABELS` 中文化、系统提示 `SYSTEM_PROMPT_TITLE` 禁止 camelCase 字段名（名册与穷尽性见 §10.6）。此前 #PB-32 登记的「同类隐患」**已关闭**。
- **主图优化（`IMAGE_OPT_SYSTEM_PROMPT`）**：只发送一句中文指令 + 图片（`content=[text, image_url]`），**不发送任何字段键**，故无需名册；其输出 JSON 键（`summary/compliance/issues/plan`）为响应契约。
- **仍未治理的同类面（如需请另立单）**：`mode` 等**枚举取值**仍是英文（`generate`/`optimize`），当前口径是「只换键、值不变」；连取值也中文化属新口径。
