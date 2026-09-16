# 商家成长任务体系 — 开发规则

> 本文件是项目的唯一开发规范来源。所有代码必须遵守以下规则。

---

## 一、技术栈

| 项目 | 选型 |
|------|------|
| 框架 | uni-app + Vue 3 Composition API |
| 组件库 | uview-plus（唯一，禁止引入第二个） |
| 状态管理 | Pinia |
| 语言 | TypeScript + SCSS |
| 包管理 | npm |
| 平台 | 商家端 H5（PC Web + 移动端同等重要）；无小程序 / 原生 App 目标 |

---

## 二、目录结构

```
src/
├── pages/                          ← 页面（按业务模块分文件夹）
│   └── 模块名/
│       ├── index.vue               ← 列表/首页
│       ├── detail.vue              ← 详情页
│       └── ...
│
├── components/                     ← 全局公共组件（跨页面复用）
│   └── 组件名/
│       ├── index.vue
│       └── README.md               ← 组件说明（props/事件/示例）
│
├── components-local/               ← 页面级私有组件（仅某页面内重复）
│   └── 页面模块名/
│       └── 组件名.vue
│
├── api/                            ← 接口请求（按业务模块拆文件，不在此写死清单）
│   ├── index.ts                    ← 统一导出
│   ├── request.ts                  ← 请求封装（BASE_URL + Token 拦截器）
│   └── <业务模块>.ts                ← 例：stage2.ts（阶段/任务接口按模块命名）
│
├── utils/                          ← 工具函数（纯函数，无 UI）
│   ├── index.ts                    ← 统一导出
│   ├── format.ts                   ← 格式化
│   ├── validate.ts                 ← 校验
│   └── ...
│
├── store/                          ← 状态管理（Pinia）
│   ├── index.ts
│   └── modules/
│       ├── user.ts
│       ├── task.ts                 ← 阶段/任务与进度状态（进度同时落后端与本地缓存）
│       └── ...
│
├── types/                          ← TypeScript 类型定义
│   ├── index.ts
│   ├── task.ts
│   ├── user.ts
│   └── ...
│
├── constants/                      ← 常量 / 枚举
│   ├── index.ts
│   ├── task.ts
│   └── ...
│
├── styles/                         ← 样式
│   ├── tokens/                     ← 设计 Token（详见《设计规范》）
│   │   ├── _colors.scss
│   │   ├── _typography.scss
│   │   ├── _spacing.scss
│   │   ├── _radius.scss
│   │   ├── _shadow.scss
│   │   ├── _transition.scss
│   │   └── _index.scss
│   ├── mixins/                     ← SCSS 混入
│   │   └── flex.scss
│   └── global.scss                 ← 全局公共样式
│
├── static/                         ← 静态资源（不编译）
│   └── images/
│       ├── tabbar/                 ← TabBar 图标
│       └── icons/                  ← 通用图标
│
├── pages.json                      ← 页面路由配置
├── manifest.json                   ← 应用配置
├── App.vue                         ← 根组件 + 全局 CSS Variables
├── main.ts                         ← 入口文件
└── uni.scss                        ← 全局 SCSS 入口
```

---

## 三、文件归属规则

| 文件类型 | 存放位置 | 命名规则 | 违规示例 ❌ |
|----------|----------|----------|------------|
| 页面 | `src/pages/模块名/` | `index.vue` 或 `detail.vue` | 放在 `src/views/` 或根目录 |
| 全局组件 | `src/components/组件名/` | PascalCase 文件夹 + `index.vue` | 放在页面目录里 |
| 页面私有组件 | `src/components-local/页面模块/` | PascalCase | 放在 `components/` 里 |
| 接口请求 | `src/api/` | 按业务模块拆文件 | 散落在组件里直接 fetch |
| 工具函数 | `src/utils/` | 按功能拆文件 | 写在组件内部 |
| 状态管理 | `src/store/modules/` | 按业务模块拆文件 | 组件内 reactive 管全局状态 |
| 类型定义 | `src/types/` | 按业务模块拆文件 | 类型写在 `.vue` 文件里 |
| 常量枚举 | `src/constants/` | 按业务模块拆文件 | 魔法数字散落组件中 |
| 静态资源 | `src/static/images/分类/` | 按类型分文件夹 | 图片放 public/ 或组件旁边 |
| 设计 Token | `src/styles/tokens/` | `_xxx.scss` | Token 写在页面 `<style>` 里 |

---

## 四、组件复用规则

### 4.1 触发条件

**同一形式出现次数 ≥ 2 次 → 必须封装**

不管差异多小（文案不同、颜色不同、数据不同），都要封装，用 props 区分。

### 4.2 封装决策流程

```
看到重复 UI →
  ├── 形状相同，只是内容不同？ → 封装，用 props 传内容
  ├── 形状相同，只是颜色不同？ → 封装，用 props 或 type 控制
  ├── 形状相同，只是显隐不同？ → 封装，用 v-if/v-show 控制
  └── 形状完全不同？           → 不封装，但确认是否真的不同
```

### 4.3 封装位置

- 2 个以上页面用到 → `src/components/`（全局组件）
- 仅某页面内重复 → `src/components-local/页面名/`（页面私有组件）

### 4.4 命名规范

- 文件夹：PascalCase（`TaskCard`、`StatusBadge`）
- 文件：`index.vue`
- Props：camelCase（定义时）、kebab-case（模板中使用）

### 4.5 组件文档模板

每个全局组件的 `index.vue` 文件顶部必须有 JSDoc 注释：

```vue
<script setup lang="ts">
/**
 * ComponentName - 组件中文名
 * @description 一句话说明用途
 *
 * @example
 * <ComponentName prop1="value" />
 */
</script>
```

### 4.6 常见封装清单

| 重复模式 | 封装为 | 位置 | Props 设计 |
|----------|--------|------|-----------|
| 任务卡片 | `TaskCard` | `components/` | `task: TaskInfo` |
| 状态标签 | `StatusBadge` | `components/` | `type, text, plain` |
| 进度条 | `ProgressBar` | `components/` | `percent, label, color` |
| 空状态 | `EmptyState` | `components/` | `type, text, actionText` |
| 列表项 | `ListItem` | `components/` | `icon, title, desc, extra` |
| 统计数字 | `StatCard` | `components/` | `value, label, icon, color` |
| 操作按钮组 | `ActionButtons` | `components-local/页面名/` | `primary, secondary, @primaryClick, @secondaryClick` |
| 筛选栏 | `FilterBar` | `components-local/页面名/` | `options, modelValue, @change` |

