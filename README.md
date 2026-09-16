# Online-taskpaipai · 商家成长任务体系

> 京东拍拍二手 · 商家成长任务体系（三端开源实现）
> An open-source implementation of a merchant-growth task system: H5 app, admin console and FastAPI backend.

## 这是什么

面向**京东拍拍二手**商家的「成长任务体系」：商家在 H5 端按阶段完成任务（入驻准备 → 开店搭建 → 品牌 / 商品发布 / 优化 / 活动），
平台侧用管理后台配置任务、查看进度、处理反馈与数据分析；后端提供任务 / 进度 / 店铺数据 / 类目 / 费用 / AI 辅助等能力。

## 三端与技术栈

| 端 | 目录 | 技术栈 |
|----|------|--------|
| 商家端 H5（移动端 + PC Web） | `project/` | uni-app + Vue 3 + TypeScript + SCSS + uview-plus + Pinia |
| 管理后台（PC Web） | `admin/` | Vue 3 + Element Plus + Pinia + axios + Vite |
| 后端 API | `api-py/` | Python 3.12 + FastAPI + SQLAlchemy 2.0（同步）+ PyMySQL + Pydantic v2 + Alembic |
| 数据库 | `project/scripts/schema.sql` | MySQL 8.0（表结构真源，勿手改） |
| 资费同步自动化 | `automation/` | Node.js + Playwright（月度定时任务） |

## 目录结构

```
api-py/                 # 后端（FastAPI）：app/ 服务与路由、scripts/ 门禁脚本、tests/ 用例
admin/                  # 管理后台（Vue 3 + Element Plus）
project/                # 商家端 H5（uni-app）；scripts/schema.sql 为表结构真源
automation/             # 资费同步等运维自动化脚本
scripts/                # 仓库级辅助脚本
governance/             # 规范与治理文档（先看 governance/README.md）
package.json            # 统一验收入口（npm run verify）
```

## 快速开始

### 后端（api-py）

```bash
cd api-py
cp .env.example .env          # 按注释填写本地配置
uv sync                       # 安装依赖（需 uv）
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- 健康检查：`GET http://127.0.0.1:8000/health`
- 接口文档：`DEBUG=true` 时开 `/docs`（生产关闭）
- 测试：`uv run python -m pytest tests/ -q`

### 管理后台（admin）

```bash
cd admin
npm install
npm run dev      # 开发（默认 5174）
npm run build    # 生产构建
```

### 商家端 H5（project）

```bash
cd project
npm install
npm run dev:h5   # 开发（默认 5173）
npm run build:h5 # 生产构建
```

前端可配置的环境变量见 `project/.env.example`。

## 质量门禁

仓库根目录提供统一验收入口（约 5–6 分钟）：

```bash
npm run verify
```

链路 = 后端可编译 / 可导入 → 管理后台构建 → 商家端构建 → **数据库三门禁** → **pytest 全量**：

- `api-py/scripts/check_schema.py`：`schema.sql` 真源 ↔ 实库结构硬对账
- `api-py/scripts/check_data_encoding.py`：双重编码乱码巡检
- `api-py/scripts/check_orphan.py`：`merchant_id` 孤儿只读巡检
- `uv run python -m pytest tests/ -q`：后端全量用例

## 规范与治理

所有**规则、规范与产品真源**集中在 `governance/`，入口见 **`governance/README.md`**：

- `governance/AGENTS.md`：项目宪法（边界、真源优先级、owner 映射、验收规则、git 规则）
- `governance/agent/`：协作与流程规则（铁律、协作体系、部署确认闸、角色卡）
- `governance/product/`：产品与技术真源（设计规范、前端开发规则、后端技术方案、后台开发标准、阶段体系、接口对接手册）

## 关于本仓库（开源导出说明）

本仓库是从内部工程仓库导出的**脱敏子集**，用于开源展示与协作：

- **不包含**：生产环境配置与凭据、数据库备份与导出、运维拓扑、内部工作记录与验收证据；
- 文档与示例中的服务器地址、账号标识、业务 ID 等**已替换为占位符**（如 `<SERVER_IP>`、`<OPEN_ID>`、`<MERCHANT_ID>`）；
- 部署与运维相关的**真实参数**请自行按 `governance/agent/deployment-gate.md` 的流程在自有环境配置；
- 若发现任何不应公开的内容，欢迎提 issue 或直接联系维护者，我们会立即处理。

## 许可

暂未附带开源许可证文件；如需使用请先与维护者联系。
