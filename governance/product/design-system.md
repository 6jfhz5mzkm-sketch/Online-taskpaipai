# 商家成长任务体系 — 设计规范

> 本文件是项目的唯一设计权威来源。所有页面样式必须从此处取值，禁止硬编码。

---

## 一、视觉风格

### 1.1 设计调性

- **关键词**：清新、友好、轻盈、有活力、不压迫
- **参考来源**：ZCOOL 任务管理界面设计
- **适配场景**：商家端 H5 任务中心（PC Web + 移动端同等重要；无小程序 / 原生 App 目标）

### 1.2 风格特征

- 圆角偏大（10-24px），所有卡片、按钮圆润友好
- 柔和弥散阴影，不用硬阴影
- 充足留白，宽松间距
- 微绿调灰白背景，清新不刺眼
- 适度动效（200ms），hover 反馈清晰

---

## 二、UI 组件库

### 2.1 选定方案

| 项目 | 选型 |
|------|------|
| 组件库 | **uview-plus** v3.8.55 |
| 框架 | uni-app + Vue 3 Composition API |
| 包管理 | npm |

### 2.2 使用原则

- **只用 uview-plus 一个组件库**，禁止引入第二个
- 组件库自带主题变量通过覆盖 `$u-*` / `--up-*` 实现，不重复定义
- 页面中禁止直接写 `<u-xxx style="color: #xxx">`，必须通过主题变量控制颜色
- 新增自定义组件时，优先组合 uview-plus 基础组件，不自己造轮子

---

## 三、设计 Token

### 3.1 文件位置

所有 Token 集中在 `src/styles/tokens/` 下，通过 `uni.scss` 统一引入。

### 3.2 色彩系统

#### 主色（成长绿）—— 与 uview-plus `$u-primary` 对齐

| Token | 色值 | 用途 |
|-------|------|------|
| `$u-primary` | `#22C55E` | 按钮、链接、重点强调 |
| `$u-primary-dark` | `#16A34A` | hover 态 |
| `$u-primary-disabled` | `#86EFAC` | 禁用态 |
| `$u-primary-light` | `#F0FDF4` | 浅底色、tag 背景、选中行 |

#### 功能色

| 语义 | 主色 | 浅底色 | 边框色 | 用途 |
|------|------|--------|--------|------|
| 成功 | `#22C55E` | `#F0FDF4` | `#BBF7D0` | 任务完成 |
| 进行中 | `#3B82F6` | `#EFF6FF` | `#BFDBFE` | 进行中任务 |
| 警告 | `#F59E0B` | `#FFFBEB` | `#FDE68A` | 待处理/注意 |
| 错误 | `#EF4444` | `#FEF2F2` | `#FECACA` | 错误/删除 |
| 信息 | `#6366F1` | `#EEF2FF` | `#C7D2FE` | 提示/帮助 |

#### 中性色

| Token | 色值 | 用途 |
|-------|------|------|
| `$u-main-color` | `#1F2937` | 主文字（标题） |
| `$u-content-color` | `#4B5563` | 正文 |
| `$u-tips-color` | `#9CA3AF` | 辅助说明 |
| `$u-light-color` | `#D1D5DB` | 禁用文字 |
| `$u-border-color` | `#E2E8F0` | 边框、分割线 |
| `$u-bg-color` | `#F8FAFC` | 页面背景 |

#### uview-plus 颜色变量完整覆盖清单

```scss
// 主色
$u-primary:            #22C55E;
$u-primary-dark:       #16A34A;
$u-primary-disabled:   #86EFAC;
$u-primary-light:      #F0FDF4;

// 成功
$u-success:            #22C55E;
$u-success-dark:       #16A34A;
$u-success-disabled:   #86EFAC;
$u-success-light:      #F0FDF4;

// 警告
$u-warning:            #F59E0B;
$u-warning-dark:       #D97706;
$u-warning-disabled:   #FCD34D;
$u-warning-light:      #FFFBEB;

// 错误
$u-error:              #EF4444;
$u-error-dark:         #DC2626;
$u-error-disabled:     #FCA5A5;
$u-error-light:        #FEF2F2;

// 信息
$u-info:               #6366F1;
$u-info-dark:          #4F46E5;
$u-info-disabled:      #A5B4FC;
$u-info-light:         #EEF2FF;

// 中性色
$u-main-color:         #1F2937;
$u-content-color:      #4B5563;
$u-tips-color:         #9CA3AF;
$u-light-color:        #D1D5DB;
$u-border-color:       #E2E8F0;
$u-bg-color:           #F8FAFC;
$u-disabled-color:     #D1D5DB;
```