---

## 五、硬性禁令

| 禁止行为 | 说明 |
|----------|------|
| 硬编码样式值 | 禁止 `color: #22C55E`、`font-size: 14px`、`border-radius: 8px` |
| 复制粘贴组件 | 同一 UI 出现 2 次必须封装 |
| 混用组件库 | 只用 uview-plus，不引入第二个 |
| 乱放文件 | 新文件必须按目录归属规则归位 |
| 逐个覆盖组件样式 | 改风格只改 Token 文件，不逐组件覆盖 |
| 组件内直接调接口 | 接口调用统一走 `src/api/` |
| 魔法数字散落 | 数字、状态码等放 `src/constants/` |
| 类型定义散落 | TS 类型统一放 `src/types/` |

---

## 六、新文件归位检查

每次新增文件前，按此表确认：

```
□ 这是页面？           → src/pages/模块名/xxx.vue
□ 这是跨页面组件？      → src/components/组件名/index.vue
□ 这是页面内重复组件？  → src/components-local/页面名/组件名.vue
□ 这是接口？           → src/api/模块名.ts
□ 这是工具函数？       → src/utils/功能.ts
□ 这是类型？           → src/types/模块名.ts
□ 这是常量？           → src/constants/模块名.ts
□ 这是状态管理？       → src/store/modules/模块名.ts
□ 这是静态资源？       → src/static/images/分类/
□ 这是样式 Token？     → src/styles/tokens/_xxx.scss
```
---

## 七、前后端协作规则

### 7.1 API 对接

- 前端接口定义必须与 project/docs/后端技术方案.md 中的 API 规范一致
- 前端 src/api/ 目录下的接口文件，路径和参数必须与后端 API 清单对齐
- 后端 API 变更时，前端必须同步更新 src/api/ 对应文件

### 7.2 统一响应格式

所有 API 返回统一格式：

```typescript
interface ApiResponse<T = any> {
  code: number;      // 0=成功，非0=失败
  message: string;   // 提示信息
  data: T;           // 业务数据
}
```


### 7.3 认证与 Token

- 认证方式：JWT（JSON Web Token）
- Token 位置：Authorization: Bearer <token>
- 前端请求拦截器必须自动携带 Token
- Token 过期（401）时，前端必须跳转登录页

### 7.4 错误处理

| 错误码 | 含义 | 前端处理 |
|--------|------|---------|
| 0 | 成功 | 正常展示数据 |
| 400 | 参数错误 | 提示 message 内容 |
| 401 | 未认证 | 跳转登录页 |
| 403 | 无权限 | 提示无权限 |
| 404 | 资源不存在 | 提示数据不存在 |
| 500 | 服务器错误 | 提示服务异常，请稍后重试 |

---

## 八、用户可见文案规则

### 8.1 单一真源与分工（强制）

| 文案类型 | 唯一真源 | 说明 |
|----------|----------|------|
| 接口级 `message`（后端随 `code` 下发的提示） | `project/docs/后端技术方案.md` §4.3（失败场景）/ §5.2（各接口 `message` 行） | 前端**只做展示或映射**，不得另造同义文案；能透传即透传 |
| 前端本地文案（toast / 按钮 / 标题 / 空态 / 加载态 / 占位符 / 引导 / 法定信息） | **本文件 §8.2** | **新增或修改任何用户可见文案，必须先在本节登记**（文案 + 位置 + 触发条件 + 依据）；未登记不得合入 |
| 视觉表现（颜色 / 字号 / 间距 / 圆角） | `project/docs/设计规范.md`（设计 Token） | 文案不进 Token 文件，Token 也不承载文案 |

补充规则：

1. **去重**：同一句文案在 ≥2 处出现 → 提取为 `src/constants/` 常量或组件内常量，禁止多份字面量各自漂移（§8.2 两条即为页面内常量 `AUTH_CODE_EXPIRED_TEXT` / `FEISHU_APP_ID_MISSING_TEXT`）。
2. **不回显技术细节**：技术错误码（如飞书 `20003`、HTTP 状态码）不得直接展示给用户，只给可执行动作。
3. **不重复提示**：后端已给出 `message` 且 `request` 封装已 toast 时，调用处只记日志，不再新造同义 toast。
4. **文案变更 = 代码 + 真源同步**：任何措辞/标点/中英混排调整，须同步更新 §8.2（与 §7.1 接口同步同性质）。
5. **法定/合规文案**（备案号等）不得由页面各自硬编码，须收在唯一组件或常量（当前样板：`project/src/components/IcpFooter/index.vue`）。

### 8.2 已登记文案（登录链路 / 阶段二登记链路）

