# api-py · 商家成长任务体系 Python/FastAPI 后端

> 迁移自 NestJS backend,接口契约(/api/*)一致,前端零改动。
> 阶段定位(按 R71 方案):阶段0 = 环境 + FastAPI 骨架 + Alembic + 连库 + /health。

## 技术栈

FastAPI + SQLAlchemy 2.0(同步)+ PyMySQL + Pydantic v2 + python-jose + passlib + slowapi + Alembic + openpyxl + lark-oapi + httpx(Python 3.12 + uv)

## 目录结构

```
api-py/
├── app/
│   ├── main.py            # FastAPI 实例 + CORS + 全局异常 + /health
│   ├── api/
│   │   └── router.py      # 路由聚合(/api 前缀)
│   ├── core/
│   │   ├── config.py      # 配置(pydantic-settings,读 .env)
│   │   ├── response.py    # 统一响应 {code,message,data}
│   │   └── exceptions.py  # 业务异常 ApiException
│   └── db/
│       ├── engine.py      # SQLAlchemy 引擎(读 .env 连库)
│       ├── session.py     # get_db 依赖
│       └── base.py        # DeclarativeBase
├── alembic/               # 迁移(只做结构一致校验,不 alter 生产表)
├── .env.example           # 环境变量示例(不入库)
├── .env                   # 本地配置(已 gitignore,不入库)
└── pyproject.toml         # 依赖清单(uv 管理)
```

## 本地运行

```bash
cd api-py
cp .env.example .env        # 按需改 DB_*
uv sync                     # 建 .venv 并安装依赖
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

> 后端**未启用 `--reload`**：改动 `app/` 下代码后必须手动重启 uvicorn，否则继续跑旧代码。
> 仅本地临时调试可自行加 `--reload`，部署环境一律不加。

- Swagger:    http://127.0.0.1:8000/docs（仅 DEBUG=true 开放；DEBUG=false 时 404）
- ReDoc:      http://127.0.0.1:8000/redoc

## 登录模式（SEC-01，生产必读）

- `LOGIN_MODE`（.env）：`mock` = 本地开发（固定返回 `mock_merchant_001` token）；`real` = 真实飞书 OAuth 登录。
- **生产必须 `LOGIN_MODE=real`** 且配置真实 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`。`mock` 会让公网未登录即可拿到商家 token，越权访问 `get_current_merchant` 接口（SEC-01）。
- `LOGIN_MODE=real` 且 `FEISHU_APP_SECRET` 缺失/占位 → 启动后登录直接报 502（fail-fast，绝不静默降级 mock）。
- 真实登录流程（`app/services/feishu.py` `login_feishu`，2026-09-14 生产实测口径）：`POST /open-apis/auth/v3/app_access_token/internal` 取 app_access_token（进程内缓存）→ `POST /open-apis/authen/v1/oidc/access_token` 换 user_access_token（**必须带 `Authorization: Bearer <app_access_token>`**；缺该头飞书返回 `code=20014`）→ `GET /open-apis/authen/v1/user_info`（Bearer = user access_token）取 open_id/union_id/name。

## 静态资源(顾问企微二维码)

前端 `<img src="/api/static/advisor-qr.jpg">` 与 `GET /api/feishu/advisor-qr` 的 `qr_url` 都指向
`GET /api/static/advisor-qr.jpg`。该端点**只服务一个固定文件**,路径由 `ADVISOR_QR_FILE` 配置
(默认 `static/advisor-qr.jpg`,相对 api-py 根目录):

- 把商家顾问企微二维码图片放到 `api-py/static/advisor-qr.jpg`(真实图片不入库,目录已用 `.gitkeep` 占位);
- 未放置时该端点返回**结构化 404**「顾问二维码未配置」;配置越界/文件不可读返回**结构化 500**(不回显绝对路径);
- 无需登录(前端图片请求无法携带 token)。

## 数据库

连接参数在 `.env`(DB_HOST/DB_PORT/DB_USER/DB_PASS/DB_NAME)。默认开发连本地 MySQL
`merchant_task`;Docker MySQL 服务器 `<SERVER_IP>:3307`(库 `merchant_task_prod`)改 .env 即可。

## Alembic

仅用于结构一致校验,不 alter 生产表。`cd api-py && uv run alembic current` 联库查看当前版本。
