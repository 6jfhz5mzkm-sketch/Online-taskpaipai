# governance · 规范与治理

本目录收录本项目的**规则、规范与产品真源**，供统一查阅。
它们是长期演进的工程约定；**冲突时按「项目宪法 > 协作铁律 > 各角色卡」的顺序裁决**。

## 建议阅读顺序

1. `AGENTS.md` —— 项目宪法：项目边界、真源优先级、必需工作流、owner 映射、验收与 git 规则
2. `agent/iron-rules.md` —— 协作铁律：调度与执行纪律、临时实体与端口纪律、git 授权规则
3. `agent/deployment-gate.md` —— 生产部署确认闸：预览 → 用户人眼确认 → 部署 → 上线后验证
4. `product/backend-spec.md` —— **后端唯一真源**：API 边界、业务规则、目录规范、变更管理
5. `product/design-system.md` / `product/frontend-rules.md` —— 前端设计 Token 与开发规则
6. 其余按需：后台开发标准、阶段体系、数据分析专区、接口对接手册

## 文件清单与来源映射

> 本仓库为脱敏导出，目录名与文件名已改为英文；下表给出与内部原始路径的对应关系，便于对照与追溯。

| 本仓库路径 | 内部原始路径 | 说明 |
|-----------|-------------|------|
| `governance/AGENTS.md` | `AGENTS.md` | 项目宪法（最高准则） |
| `governance/agent/iron-rules.md` | `dev-docs/铁律.md` | 协作铁律 |
| `governance/agent/collaboration.md` | `dev-docs/Agent协作体系.md` | 多 Agent 协作体系与派单 / 汇报模板 |
| `governance/agent/deployment-gate.md` | `dev-docs/部署规则.md` | 生产部署确认闸（独立成文） |
| `governance/agent/roles/*.md` | `dev-docs/agents/*.md` | 各角色卡（职责 / 边界 / 交付标准） |
| `governance/product/design-system.md` | `project/docs/设计规范.md` | 视觉规范与设计 Token |
| `governance/product/frontend-rules.md` | `project/docs/开发规则.md` | 前端框架 / 目录 / 组件复用 / 硬性禁令 |
| `governance/product/backend-spec.md` | `project/docs/后端技术方案.md` | **接口与业务规则唯一真源** |
| `governance/product/admin-console-standard.md` | `project/docs/任务管理后台开发标准.md` | 管理后台开发标准 |
| `governance/product/data-center-spec.md` | `project/docs/数据分析专区方案.md` | 数据分析专区方案 |
| `governance/product/stage2-task-system.md` | `project/docs/阶段二任务体系.md` | 阶段二任务体系 |
| `governance/product/stage-isolation-rules.md` | `project/docs/阶段隔离规则与阶段二任务清单.md` | 阶段隔离规则与任务清单 |
| `governance/product/api-integration-handbook.md` | `docs/前后端对接方案.md` | 前后端对接手册（派生视图，真源仍为后端技术方案） |

## 脱敏说明

本目录内容在导出时做过**逐份脱敏**（不改变任何规则语义）：

| 处置 | 说明 |
|------|------|
| `<SERVER_IP>` / `<SERVER_ROOT>` / `<DEPLOY_ROOT>` | 服务器地址、部署根目录、运维路径 |
| `<OPEN_ID>` / `<FEISHU_APP_ID>` / `<INTERNAL_EMAIL>` | 内部账号标识与联系方式 |
| `<MERCHANT_ID>` / `<JD_MERCHANT_ID>` / `<PHONE>` | 业务侧真实标识 |
| **未收录** | 生产部署方案与拓扑、数据库备份、验收证据、内部任务单与进度记录、线程登记 |

## 参与与反馈

- 规范变更建议请走 issue / PR，并在 PR 描述里写明：**为什么现有规则不够 + 影响哪些行为 + 如何验证**；
- 发现任何不应公开的内容（凭据、真实标识、内部拓扑），请直接提 issue，我们会立即处理。