| # | 文案 | 位置 | 触发条件 | 依据 | 登记状态 |
|---|------|------|----------|------|----------|
| 1 | 登录链接已失效，请重新点击飞书登录 | `project/src/pages/login/index.vue`（常量 `AUTH_CODE_EXPIRED_TEXT` :65；使用于 `handleAuthCodeExpired` :104 / :108） | 飞书错误码 **20003**（授权码无效/已过期）；不回显错误码，最多自动重发起一次授权 | #F-17 任务 3；与后端 §5.2 的 20003 映射同义（后端 `message` 同语义） | **本次新增（#P-6 登记）** |
| 2 | 飞书应用未配置 | 同文件（常量 `FEISHU_APP_ID_MISSING_TEXT` :63；使用于 `redirectToFeishuAuth` :180） | 构建期 `VITE_FEISHU_APP_ID` 为空且登录模式为 `feishu`（`VITE_LOGIN_MODE=feishu`）时中止跳转并提示 | #F-15 任务 2 | **本次新增（#P-6 登记）** |
| 3 | 退出登录 | `project/src/constants/auth.ts`（常量 `LOGOUT_ENTRY_TEXT`；两侧壳层共用且均已接入：阶段二 `components-local/stage2/Stage2Sidebar.vue`、阶段一 `pages/index/index.vue`） | 本地存在 `token`（已登录）时侧栏用户区显示入口；点击打开二次确认弹窗 | #F-19 任务 1（措辞经总控批准） | **本次新增（#F-19）** |
| 4 | 退出登录（确认弹窗标题） | 同文件（常量 `LOGOUT_CONFIRM_TITLE`；共享 Modal 的 title） | 打开退出确认弹窗时展示 | #F-19 任务 1 | **本次新增（#F-19）** |
| 5 | 退出后需重新登录才能继续完成任务，确认退出吗？ | 同文件（常量 `LOGOUT_CONFIRM_MESSAGE`；确认弹窗正文） | 打开退出确认弹窗时展示（说明退出后果） | #F-19 任务 1 | **本次新增（#F-19）** |
| 6 | 取消 | 同文件（常量 `LOGOUT_CONFIRM_CANCEL_TEXT`；确认弹窗次要按钮） | 退出确认弹窗的取消动作（不退出、仅关闭弹窗） | #F-19 任务 1 | **本次新增（#F-19）** |
| 7 | 确认退出 | 同文件（常量 `LOGOUT_CONFIRM_OK_TEXT`；确认弹窗主按钮） | 确认执行退出：清 `token` / `merchant` 并 `reLaunch` 登录页（无额外 toast） | #F-19 任务 1 | **本次新增（#F-19）** |
| 8 | 退出登录 | `admin/src/constants/auth.ts`（常量 `LOGOUT_ENTRY_TEXT`；管理后台用户区下拉菜单项，接入于 `admin/src/components/Layout/index.vue`） | 管理后台已登录时用户区菜单显示入口；点击打开二次确认弹窗 | #AF-13（用户 2026-09-14「管理后台也要加退出登录」）；文案风格与商家端 #3 一致 | **本次新增（#AF-13）** |
| 9 | 退出登录（确认弹窗标题） | 同文件（常量 `LOGOUT_CONFIRM_TITLE`；Element Plus `ElMessageBox` 标题） | 打开退出确认弹窗时展示 | #AF-13 | **本次新增（#AF-13）** |
| 10 | 退出后需重新登录才能继续管理后台，确认退出吗？ | 同文件（常量 `LOGOUT_CONFIRM_MESSAGE`；确认弹窗正文） | 打开退出确认弹窗时展示（说明退出后果；句式与商家端 #5 一致，仅场景词改为「管理后台」） | #AF-13 | **本次新增（#AF-13）** |
| 11 | 取消 | 同文件（常量 `LOGOUT_CONFIRM_CANCEL_TEXT`；确认弹窗次要按钮） | 退出确认弹窗的取消动作（不退出、仅关闭弹窗） | #AF-13 | **本次新增（#AF-13）** |
| 12 | 确认退出 | 同文件（常量 `LOGOUT_CONFIRM_OK_TEXT`；确认弹窗主按钮） | 确认执行退出：清 `admin_token` / `admin_info` 并跳 `/login`（无额外 toast；管理后台 token 与商家端互相独立，只清 admin 自己的） | #AF-13 | **本次新增（#AF-13）** |
| 13 | 选择经营类目 | `project/src/constants/category.ts`（常量 `CATEGORY_PICKER_TITLE`；**弹窗标题与侧栏常驻入口共用同一句**，接入于 `components-local/stage2/CategoryPicker.vue` 与 `components-local/stage2/Stage2Sidebar.vue`） | 阶段二侧栏左下角常驻入口常显（用户区上方）；首次进入阶段二且未保存经营类目时自动弹窗的标题 | #F-20 任务 2.2 / 2.3 | **本次新增（#F-20）** |
| 14 | 首次进入需要先选择经营类目：最多 3 个，并指定 1 个主类目；保存后可在左侧入口随时修改。 | 同文件（常量 `CATEGORY_DIALOG_INTRO`；弹窗说明） | 打开经营类目弹窗（自动弹或侧栏入口）时展示 | #F-20 任务 2.2 | **本次新增（#F-20）** |
| 15 | 本次可先跳过；跳过不会保存，下次进入会再次提示。 | 同文件（常量 `CATEGORY_DIALOG_HINT`；弹窗提示） | 打开经营类目弹窗时展示（说明「跳过」语义：仅本次驻留生效、不写库） | #F-20 任务 2.2 / 2.4 | **本次新增（#F-20）** |
| 16 | 跳过 | 同文件（常量 `CATEGORY_SKIP_TEXT`；弹窗次要按钮） | 点击跳过：仅关闭弹窗，不写库、不报错、不写永久静默标记；下次进入页面重新判定 | #F-20 任务 2.4 | **本次新增（#F-20）** |
| 17 | 保存经营类目 | 同文件（常量 `CATEGORY_SAVE_TEXT`；弹窗主按钮） | 点击保存：`POST /api/merchant/category`（API-07，数量 1-3） | #F-20 任务 2.1 | **本次新增（#F-20）** |
| 18 | 保存中… | 同文件（常量 `CATEGORY_SAVING_TEXT`；弹窗主按钮保存中态） | 保存请求进行中（防重复提交） | #F-20 任务 2.1 | **本次新增（#F-20）** |
| 19 | 经营类目尚未保存 | 原：阶段一 `pages/index/index.vue` T1.1.2 任务卡 `#right-extra` 插槽 + 常量 `project/src/constants/category.ts` 的 `CATEGORY_UNSAVED_TEXT`（**两者均已删除**） | ~~查询侧返回空数组时在卡片右侧显示~~ | #F-21 任务 2.4 新增 → **#F-22 按用户要求撤回**（用户 2026-09-14 原话：「在一阶段目前展示在右侧角标位置的，"经营类目尚未保存"删除。」） | **已撤回（#F-22）**：代码/常量/样式均已移除，`grep -rn "经营类目尚未保存" project/src` = 0；仅保留本历史行 |
| 20 | AI 配置 | `admin/src/constants/ai-config.ts`（常量 `AI_CONFIG_MENU_TEXT`；菜单项 + 页面标题，接入于 `admin/src/components/Layout/index.vue` 与 `admin/src/router/index.ts` meta.title） | super_admin 登录后侧栏显示入口；点击进入 AI 分入口配置页 | #AF-14（P7 v1.1 方案 §六；用户 2026-09-14） | **本次新增（#AF-14）** |
| 21 | AI 配置页顶部说明（密钥留空=不修改、清空=回落 env） | 同文件（常量 `AI_CONFIG_PAGE_INTRO_TEXT`；页面顶部 `el-alert`） | 进入 AI 配置页即展示（说明写入语义，避免误改） | #AF-14（P7 §5.3 写入契约） | **本次新增（#AF-14）** |
| 22 | 三入口展示名（AI 经营分析 / 主图优化 / 标题优化） | 同文件（常量 `AI_CONFIG_ENTRY_LABELS`；入口卡片标题） | 渲染三入口卡片标题时 | #AF-14（任务单 §3.2） | **本次新增（#AF-14）** |
| 23 | 字段标签（密钥（api_key）/ 接口地址（base_url）/ 模型（model）/ 超时（ms）/ 最大 tokens / 每日限流 / 启用） | 同文件（常量 `AI_CONFIG_FIELD_LABELS`；表单 `el-form-item` label） | 渲染配置表单字段标签时 | #AF-14（P7 §6.2 字段表） | **本次新增（#AF-14）** |
| 24 | 保存 / 测试连接 / 清除自定义密钥 | 同文件（常量 `AI_CONFIG_SAVE_TEXT` / `AI_CONFIG_VERIFY_TEXT` / `AI_CONFIG_CLEAR_KEY_TEXT`；各入口卡片操作按钮） | 点击触发对应动作：保存（仅提交 dirty 字段）/ 连通性自检 / 显式清除回落 env | #AF-14（P7 §6.2） | **本次新增（#AF-14）** |
| 25 | 密钥正常 / 未配置密钥（回落 env）/ 加密密钥不匹配，当前回落 env | 同文件（常量 `AI_CONFIG_KEY_STATUS_OK_TEXT` / `AI_CONFIG_KEY_STATUS_NONE_TEXT` / `AI_CONFIG_KEY_STATUS_DECRYPT_FAILED_TEXT`；入口卡片状态标签） | 按后端 `apiKeyStatus`（ok / none / decrypt_failed）渲染；`decrypt_failed` 用 danger 样式显著告警，不吞成空值 | #AF-14（任务单 §3.3；P7 §5.2 状态枚举） | **本次新增（#AF-14）** |
| 26 | 已配置：{掩码}（留空表示不修改）/ 未配置（留空表示不修改） | 同文件（常量 `AI_CONFIG_SECRET_PLACEHOLDER_CONFIGURED_PREFIX` / `AI_CONFIG_SECRET_PLACEHOLDER_SUFFIX` / `AI_CONFIG_SECRET_PLACEHOLDER_EMPTY`；密钥输入框 placeholder，**输入框初始为空、绝不预填掩码**） | 渲染密钥输入框占位时展示当前掩码（仅作提示，不进入表单值） | #AF-14（P7 §6.3 三条防线之一） | **本次新增（#AF-14）** |
| 27 | 指纹：{16hex} / 指纹：— / 最近修改：{人} @ {时间} / 最近修改：— | 同文件（常量 `AI_CONFIG_FINGERPRINT_PREFIX` / `AI_CONFIG_FINGERPRINT_EMPTY_TEXT` / `AI_CONFIG_UPDATED_PREFIX` / `AI_CONFIG_UPDATED_EMPTY_TEXT`；卡片只读元信息） | 渲染指纹与最近修改信息时（指纹用于确认「改的是不是同一把 key」） | #AF-14（P7 §6.2 只读列） | **本次新增（#AF-14）** |
| 28 | 密钥长度需在 8-256 之间 / 检测到掩码内容，请填写完整密钥 / 接口地址需以 http:// 或 https:// 开头 / 没有需要保存的修改 | 同文件（常量 `AI_CONFIG_API_KEY_LENGTH_TEXT` / `AI_CONFIG_API_KEY_MASK_REJECT_TEXT` / `AI_CONFIG_BASE_URL_FORMAT_TEXT` / `AI_CONFIG_NO_DIRTY_TEXT`；提交前本地校验提示） | 提交前拦截：空串/超长/掩码回写/格式非法/无 dirty 字段（避免发出必然 400 的请求） | #AF-14（P7 §5.3 + §6.3 第 3 条前移） | **本次新增（#AF-14）** |
| 29 | 已保存，当前进程立即生效；其它 worker 最多 60 秒后生效 | 同文件（常量 `AI_CONFIG_SAVE_OK_TEXT`；保存成功 toast） | PUT 返回 200 后提示（把多 worker 生效边界写在 UI 上） | #AF-14（P7 §6.2 保存提示） | **本次新增（#AF-14）** |
| 30 | 清除自定义密钥（确认框标题）/ 清除后该入口将回落使用环境变量（env）中的密钥，确认清除吗？/ 确认清除 / 取消 / 已清除自定义密钥，该入口已回落 env | 同文件（常量 `AI_CONFIG_CLEAR_CONFIRM_TITLE` / `AI_CONFIG_CLEAR_CONFIRM_MESSAGE` / `AI_CONFIG_CLEAR_CONFIRM_OK_TEXT` / `AI_CONFIG_CLEAR_CONFIRM_CANCEL_TEXT` / `AI_CONFIG_CLEAR_OK_TEXT`；`ElMessageBox` 二次确认 + 成功提示） | 点击「清除自定义密钥」时二次确认；确认后提交显式 `null`（回落 env） | #AF-14（P7 §5.3「显式 null」；任务单 §3.4） | **本次新增（#AF-14）**；注：`取消` 与 #11 字面量相同，建议后续抽公共按钮文案常量（本轮未改 #AF-13 文件） |
| 31 | 无权访问该页面（仅超级管理员） | 同文件（常量 `AI_CONFIG_ROLE_DENIED_TEXT`；`admin/src/router/index.ts` 路由守卫） | 非 super_admin 直连 `/ai-config` 时提示并重定向 `/dashboard` | #AF-14（P7 §5.4 三层防线之二） | **本次新增（#AF-14）** |
| 32 | 暂无 AI 配置 / 关闭后该入口整体回落 env 配置（不清空已存字段） | 同文件（常量 `AI_CONFIG_EMPTY_TEXT` / `AI_CONFIG_ENABLED_HINT_TEXT`；空态与启用开关旁提示） | 列表为空时展示空态；渲染「启用」开关说明时 | #AF-14（任务单 §3.2/§3.8） | **本次新增（#AF-14）** |
| 33 | 京麦商家ID | `project/src/constants/merchant.ts`（常量 `JD_MERCHANT_ID_LABEL`；经营类目弹窗顶部输入标签，接入 `components-local/stage2/CategoryPicker.vue`） | 打开经营类目弹窗时展示该字段标签 | #F-25 任务 3.3 | **本次新增（#F-25）** |
| 34 | 店铺名称 | 同文件（常量 `SHOP_NAME_LABEL`；经营类目弹窗顶部输入标签） | 同上 | #F-25 任务 3.3 | **本次新增（#F-25）** |
| 35 | 请输入京麦商家ID（仅数字） | 同文件（常量 `JD_MERCHANT_ID_PLACEHOLDER`；输入占位） | 字段为空时的占位提示（说明只允许数字） | #F-25 任务 3.3 | **本次新增（#F-25）** |
| 36 | 请输入店铺名称（仅汉字） | 同文件（常量 `SHOP_NAME_PLACEHOLDER`；输入占位） | 字段为空时的占位提示（说明只允许汉字） | #F-25 任务 3.3 | **本次新增（#F-25）** |
| 37 | 京麦商家ID仅支持数字 | 同文件（常量 `JD_MERCHANT_ID_INVALID_TEXT`；保存前格式校验失败 toast，接入 `components-local/stage2/CategoryPicker.vue` 经营类目弹窗输入区） | 保存时字段含非数字字符（实时过滤之外的兜底）：阻止提交并提示，不发任何请求 | #F-25 任务 3.3 / 3.4；登记弹窗已于 #F-26-R2 移除，本句仍由经营类目弹窗使用 | **本次新增（#F-25）**；位置修正（#F-26-R2） |
| 38 | 店铺名称仅支持汉字 | 同文件（常量 `SHOP_NAME_INVALID_TEXT`；保存前格式校验失败 toast，接入 `components-local/stage2/CategoryPicker.vue` 经营类目弹窗输入区） | 保存时字段含非汉字字符：阻止提交并提示，不发任何请求 | #F-25 任务 3.3 / 3.4；登记弹窗已于 #F-26-R2 移除，本句仍由经营类目弹窗使用 | **本次新增（#F-25）**；位置修正（#F-26-R2） |
| 39 | 信息仅用于登记存档：商家 ID 仅支持数字、店铺名称仅支持汉字，可随时跳过。 | ~~`project/src/pages/stage2/index.vue`（商家信息登记弹窗 `.reg-form__hint`）~~ | ~~登记弹窗内展示~~（弹窗已随 #F-26-R2 整块删除，文案不再出现在任何界面） | #F-25 任务 3.4 新增 → **#F-26-R2 按用户要求移除**（用户 2026-09-14 原话：「把这个删掉，只留下现在调整之后的选择类目的弹窗」） | **已移除（#F-26-R2）**：代码/样式/状态一并删除，`grep -rn "reg-form\|showRegistrationModal\|handleSaveRegistration" project/src` = 0；仅保留本历史行 |
| 40 | 请选择一级类目 | `project/src/constants/category.ts`（常量 `CATEGORY_TOP_PLACEHOLDER`；一级 dropdown 触发器占位） | 未选择一级类目（parent_id=0）时展示 | #F-25-R1 | **本次新增（#F-25-R1）** |
| 41 | 请选择二级类目 | 同文件（常量 `CATEGORY_SUB_PLACEHOLDER`；二级 dropdown 触发器占位） | 已选一级类目但未勾选二级类目（parent_id<>0）时展示 | #F-25-R1 | **本次新增（#F-25-R1）** |
| 42 | 请选择1-3个类目 | 同文件（常量 `CATEGORY_COUNT_ERROR_TEXT`；多选数量越界 toast） | 二级 dropdown 勾第 4 个时前端前置拦截（真源：`project/docs/后端技术方案.md` §5.2 API-07 异常情况行，措辞与后端 400 一致） | #F-25-R1（原为组件内局部常量，本次迁入 constants 统一） | **本次迁移登记（#F-25-R1）** |
| 43 | 商家登记信息（抽屉信息区标题） | `admin/src/constants/merchant.ts`（常量 `MERCHANT_INFO_TITLE`；`admin/src/pages/merchant-progress/index.vue` 详情抽屉 `el-descriptions` 标题） | 打开商家进度详情抽屉时展示 | #AF-15（用户 2026-09-14「点击商家带出京麦商家ID/店铺名称」） | **本次新增（#AF-15）** |
| 44 | 京麦商家ID / 店铺名称（管理后台字段标签） | 同文件（常量 `MERCHANT_INFO_JD_ID_LABEL` / `MERCHANT_INFO_SHOP_NAME_LABEL`；抽屉信息区字段标签，**措辞与 #33/#34 商家端一致**） | 渲染详情抽屉两个字段标签时 | #AF-15 | **本次新增（#AF-15）** |
| 45 | 未登记 | 同文件（常量 `MERCHANT_INFO_UNREGISTERED_TEXT`；字段空态） | `jd_merchant_id` / `shop_name` 为 `null` 或空串时展示（不显示 `null`、不隐藏该行） | #AF-15（任务单 §3.3） | **本次新增（#AF-15）** |
| 46 | 加载中… / 登记信息获取失败 | 同文件（常量 `MERCHANT_INFO_LOADING_TEXT` / `MERCHANT_INFO_FAILED_TEXT`；信息区加载态与失败态） | 打开抽屉后取回登记信息期间展示加载态；请求失败展示失败态（与「未登记」区分，不静默当空值） | #AF-15（任务单 §3.3/§3.4） | **本次新增（#AF-15）** |
| 47 | 共 {总数} 行 / 写入 {写入} 行 / 跳过 {跳过} 行 / 修正 {修正} 行 | `project/src/constants/stage2.ts`（常量 `EXCEL_RESULT_SUMMARY_LABELS` + `EXCEL_RESULT_ROW_UNIT` + `EXCEL_RESULT_SEPARATOR`；接入 `components-local/stage2/ExcelUpload.vue` 导入结果区汇总行） | Excel 上传成功（HTTP 201 有写入 / 200 全坏行）后展示；数值分别取后端 `total_rows / count / skipped / normalized` | #PB-24-3（响应契约 #PB-24-2） | **本次新增（#PB-24-3）** |
| 48 | 第 {物理行号} 行 · {字段中文名或库列名} · {后端 message} | 同文件（常量 `EXCEL_ISSUE_LINE_TEMPLATE`；字段名经 `SHOP_METRIC_LABELS` 映射，未收录回退库列名；**原因文案原样用后端 `message`**） | 导入结果中逐条渲染后端 `issues[]`（有坏行或被归一的行）时 | #PB-24-3 | **本次新增（#PB-24-3）** |
| 49 | 仅显示前 200 条问题，完整记录见服务端日志 | 同文件（常量 `EXCEL_ISSUES_TRUNCATED_TEXT`；问题清单尾部提示） | 后端 `issues_truncated == true`（问题数 > 200，上界由后端 `MAX_ISSUES` 固定）时展示 | #PB-24-3（契约 #PB-24-2） | **本次新增（#PB-24-3）** |
| 50 | 手机号登录 | `project/src/constants/auth.ts`（常量 `PHONE_LOGIN_TITLE`；登录页手机号表单标题） | `VITE_LOGIN_MODE=phone` 时渲染表单标题 | #FE-25 范围A-1 | **本次新增（#FE-25）** |
| 51 | 请输入手机号 | 同文件（常量 `PHONE_PLACEHOLDER`；手机号输入框占位） | 手机号输入框为空时展示 | #FE-25 范围A-1 | **本次新增（#FE-25）** |
| 52 | 请输入验证码 | 同文件（常量 `PHONE_CODE_PLACEHOLDER`；验证码输入框占位 + 未填验证码点登录的就地提示，**同一常量两处复用**） | 验证码为空时展示 | #FE-25 范围A-1 | **本次新增（#FE-25）** |
| 53 | 获取验证码 | 同文件（常量 `PHONE_SEND_CODE_TEXT`；发码按钮默认态） | 非请求中、非倒计时内 | #FE-25 范围A-2 | **本次新增（#FE-25）** |
| 54 | 发送中... | 同文件（常量 `PHONE_SEND_CODE_LOADING_TEXT`；发码按钮请求中态） | send-code 请求进行中（防连点） | #FE-25 范围A-2 | **本次新增（#FE-25）** |
| 55 | 重新获取(60s) | 同文件（常量 `PHONE_RESEND_CODE_TEXT` + 秒数拼接；发码按钮倒计时态） | 发码成功后倒计时内按钮禁用；**秒数唯一来源 = 后端响应 `cooldown_seconds`，前端不硬编码** | #FE-25 范围A-2 | **本次新增（#FE-25）** |
| 56 | 手机号格式不正确 | 同文件（常量 `PHONE_INVALID_TEXT`；手机号就地提示） | 前端 `^1[3-9]\d{9}$` 校验失败（与后端 400 专句同措辞） | #FE-25 范围A-1 | **本次新增（#FE-25）** |
| 57 | 登录 | 同文件（常量 `PHONE_LOGIN_BUTTON_TEXT`；登录按钮默认态） | phone 模式登录按钮 | #FE-25 范围A-1 | **本次新增（#FE-25）** |
| 58 | 登录中... | 同文件（常量 `PHONE_LOGIN_LOADING_TEXT`；登录按钮请求中态） | phone-login 请求进行中 | #FE-25 范围A-4 | **本次新增（#FE-25）** |
| 59 | 安全验证组件加载失败，请刷新重试或稍后再试 | 同文件（常量 `CAPTCHA_UNAVAILABLE_TEXT`；人机校验 fail-closed 兜底 toast） | `getCaptchaParam()` 抛错（SDK 未加载 / appId 未配置 / 初始化失败 / 等待超时）→ **不发 send-code**；不含供应商名与内部码（用户主动取消走 #60） | #FE-25 范围B | **本次新增（#FE-25）** |
| 60 | 请完成安全验证后再获取验证码 | `project/src/constants/auth.ts`（常量 `CAPTCHA_INCOMPLETE_TEXT`；用户主动取消/未完成安全验证的轻提示） | SDK 已唤起但用户关闭弹层、或 onSuccess 时 `getValidate()` 为空 → **不发 send-code**、按钮立即恢复可点（不启动倒计时） | #FE-25-R1 裁决（与 #59 严格区分：本条不是组件故障） | **本次新增（#FE-25-R1）** |
| 61 | 商家清单（页面标题 / 侧栏菜单 / 面包屑 / 首页入口） | `admin/src/constants/merchant.ts`（常量 `MERCHANT_LIST_TITLE`；接入 `admin/src/router/index.ts` meta.title、`components/Layout/index.vue` 菜单项、`pages/dashboard/index.vue` 快捷入口） | 渲染侧栏菜单与面包屑时 | #AF-14（商家清单页；用户 2026-09-15） | **本次新增（#AF-14）** |
| 62 | 商家进度（菜单项改名，原「商家管理」） | 同文件（常量 `MERCHANT_PROGRESS_TITLE`；同一批接入点） | 与新页「商家清单」区分：进度聚合页保留独立入口 | #AF-14（任务单 §2 改名并保持顺序） | **本次新增（#AF-14）** |
| 63 | 商家ID / 昵称 / 京麦商家ID / 店铺名（关键词占位）；查询；重置；全部 | 同文件（常量 `MERCHANT_LIST_KEYWORD_PLACEHOLDER` / `MERCHANT_LIST_SEARCH_TEXT` / `MERCHANT_LIST_RESET_TEXT` / `MERCHANT_LIST_ALL_OPTION_LABEL`；筛选区输入与按钮、下拉「全部」项） | 关键词输入占位（说明匹配范围）；点击查询/重置；下拉未选择时 | #AF-14（冻结契约：keyword 4 字段匹配） | **本次新增（#AF-14）** |
| 64 | 表格列标签：商家ID / 昵称 / 京麦商家ID / 店铺名 / 当前阶段 / 状态 / 最近活跃 / 注册时间 | 同文件（常量 `MERCHANT_LIST_COLUMN_LABELS`；`pages/merchant-list/index.vue` 表头） | 渲染商家清单表头时 | #AF-14（任务单 §1 列清单） | **本次新增（#AF-14）** |
| 65 | 阶段选项与标签：入驻准备（onboarding）/ 开店搭建（shop_setup） | 同文件（常量 `MERCHANT_STAGE_OPTIONS` / `MERCHANT_STAGE_LABELS`；筛选项与列表「当前阶段」列） | 阶段下拉渲染与列表映射（未登记取值回退原值，不隐藏） | #AF-14（冻结契约 stage 枚举） | **本次新增（#AF-14）** |
| 66 | 状态选项与标签：正常（1）/ 禁用（0）/ 已退出（2） | 同文件（常量 `MERCHANT_STATUS_OPTIONS` / `MERCHANT_STATUS_LABELS`；筛选项与列表「状态」列） | 状态下拉渲染与列表映射（注：当前后端投影未返回 status，列按空值占位展示，#PB-24 落地后自动生效） | #AF-14（冻结契约 status 枚举） | **本次新增（#AF-14）** |
| 67 | — （列表空值占位）/ 没有符合条件的商家（空态）/ 商家列表加载失败（错误态） | 同文件（常量 `MERCHANT_LIST_VALUE_PLACEHOLDER` / `MERCHANT_LIST_EMPTY_TEXT` / `MERCHANT_LIST_FAILED_TEXT`；列表单元格与页面状态） | 时间列/普通文本列为空、筛选无结果、请求失败时展示（不显示 null、不隐藏该行） | #AF-14（任务单 §1 空值/状态要求） | **本次新增（#AF-14）** |
| 68 | 查看商家清单 / 查看商家进度（首页快捷入口描述） | 同文件（常量 `MERCHANT_LIST_QUICK_DESC` / `MERCHANT_PROGRESS_QUICK_DESC`；`pages/dashboard/index.vue` 快捷入口） | 首页快捷入口列表渲染时 | #AF-14 | **本次新增（#AF-14）** |
| 69 | 同店账号（区块标题）/ 绑定账号（按钮）/ 解绑（成员行操作）/ 本账号（自身行标记） | `admin/src/constants/merchant.ts`（常量 `MERCHANT_BINDING_TITLE` / `MERCHANT_BINDING_BIND_TEXT` / `MERCHANT_BINDING_UNBIND_TEXT` / `MERCHANT_BINDING_SELF_TAG_TEXT`；接入 `admin/src/pages/merchant-progress/index.vue` 抽屉「同店账号」区） | 打开商家进度详情抽屉时渲染区块标题与「绑定账号」按钮；成员行 `is_self=true` 显示「本账号」且**不渲染解绑按钮** | 设计单 `dev-docs/任务单/merchant-account-binding-design.md` §6.2；#AF-18（任务单 §1） | **本次新增（#AF-18）** |
| 70 | 该商家尚未登记京麦商家ID（区内提示）/ 需先在商家端登记京麦商家ID，才能绑定同店账号（按钮 tooltip） | 同文件（常量 `MERCHANT_BINDING_UNREGISTERED_TEXT` / `MERCHANT_BINDING_UNREGISTERED_TOOLTIP_TEXT`） | `merchant.jd_merchant_id` 为空/null 时：`el-alert`(info) 常显 + 「绑定账号」按钮**禁用**（hover 才出 tooltip；禁用态点击不弹窗） | 设计单 §6.2；#AF-18 | **本次新增（#AF-18）** |
| 71 | 表格列标签：商家ID / 昵称 / 状态 / 绑定时间 / 绑定人 / 操作 | 同文件（常量 `MERCHANT_BINDING_COLUMN_LABELS`；`pages/merchant-progress/index.vue` 成员表表头） | 渲染同店账号成员表表头时 | 设计单 §6.2 列清单；#AF-18 | **本次新增（#AF-18）** |
| 72 | 暂无同店账号绑定（空态）/ 同店账号信息加载失败（错误态） | 同文件（常量 `MERCHANT_BINDING_EMPTY_TEXT` / `MERCHANT_BINDING_FAILED_TEXT`） | 读取成功但成员为空 / `GET /api/admin/merchant/{merchantId}/bindings` 非 2xx 时（失败态只呈现错误条，**不叠加空表**） | #AF-18 | **本次新增（#AF-18）** |
| 73 | 绑定账号（弹窗标题）/ 商家ID / 昵称（搜索占位「商家ID / 昵称」）/ 搜索 / 取消 / 候选表列标签（商家ID / 昵称 / 状态）/ 没有匹配的账号 / 请先选择一个账号 | 同文件（常量 `MERCHANT_BINDING_DIALOG_TITLE` / `MERCHANT_BINDING_SEARCH_PLACEHOLDER` / `MERCHANT_BINDING_SEARCH_TEXT` / `MERCHANT_BINDING_CANCEL_TEXT` / `MERCHANT_BINDING_CANDIDATE_COLUMN_LABELS` / `MERCHANT_BINDING_CANDIDATE_EMPTY_TEXT` / `MERCHANT_BINDING_SELECTED_REQUIRED_TEXT`） | 打开绑定弹窗（默认空关键字拉第 1 页候选，**剔除当前商家自身**）；未选行点「绑定账号」给 warning | 设计单 §6.2（候选**只展示 3 列**：商家ID / 昵称 / 状态，**绝不展示手机号**）；#AF-18 | **本次新增（#AF-18）** |
| 74 | 确认绑定（标题）/ 绑定后两个账号共享阶段/任务进度；账号级标记（新手引导、欢迎消息、数据专区解锁标记）不共享（正文）/ 确认绑定（主按钮）；确认解绑（标题）/ 解绑后该账号不再共享本店进度；已完成的进度记录保持不变（正文）/ 确认解绑（主按钮） | 同文件（常量 `MERCHANT_BINDING_CONFIRM_TITLE` / `MERCHANT_BINDING_CONFIRM_MESSAGE` / `MERCHANT_BINDING_CONFIRM_OK_TEXT` / `MERCHANT_BINDING_UNBIND_CONFIRM_TITLE` / `MERCHANT_BINDING_UNBIND_CONFIRM_MESSAGE` / `MERCHANT_BINDING_UNBIND_CONFIRM_OK_TEXT`；`ElMessageBox.confirm`） | 绑定/解绑二次确认弹窗展示；点「取消」不发送任何写请求 | 设计单 §6.2 **原文照录**（不得改写）；#AF-18 | **本次新增（#AF-18）** |
| 75 | 绑定/解绑的结果提示（前端无字面量） | `admin/src/pages/merchant-progress/index.vue`（成功：`ElMessage.success(res.message)`；失败：由 `admin/src/api/request.ts` 拦截器按后端 `message` 原样 toast） | 绑定/解绑请求返回后 | 后端文案真源（如「该商家已被登记」「该商家尚未登记京麦商家ID，无法绑定」「该账号已绑定到其它商家」「不能绑定自身」「绑定关系不存在」）；前端**不新造同义句**（§8.1 第 3 条）；#AF-18 | **本次新增（#AF-18）** |
| 76 | 该商家已被登记 | **前端无字面量**（不新增常量）：由后端 `PUT /api/merchant/registration` 返回 `{code:400, message:"该商家已被登记"}`，前端经 `api/request.ts` 原样 toast | 阶段二登记时该京麦商家ID **已被别的活跃账号登记**或**已存在活跃绑定组**（HTTP 400，写库不发生） | 设计单 `dev-docs/任务单/merchant-account-binding-design.md` §5.1 判据 / §5.2 文案表；业务真源 = 后端（落点 `services/merchant.py::save_registration` 的唯一性校验，由 #PB 单落地并回写 `后端技术方案` §4.3/API-20） | **本次新增（#FE-17）** |

