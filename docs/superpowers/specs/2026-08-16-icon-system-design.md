# 图标系统整体优化设计

日期：2026-08-16

## 1. 背景与目标

当前 Web 端图标来源混杂：桌面端 75 个文件直接引用 `@ant-design/icons`（89 个不同图标），移动端 39 个文件用 `lucide-react`，企业驾驶舱另有 10 个手绘线性 SVG，前端没有任何本地图标资产目录。部分业务语义（消防、危化品、隐患排查、应急预案等）在 AntD 中没有贴切的图标，只能退而求其次。

目标（用户已确认，两者都要）：

1. **统一视觉风格**：全系统业务图标统一为线性风格；
2. **补齐业务语义**：用 iconfont 定制图标替换语义不贴切的业务图标。

范围：**桌面 Web 端整体一起做**；移动端（lucide）留到第二阶段。

## 2. 关键决策

| 决策点 | 结论 |
|---|---|
| 风格方向 | A 线性统一（用户选定） |
| 接入方案 | 方案 1：本地 SVG + 统一 `AppIcon` 组件（双轨制） |
| 通用操作图标 | 保留 AntD（箭头、加载、编辑、删除、编辑器工具栏等） |
| 通用菜单入口 | 保留 AntD：用户管理、角色管理、系统配置、个人资料、退出登录 |
| 资产存放 | `frontend/src/assets/icons/`，SVG 存本地，不依赖 iconfont CDN |
| 版权 | 优先选「免费商用」图标；禁止转售/训练；文档记录来源 |

方案 1 的核心：业务图标全部经过 `AppIcon` 一个入口渲染，未来若升级为全量替换（方案 2），只需改 `AppIcon` 内部实现。

## 3. 现状盘点

| 范围 | 现状 |
|---|---|
| 桌面端 | 75 个文件用 `@ant-design/icons`，89 个不同图标 |
| 移动端 | `frontend/src/mobile` 39 个文件用 `lucide-react`（桌面端 0 处） |
| 驾驶舱模块导航 | `ModuleNav.tsx` 10 个手绘线性 SVG（24px 视口、描边 1.6） |
| 风险/隐患侧边导航 | `ModuleSideNav.tsx` 纯文字，无图标，不参与替换 |
| 本地资产 | `frontend/src/assets` 仅 hero.png / react.svg / vite.svg |
| 安全标志 | `backend/app/static/signs` 36 个 SVG（已有专用链路，保持不动） |

## 4. 图标资产层

### 4.1 目录与命名

选定的 24 个唯一 SVG 落盘到 `frontend/src/assets/icons/`，按用途 kebab-case 命名。AI 配置菜单与业务页 AI 标识共用 `ai.svg`。

### 4.2 SVG 清洗规则

从 iconfont 下载/内联后统一清洗：

- 去掉 `class`、内联 `style`、`version` 属性；
- 去掉硬编码 `fill` 颜色，统一由组件层以 `currentColor` 控制（单色线性图标）；
- 保留原 `viewBox`（多数 1024×1024，个别 1025/1109 宽），不做坐标缩放，避免精度损失；
- 每个文件人工抽查渲染质量，不满意的重新搜索替换。

### 4.3 完整映射表

| 用途 | 场景 | SVG 文件名 | iconfont id | iconfont 名称 |
|---|---|---|---|---|
| 基本信息 | 驾驶舱模块导航 | archive.svg | 1490623 | 档案 |
| 组织架构 | 驾驶舱模块导航 | org.svg | 29865223 | 组织架构 |
| 周边环境 | 驾驶舱模块导航 | geo.svg | 2076231 | 地图 |
| 危险化学品 | 驾驶舱模块导航 | chem.svg | 13209754 | 危化品报备 |
| 风险管控 | 驾驶舱模块导航 | risk.svg | 32835841 | 风险管控 |
| 隐患治理 | 驾驶舱模块导航 | hazard.svg | 12820186 | 隐患排查治理 |
| 应急资源 | 驾驶舱模块导航 | rescue.svg | 45446276 | 应急资源 |
| 风险评估 | 驾驶舱模块导航 | assessment.svg | 3759366 | 风险评估 |
| 资源调查 | 驾驶舱模块导航 | investigation.svg | 4423489 | 调查 |
| 预案管理 | 驾驶舱模块导航 | plan-manage.svg | 8625443 | 应急预案 |
| 工作台 | 主导航菜单 | dashboard.svg | 7215957 | 工作台 |
| 企业管理 | 主导航菜单 | enterprise.svg | 11239041 | 企业 |
| 预案列表 | 主导航菜单 | plan-list.svg | 2959108 | 应急预案 |
| 法规库管理 | 主导航菜单 | regulations.svg | 8329617 | 法律法规 |
| 数据字典管理 | 主导航菜单 | data-dict.svg | 1680700 | 数据字典 |
| 提示词管理 | 主导航菜单 | prompt.svg | 2286510 | 对话 |
| AI 配置 | 主导航菜单 | ai.svg | 5387814 | 机器人_o |
| 法律 | 法规库类型 | law.svg | 7991666 | 法律 |
| 标准 | 法规库类型 | standard.svg | 3207743 | 标准 |
| 政策 | 法规库类型 | policy.svg | 12031078 | 政策 |
| 主题 | 法规库类型 | topic.svg | 3522456 | 书本 |
| 安全防护 | 登录页等 | safety.svg | 3029239 | 安全帽 |
| 通知 | 通知/消息类 | notice.svg | 577374 | 通知 |
| 地图定位 | 位置类 | location.svg | 11372652 | 定位 |
| AI 标识 | 编辑器/聊天 AI 按钮 | ai.svg（复用） | 5387814 | 机器人_o |