### 3.3 按钮配色

| 类型 | 背景色 | 文字色 | 边框色 | Hover |
|------|--------|--------|--------|-------|
| 主按钮 | `#22C55E` | `#FFF` | — | `#16A34A` |
| 次按钮 | `#FFF` | `#22C55E` | `#22C55E` | `#F0FDF4` |
| 幽灵按钮 | transparent | `#22C55E` | — | `#F0FDF4` |
| 危险主按钮 | `#EF4444` | `#FFF` | — | `#DC2626` |
| 危险次按钮 | `#FFF` | `#EF4444` | `#EF4444` | `#FEF2F2` |
| 禁用按钮 | `#F5F5F5` | `#BFBFBF` | — | — |

按钮状态流转：Default → Hover → Active → Loading → Disabled

### 3.4 标签/Tag 配色

| 类型 | 背景色 | 文字色 | 边框色 |
|------|--------|--------|--------|
| 默认 | `#F5F5F5` | `#595959` | `#E8E8E8` |
| 成功 | `#F0FDF4` | `#15803D` | `#BBF7D0` |
| 进行中 | `#EFF6FF` | `#1D4ED8` | `#BFDBFE` |
| 警告 | `#FFFBEB` | `#B45309` | `#FDE68A` |
| 错误 | `#FEF2F2` | `#B91C1C` | `#FECACA` |
| 信息 | `#EEF2FF` | `#4338CA` | `#C7D2FE` |
| 品牌 | `#F0FDF4` | `#15803D` | `#BBF7D0` |

Tag 样式：圆角 `9999px`（胶囊形），内边距 `2px 10px`，字号 `12px`，行高 `20px`。

### 3.5 选中态/激活态

| 元素 | Default | Active/Selected | Hover |
|------|---------|-----------------|-------|
| 侧边栏菜单 | bg: transparent, text: `#595959`, icon: `#8C8C8C` | bg: `#F0FDF4`, text: `#22C55E`, icon: `#22C55E`, 左边框: 3px `#22C55E` | bg: `#F0FDF4`, text: `#22C55E` |
| 标签页 Tab | bg: transparent, text: `#595959` | bg: `#22C55E`, text: `#FFF`, 下边框: 2px `#22C55E` | bg: `#F0FDF4`, text: `#22C55E` |
| 任务卡片 | bg: `#FFF`, border: `#F0F0F0`, shadow: none | bg: `#FFF`, border: `#22C55E`, shadow: 0 0 0 1px 绿 | bg: `#FAFAFA`, border: `#E8E8E8` |
| 复选框 | border: `#D9D9D9`, bg: `#FFF` | bg: `#22C55E`, border: `#22C55E`, icon: `#FFF` | border: `#22C55E` |
| 单选框 | border: `#D9D9D9`, bg: `#FFF` | border: `#22C55E`, 内圆: `#22C55E` r=5px | border: `#22C55E` |

### 3.6 字号系统

| Token | 字号 / 行高 | 字重 | 用途 |
|-------|-------------|------|------|
| `$up-font-size-display` | 28px / 36px | 700 | 页面大标题（极少用） |
| `$up-font-size-h1` | 22px / 30px | 600 | 页面标题 |
| `$up-font-size-h2` | 18px / 26px | 600 | 区块标题 |
| `$up-font-size-h3` | 16px / 24px | 600 | 卡片标题、表单标题 |
| `$up-font-size-body` | 14px / 22px | 400 | 正文内容（主字号） |
| `$up-font-size-body-sm` | 13px / 20px | 400 | 紧凑场景正文 |
| `$up-font-size-caption` | 12px / 18px | 400 | 辅助说明、时间、标签 |
| `$up-font-size-mini` | 11px / 16px | 500 | 徽标数字、极小标签 |

字体栈：

```scss
font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC',
             'Microsoft YaHei', 'Helvetica Neue', sans-serif;
```