> **阶段二登记链路（#FE-17）**：#76 是**后端 message 直出型文案**——商家端不新增任何字面量/常量，只经请求层透传（证据：`project/src/api/merchant.ts:21-22` 唯一发送点、`project/src/api/request.ts:80-82` 统一 toast、`project/src/components-local/stage2/CategoryPicker.vue:560-562` 有意不重复提示）。本行登记的目的是**可检索的文案归属与触发条件**，避免后续误判为"前端缺文案"。

> **#FE-25 口径说明（前端不登记后端文案）**：手机号登录的错误文案（「手机号格式不正确」「请先完成安全验证」「发送过于频繁，请在 N 秒后重试」「今日发送次数已达上限，请明天再试」「发送过于频繁，请稍后再试」「当前发送量已达上限，请稍后再试」「短信服务暂不可用，请稍后重试」「验证码不正确或已过期」「验证尝试次数过多，请重新获取验证码」「账号已被禁用，请联系平台」）**真源在后端常量**（#PB-23 → `后端技术方案` §4.3/§5.2），前端**只展示后端 `message`**、不新造同义句（§8.1 第 3 条），故不在本表逐条登记。

> 登记说明：#1 / #2 由 #F-17 / #F-15 **先落地在代码**，本节为**事后补登记**（#P-6 只补真源、不改代码）；#3~#7 的措辞由 #F-19 报总控确认后落地在 `project/src/constants/auth.ts`（**唯一真源**，符合 §8.1「未登记不得合入」）。 #8~#12 为管理后台侧同类文案（`admin/src/constants/auth.ts`，**管理后台独立真源文件**，与商家端 `project/src/constants/auth.ts` 各自维护、措辞同风格），落地于 `admin/src/components/Layout/index.vue`（#AF-13）。
> **已收敛（实测口径）**：阶段一 `pages/index/index.vue` 已接入本表 #3~#7 常量（`import { LOGOUT_* } from '@/constants/auth'`，登出动作从 `@/utils/auth` 导入），两侧措辞一致；`grep -rn "暂不退出" project/src` 仅命中 `pages/index/index.vue:801` 的**代码注释**（非用户可见文案），该注释随 #F-21 清理阶段一旧面板时一并处理。
> #13~#18 为 #F-20 新增的经营类目弹窗文案（`project/src/constants/category.ts`，弹窗与侧栏入口共用）；**#33~#39 为 #F-25**（商家登记输入区 + 侧栏融合：新增/修改文案，落在 `constants/merchant.ts` 与登记弹窗），**#40~#42 为 #F-25-R1**（二级类目 dropdown 多选：新增占位与迁移数量越界提示，均落 `constants/category.ts`）；**#47~#49 为 #PB-24-3**（Excel 导入结果：汇总行标签、问题条目行模板、截断提示，均落 `constants/stage2.ts`；**问题原因文案不在此登记——单一真源是后端 `ISSUE_MESSAGES`，前端原样展示**）。**#F-26 / #F-26-R1 / #F-26-R2 未新增任何用户可见文案**（#F-26 为图标与触发器视觉、#F-26-R1 为输入框行高修复、#F-26-R2 为登记弹窗删除），故本表仅在 #37/#38 修正引用位置、在 #39 标注移除。**#19 已由 #F-22 撤回**（阶段一 T1.1.2 卡片右侧不再显示任何类目提示；保存/回显全部在阶段二）：按「撤回留痕、不抹历史」处理，行内标注撤回原因与实测口径。后续调整按 §8.1 第 4 条同步本表。