## 5. AppIcon 组件

### 5.1 文件位置与接口

- `frontend/src/components/common/AppIcon.tsx`：对外组件；
- `frontend/src/components/common/icons.tsx`：集中内联 24 个 SVG 的 JSX（零新依赖、tree-shake 友好、类型安全，不使用 `?raw` + 危险注入，不依赖 CDN）。

Props：

```ts
type AppIconName =
  | "archive" | "org" | "geo" | "chem" | "risk" | "hazard" | "rescue"
  | "assessment" | "investigation" | "plan-manage" | "dashboard" | "enterprise"
  | "plan-list" | "regulations" | "data-dict" | "prompt" | "ai" | "law"
  | "standard" | "policy" | "topic" | "safety" | "notice" | "location";

interface AppIconProps {
  name: AppIconName;
  size?: number;        // 默认 16；菜单 14/16，模块导航 24/28
  className?: string;
}
```

### 5.2 渲染约定

- 输出 `<svg width={size} height={size} viewBox="…" fill="currentColor" aria-hidden="true">`；
- 装饰性图标一律 `aria-hidden`，语义信息由相邻文字承载；
- 未知 `name` 由 TS 联合类型在编译期拦截，运行时 `dev` 模式 console.warn 兜底；
- 不在组件内做任何颜色/尺寸魔法，交给调用方 CSS 与 `size`。

## 6. 迁移批次

每批独立提交，走项目门禁（`npx tsc -b`、`npx eslint`、`npx vitest run`），并对相关页面截图对比视觉回归。

| 批次 | 内容 | 涉及文件 |
|---|---|---|
| 1 | `AppIcon` + `icons.tsx` + 24 个 SVG + 组件单测 | 新增组件与资产 |
| 2 | 驾驶舱 ModuleNav 10 个手绘图标替换 | `ModuleNav.tsx` |
| 3 | 主导航 7 个业务菜单替换 | `MainLayout.tsx` |
| 4 | 法规库类型 4 个、登录页安全、通知、地图定位、AI 标识（`RobotOutlined` → `AppIcon ai`） | 法规库组件、登录布局、编辑器/聊天组件等 |

批次 2-4 完成后全量回归 + 驾驶舱 e2e 抽查。

批次 4 的具体替换点（`NotificationOutlined` / `EnvironmentOutlined` / `RobotOutlined` 等出现位置）由实现计划通过全仓 `rg` 枚举后逐一列入，只替换业务语义场景，通用操作场景保留 AntD。

## 7. 验证方案

- `AppIcon` 单测：按 `name` 渲染对应 SVG、`size` 生效、`className` 透传、未知 `name` 报错、`aria-hidden`；
- 每批：tsc / eslint / vitest + 相关页面 Playwright 截图对比；
- 全量：backend pytest（图标改动不影响后端，仅在改动后端文件时跑）、frontend 全量 vitest、驾驶舱 e2e。

## 8. 风险与对策

| 风险 | 对策 |
|---|---|
| iconfont 图标质量参差 | 落盘后逐个人工抽查，不满意重新搜索；映射表留 iconfont id 便于追溯 |
| 视口宽高比不统一（1024/1025/1456） | 保留原 viewBox，CSS 统一显示尺寸，宽高比差异可接受 |
| 批量替换回归面大 | 按批次独立提交；每批截图对比；出错用 `git undo` 回退 |
| CDN 不可用 | 方案已排除 CDN，SVG 全部本地化 |

## 9. 后续事项（不阻塞本设计）

- 移动端 lucide 图标统一为同一套语言（第二阶段，需单独设计）；
- 开工前执行 `graphify update`（当前 `graphify-out/graph.json` 已过期）；
- 实现完成后按项目惯例沉淀记忆：`project-decisions`（AppIcon 双轨制）、`global/patterns`（SVG 清洗与内联接入流程）、`global/commands`（iconfont 搜索/下载用法）。

## 10. 实现状态

（日期：2026-08-17）本设计已按实现计划落地：AppIcon + 24 个本地 SVG 资产、驾驶舱模块导航 10 项、主导航业务菜单 7 项、法规类型 4 项、AI 标识 14 处、位置/通知/安全 10 处全部替换完成；通用操作图标与 5 个通用菜单入口保留 AntD。已知遗留：部分文件存在既有 eslint lint 债（任务 8 记录）；移动端 lucide 统一为第二阶段。