### 3.7 间距系统（4px 基础单位，8px 网格）

| Token | 值 | 适用场景 |
|-------|-----|----------|
| `$up-space-1` | 4px | 极小间距（图标与文字） |
| `$up-space-2` | 8px | 小间距（标签内边距、紧凑元素） |
| `$up-space-3` | 12px | 中小间距（表单项间） |
| `$up-space-4` | 16px | 中间距（卡片内边距、列表项） |
| `$up-space-5` | 20px | 中大间距（区块内边距） |
| `$up-space-6` | 24px | 大间距（卡片间距、区块间距） |
| `$up-space-8` | 32px | 特大间距（区块分隔） |
| `$up-space-10` | 40px | 页面边距 |
| `$up-space-12` | 48px | 大区块分隔 |

### 3.8 圆角系统

| Token | 值 | 适用场景 |
|-------|-----|----------|
| `$up-radius-xs` | 4px | 小标签、徽标数字 |
| `$up-radius-sm` | 6px | 按钮、输入框、下拉框 |
| `$up-radius-md` | 10px | 卡片、面板、对话框 |
| `$up-radius-lg` | 16px | 大卡片、侧边栏 |
| `$up-radius-xl` | 20px | 任务卡片（强调圆润感） |
| `$up-radius-full` | 9999px | 头像、胶囊按钮、Tag |

### 3.9 阴影系统

| Token | 值 | 用途 |
|-------|-----|------|
| `$up-shadow-xs` | `0 1px 2px rgba(0,0,0,0.03)` | 极小组件 |
| `$up-shadow-sm` | `0 1px 3px rgba(0,0,0,0.06)` | 小组件 |
| `$up-shadow-md` | `0 4px 12px rgba(0,0,0,0.08)` | 卡片默认 |
| `$up-shadow-lg` | `0 8px 24px rgba(0,0,0,0.10)` | 弹窗、下拉 |
| `$up-shadow-xl` | `0 16px 48px rgba(0,0,0,0.12)` | 模态框 |
| `$up-shadow-btn` | `0 4px 14px rgba(34,197,94,0.25)` | 主按钮专用 |

### 3.10 过渡动效

| Token | 值 | 用途 |
|-------|-----|------|
| `$up-ease-fast` | `0.15s ease` | 快速响应（hover） |
| `$up-ease-normal` | `0.2s cubic-bezier(0.4,0,0.2,1)` | 通用过渡 |
| `$up-ease-slow` | `0.3s cubic-bezier(0.4,0,0.2,1)` | 页面切换 |
| `$up-ease-bounce` | `0.4s cubic-bezier(0.34,1.56,0.64,1)` | 弹性效果 |

---

## 四、Token 使用规则

### 4.1 强制规则

- 页面和组件中**禁止硬编码**任何颜色值、字号、间距、圆角、阴影
- 所有样式值必须通过 `$xxx`（SCSS 变量）或 `var(--xxx)`（CSS 变量）引用
- uview-plus 组件的颜色通过覆盖主题变量控制，不单独写 style

### 4.2 引用方式

```scss
// SCSS 变量（推荐，编译时解析）
.card {
  border-radius: $up-radius-md;
  padding: $up-space-4;
  box-shadow: $up-shadow-md;
  color: $u-primary;
}

// CSS 变量（推荐，支持动态切换）
.card {
  border-radius: var(--up-radius-md);
  padding: var(--up-space-4);
}
```

### 4.3 改风格流程

1. 改主色 → 编辑 `src/styles/tokens/_colors.scss` 中的 `$u-primary` 等
2. 改字号/圆角/间距 → 编辑对应 Token 文件
3. 全局生效，无需逐个组件修改

---

## 五、响应式与断点

### 5.1 平台边界

商家端 H5 需同时覆盖 **PC Web 与移动端（同等重要）**；管理后台仅面向 PC Web。无小程序 / 原生 App 目标。

### 5.2 断点清单（以既有代码为基线，2026-09-10 全量盘点 `src/**/*.vue`）