### 8.3 待收敛清单（既有文案：**尚未登记、尚未定稿**）

> 抽样（非穷尽）自 `project/src`，按「重复出现 / 同义措辞不统一 / 与后端文案可能重叠」筛选。**未移入 §8.2 前不具有真源效力**；收敛时逐条评审，禁止一次性大改。

| # | 现象 | 证据（文件:行） | 建议收敛方向 |
|---|------|----------------|-------------|
| 1 | 「失败 + 处置」句式不统一 | `login/index.vue` :134 / :201 / :225（登录失败，请重试）、`TrademarkSearch.vue` :66（复制失败，请重试）、:90（查询失败，请稍后重试）、`TitleOptimizePanel.vue` :204（AI 生成失败，请重试）、:219（复制失败，请重试）、`data-board.vue` :289（分析服务暂不可用，请稍后重试） | 统一为「动作 + 失败 + 处置」句式，抽公共常量 |
| 2 | 同类动作三种措辞 | `stage2/data-board.vue` :57 / :154（重试）、:67（刷新）、`data-center/index.vue` :105 / :134（重试）、:143（刷新）、`TitleOptimizePanel.vue` :87（点击重试） | 区分「重试」与「刷新」语义，删除「点击重试」这类非标准措辞 |
| 3 | 同句跨文件重复 | `stage2/data-board.vue` :65 与 `data-center/index.vue` :142（完成 T2.5 店铺数据上传后刷新查看）；`data-board.vue` :55（后端聚合接口接入后将自动展示已上传数据，请稍后再试） | 抽公共组件/常量，避免两份字面量漂移 |
| 4 | 与后端同义的「未解锁」文案（潜在双真源） | 前端 `data-board.vue` :271（阶段二未解锁，无法生成分析）；后端 `api-py/app/services/shop.py` :108、`trademark.py` :26、`task_progress.py` :199 / :202（403 `message`：阶段二未解锁 / 数据专区未解锁）与 `task.py` :22 / :113（`unlockHint`：完成阶段一全部任务后解锁） | 解锁语义以接口为准，前端只展示或映射，不新造 |
| 5 | 加载态措辞 | `data-board.vue` :48（加载中...）、`CategoryPicker.vue` :22（加载中...）、`ProductGuideModal.vue` :59（图片加载失败） | 统一省略号与「加载中/加载失败」措辞 |
| 6 | 登录页静态文案（与 §8.2 同页，未登记） | `login/index.vue` :17（商家成长任务助手）、:31（飞书授权登录）、:35（登录中...）、:39（首次登录将自动创建账号）、:44（© 2024 商家成长任务体系）、:146 / :206（登录成功） | 整页文案一次性登记进 §8.2 |
| 7 | 「取消完成」确认流程一整套 | `stage2/index.vue` :153（取消完成）、:170（再想想）、:173（确认取消）、:565（已全部完成）、:586（已取消完成） | 作为一组登记，避免只登记其中一句 |
| 8 | 复制结果提示分散 | `ImageOptimizeModal.vue` :277（已复制到剪贴板）与 `TrademarkSearch.vue` :66、`TitleOptimizePanel.vue` :219（复制失败，请重试） | 抽复制结果提示常量，成功/失败成对收敛 |
| 9 | 引导入口文案 | `stage2/index.vue` :40 等共 4 处（重新观看引导） | 收敛为单一入口常量 |
| 10 | 法定文案（**已收敛样板**，登记为参考） | `components/IcpFooter/index.vue` :22（鲁ICP备2026053438号-1） | 已是单一来源；后续同类法定信息照此办理 |

---

> 后端技术方案详见 project/docs/后端技术方案.md