| 断点 | 出处（文件:行） | 该档解决的具体问题 |
|------|----------------|-------------------|
| `max-width: 900px` | `pages/data-center/upload.vue:515` | 卡片栅格 3 列 → 2 列 |
| `max-width: 768px` | `components-local/stage2/ImageOptimizeModal.vue:599` | 弹窗内双栏 → 单栏（弹窗可用宽度小于视口） |
| `max-width: 600px` | `pages/index/index.vue:1342`、`pages/stage2/index.vue:740 / :893`、`pages/stage2/data-board.vue:349`、`pages/data-center/index.vue:507`、`pages/data-center/upload.vue:298 / :521`、`components-local/stage2/DataForm.vue:223`、`components-local/stage2/Stage2Sidebar.vue:625` | **移动端主断点**：侧栏转抽屉 + 固定顶栏、主内容脱离侧栏留白、栅格降单列、卡片内 nowrap 文案允许换行 |
| `max-width: 400px` | `components-local/stage2/ProductGuideModal.vue:685` | 极窄屏弹窗：缩放工具与分页角标错开，防底部重叠 |
| `max-width: 360px` | `pages/progress/index.vue:139` | 极窄屏：三列统计栅格 → 单列 |

### 5.3 最小断点集（新增样式按此选择，禁止新造断点值）

- **600px —— 移动端主断点（默认唯一断点）**：承担所有「布局形态切换」。
- 900px：仅用于「多列栅格降列」的中间档（PC 宽屏 → 中等视口）。
- 768px：仅用于弹窗（弹窗可用宽度小于视口，需早于 600px 降栏）。
- 400px / 360px：仅用于极窄屏溢出兜底（工具条错位、统计栅格降单列）。
- 优先只写 600px；仅当 600px 与 PC 之间确实需要中间形态，或弹窗/极窄屏确有独立约束时才追加其余档位，且必须在注释中写明该档解决的具体问题。

### 5.4 移动端壳层（≤600px，T-3 方案）

- **侧栏转抽屉**：`position: fixed; left: 0; width: 280px; transform: translateX(-100%)`；展开态 `translateX(0)`。DOM 完全复用既有侧栏，不重写导航结构。
- **固定顶栏**：高 56px、占满宽度（左汉堡开合 + 中当前阶段与进度摘要 + 右用户头像）。
- **遮罩与层级**：抽屉 200 > 遮罩 150 > 顶栏 100；点击遮罩收起抽屉。
- **主内容**：`margin-left: 0`，`padding-top: calc(顶栏高度 + 内容上边距)`（保留既有 `$up-space-6` 内容节奏，不贴顶栏底边）。
- **交互**：选中导航项后自动收起抽屉；抽屉展开时禁止背景滚动（H5 用 `document.body.style.overflow`，不引入新依赖）；视口跨回 >600px 时强制收起并解锁。
- **PC（>600px）零回归**：顶栏 / 遮罩基础规则即 `display: none`（不渲染、不占位），侧栏宽度、定位、层级与内容均保持原样。

### 5.5 窄视口布局约束（硬性）

- **flex 子项须显式 `min-width: 0`**：flex 项默认 `min-width: auto`，会被内容的 `min-content` 撑破容器并产生横向溢出；可收缩的 flex 子项（如主内容区 `.main-content`）必须声明 `min-width: 0`。
- 负方向位移（抽屉 `translateX(-100%)`）不产生横向溢出；正向超出必须用 `min-width: 0` + 内容换行消除，不得靠 `overflow: hidden` 掩盖。
- **验收口径**：改动前后在 375×812 / 414×896 / 768×1024 / 1440×900 下 `document.documentElement.scrollWidth === clientWidth`（无横向溢出），且 PC 视口截图 SHA256 不变。

### 5.6 落地现状与待办

- 已按本章适配（T-3 移动端壳层）：`pages/index/index.vue`（阶段一）、`pages/stage2/index.vue`、`pages/stage2/data-board.vue`、`pages/data-center/index.vue`、`pages/data-center/upload.vue`（后四者经 `components-local/stage2/Stage2Sidebar.vue` 复用同一壳层）。
- 无左侧栏壳层的页面（`pages/login/index.vue`、`pages/task/detail.vue`、`pages/data-verify/index.vue`、`pages/webview/index.vue`）不涉及 T-3，仅需按 5.5 约束自查横向溢出。
- 新增 `white-space: nowrap` 文案时须自行确认 ≤600px 表现（既有先例：`pages/stage2/index.vue` 用 600px 档位放开为 `white-space: normal`）。
