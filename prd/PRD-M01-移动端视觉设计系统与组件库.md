# PRD-M01：移动端视觉设计系统与组件库

> **版本**：1.0 | **创建日期**：2026-06-09 | **依赖**：PRD-M00 | **关联文档**：移动端设计方案 §2 视觉设计系统

---

## 1. 模块概述

本模块定义移动端全部 Design Token 和基础 UI 组件。所有页面 Screen 和业务组件均基于此模块构建。

**核心原则（逐条强制执行）**：
1. 不引入第三方 UI 组件库（Ant Design / MUI 等），100% 自研
2. 所有组件必须通过本 PRD 定义的 Props 接口开发
3. 所有样式来自 Tailwind 原子类或 `tokens.css` 的 CSS 变量
4. 禁止组件内硬编码颜色值、字号、间距 —— 必须引用 Token

### 设计风格铁律（代码审查检查项）

以下约束必须体现在每个组件的实现中：

| 规则 | 违规示例 | 正确做法 |
|------|----------|----------|
| 禁止渐变背景 | `bg-gradient-to-r` | `bg-neutral-50` / `bg-white` |
| 禁止玻璃拟态 | `backdrop-blur` `bg-opacity-80` | 纯色背景（TabBar 除外） |
| 禁止彩色投影 | `shadow-blue-500` | `shadow-card`（`rgba(0,0,0,...)`） |
| 禁止 > 12px 圆角 | `rounded-2xl` (16px) | `rounded-md` (8px) / `rounded-lg` (12px) |
| 禁止装饰元素 | 额外 SVG 装饰、分隔花纹 | 无额外装饰 |
| 禁止花哨动画 | `animate-bounce` `animate-pulse` | 仅 `animate-spin`（Spinner）和骨架屏脉冲 |
| 禁止手写/装饰字体 | `font-serif` `font-mono` | `font-sans`（系统字体栈） |
| 禁止非 Token 颜色 | `text-[#abc123]` | `text-primary-600` `text-neutral-400` |

---

## 2. Design Token（CSS 变量）

### 2.1 文件：`mobile/styles/tokens.css`

```css
:root {
  /* ===== 色彩 ===== */
  --color-primary-600: #1A56DB;
  --color-primary-500: #3B82F6;
  --color-primary-50: #EFF6FF;

  --color-neutral-900: #111827;
  --color-neutral-600: #4B5563;
  --color-neutral-400: #9CA3AF;
  --color-neutral-100: #F3F4F6;
  --color-neutral-50: #F9FAFB;

  --color-danger: #DC2626;
  --color-warning: #F59E0B;
  --color-success: #10B981;
  --color-info: #6366F1;

  --color-white: #FFFFFF;
  --color-black: #000000;

  /* ===== 圆角 ===== */
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-full: 9999px;

  /* ===== 间距 ===== */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 32px;

  /* ===== 安全区 ===== */
  --safe-top: env(safe-area-inset-top, 0px);
  --safe-bottom: env(safe-area-inset-bottom, 0px);

  /* ===== 布局 ===== */
  --tabbar-height: 56px;
  --navbar-height: 44px;
  --navbar-large-height: 56px;

  /* ===== 阴影 ===== */
  --shadow-card: 0 1px 3px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.06);
  --shadow-modal: 0 20px 25px rgba(0, 0, 0, 0.1), 0 10px 10px rgba(0, 0, 0, 0.04);
  --shadow-fab: 0 4px 12px rgba(26, 86, 219, 0.35);
  --shadow-none: none;

  /* ===== 过渡 ===== */
  --transition-fast: 150ms ease;
  --transition-normal: 250ms ease;
  --transition-slow: 350ms ease;
}
```

---

## 3. 基础 UI 组件规范

### 3.1 Button

```typescript
// 文件：mobile/components/ui/Button.tsx

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: React.ReactNode;           // 左侧图标 (Lucide)
  fullWidth?: boolean;
  children?: React.ReactNode;
}
```

**视觉规范**：

| 属性 | primary | secondary | danger | ghost |
|------|---------|-----------|--------|-------|
| 背景 | `var(--color-primary-600)` | `var(--color-white)` | `var(--color-danger)` | transparent |
| 文字 | `var(--color-white)` | `var(--color-primary-600)` | `var(--color-white)` | `var(--color-primary-600)` |
| 边框 | none | 1px `var(--color-primary-500)` | none | none |
| Hover | 加深 8% | `var(--color-primary-50)` bg | 加深 8% | `var(--color-primary-50)` bg |
| Active | scale(0.98) | scale(0.98) | scale(0.98) | scale(0.98) |
| Disabled | opacity 0.4 | opacity 0.4 | opacity 0.4 | opacity 0.4 |
| Loading | Spinner + 禁止点击 | Spinner + 禁止点击 | Spinner + 禁止点击 | Spinner + 禁止点击 |

**尺寸**：

| 尺寸 | 高度 | 内边距（水平） | 字号 | 圆角 |
|------|------|---------------|------|------|
| sm | 36px | 12px | 14px | `var(--radius-sm)` |
| md | 44px | 16px | 16px | `var(--radius-sm)` |
| lg | 52px | 20px | 16px | `var(--radius-sm)` |

**Tailwind 实现示例**：

```tsx
const variantClasses: Record<ButtonVariant, string> = {
  primary: "bg-primary-600 text-white hover:brightness-90 active:scale-[0.98]",
  secondary: "bg-white text-primary-600 border border-primary-500 hover:bg-primary-50 active:scale-[0.98]",
  danger: "bg-danger text-white hover:brightness-90 active:scale-[0.98]",
  ghost: "bg-transparent text-primary-600 hover:bg-primary-50 active:scale-[0.98]",
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "h-9 px-3 text-body-sm rounded-sm",
  md: "h-11 px-4 text-body rounded-sm",
  lg: "h-[52px] px-5 text-body rounded-sm",
};
```

**Props 驱动示例（消费者代码）**：

```tsx
<Button variant="primary" size="lg" fullWidth loading={isSubmitting}>
  登录
</Button>

<Button variant="secondary" icon={<Download size={20} />}>
  导出文档
</Button>

<Button variant="ghost" size="sm">
  取消
</Button>
```

---

### 3.2 Input

```typescript
// 文件：mobile/components/ui/Input.tsx

type InputType = "text" | "email" | "password" | "number" | "tel" | "search";

interface InputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "size"> {
  label?: string;
  error?: string;                  // 错误信息文本，非空时显示错误态
  hint?: string;                   // 底部辅助提示
  prefixIcon?: React.ReactNode;    // 左侧图标
  suffixIcon?: React.ReactNode;    // 右侧图标（会与 password toggle 冲突）
  showPasswordToggle?: boolean;    // 密码可见/不可见切换
  fullWidth?: boolean;
}
```

**视觉规范**：

| 状态 | 边框 | 背景 | 文字 |
|------|------|------|------|
| Default | 1px `var(--color-neutral-100)` | `var(--color-white)` | `var(--color-neutral-900)` |
| Focus | 2px `var(--color-primary-500)` | `var(--color-white)` | — |
| Error | 2px `var(--color-danger)` | `var(--color-white)` | — |
| Disabled | 1px `var(--color-neutral-100)` | `var(--color-neutral-50)` | `var(--color-neutral-400)` |

**固定尺寸**：高度 52px，内边距 16px（水平），圆角 `var(--radius-sm)`，字号 `text-body`。

**实现关键点**：
- 前缀/后缀图标区域：44×44px 点击区
- 密码切换图标使用 Lucide `Eye` / `EyeOff`
- 标签文字：`text-body-sm text-neutral-600`，位于 Input 上方 8px
- 错误信息：`text-caption text-danger`，位于 Input 下方 4px

---

### 3.3 NavBar

```typescript
// 文件：mobile/components/ui/NavBar.tsx

interface NavBarProps {
  title: string;
  showBack?: boolean;
  onBack?: () => void;
  rightActions?: Array<{
    icon: React.ReactNode;
    onPress: () => void;
    label?: string;                              // 无障碍标签
  }>;
  largeTitle?: boolean;                          // 大标题模式
  border?: boolean;                              // 是否显示底部边框
}
```

**视觉规范**：

- 标准模式：高度 44px，背景 `var(--color-white)`，底部 1px `var(--color-neutral-100)` 边框
- 大标题模式：高度 56px，标题字号 `text-display`（34px Bold），无底部边框
- 返回按钮：左侧 44×44px 点击区，`ArrowLeft` 图标 24px
- 标题居中，`text-h3` Semibold，单行省略
- 右侧按钮：最多 2 个，每个 44×44px 点击区，间距 4px

**大标题滚动行为（平台级行为，需要 `useScroll` 集成）**：
- 页面滚动 > 20px 时，大标题淡出，切换到标准 NavBar（标题变小 + 出现边框）
- Framer Motion `useScroll` + `useTransform` 实现

---

### 3.4 TabBar

```typescript
// 文件：mobile/components/ui/TabBar.tsx

interface TabItem {
  key: string;
  icon: React.ReactNode;            // Lucide 图标组件
  activeIcon?: React.ReactNode;     // 选中态图标（fill 版本）
  label: string;
  badge?: number;                   // 徽章数字
}

interface TabBarProps {
  items: TabItem[];
  activeKey: string;
  onChange: (key: string) => void;
}
```

**视觉规范**：

- 固定底部，高度 `var(--tabbar-height)`（56px）
- 背景：`rgba(255,255,255,0.85)` + `backdrop-filter: blur(20px)`（唯一允许的毛玻璃效果）
- 顶部：`0 -1px 0 rgba(0,0,0,0.06)`（细线，非投影）
- Tab 项：flex 等分，每个包含图标（24px）+ 标签（10px Caption）
- 选中态：图标 + 标签 `var(--color-primary-600)`，图标缩放动画 1.0→1.15（150ms）
- 非选中态：`var(--color-neutral-400)`
- 选中 Tab 顶部：2px 高 `var(--color-primary-600)` 指示条
- Badge：红色圆点或数字，位于图标右上角

**内置配置**（4 个 Tab）：

```tsx
const MAIN_TABS: TabItem[] = [
  { key: "dashboard", icon: <LayoutDashboard />, label: "工作台" },
  { key: "enterprises", icon: <Building2 />, label: "企业" },
  { key: "plans", icon: <FileText />, label: "预案" },
  { key: "settings", icon: <Settings />, label: "设置" },
];
```

---

### 3.5 Card

```typescript
// 文件：mobile/components/ui/Card.tsx

interface CardProps {
  children: React.ReactNode;
  pressable?: boolean;             // 是否可点击（显示按下态）
  selected?: boolean;              // 选中态
  className?: string;
  onClick?: () => void;
}
```

**视觉规范**：

- 背景：`var(--color-white)`
- 圆角：`var(--radius-md)`（8px）
- 阴影：`var(--shadow-card)`
- 内边距：`var(--space-md)`（16px）
- Pressable：`cursor-pointer` + active 态 `scale-[0.99]` + `brightness-[0.98]`
- Selected：2px `var(--color-primary-500)` 边框 + `var(--color-primary-50)` 背景

---

### 3.6 BottomSheet

```typescript
// 文件：mobile/components/ui/BottomSheet.tsx

interface BottomSheetProps {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
  height?: "auto" | "40%" | "60%" | "90%";   // 内容高度 / 视口高度
  showHandle?: boolean;                        // 拖拽指示条
}
```

**视觉规范**：

- 背景遮罩：`rgba(0,0,0,0.3)`，点击关闭
- 面板背景：`var(--color-white)`
- 圆角：`var(--radius-lg)`（12px），仅顶部两角
- 拖拽指示条：36px 宽 × 4px 高，`var(--color-neutral-300)`，`var(--radius-full)`
- 动画：Framer Motion `animate={{ y: open ? 0 : "100%" }}`，duration 0.3s，ease "easeOut"
- 内容区：`overflow-y-auto` + `padding-bottom: var(--safe-bottom)`

---

### 3.7 Skeleton

```typescript
// 文件：mobile/components/ui/Skeleton.tsx

type SkeletonVariant = "text" | "circle" | "card" | "list-item";

interface SkeletonProps {
  variant?: SkeletonVariant;
  width?: string | number;
  height?: string | number;
  count?: number;                // 列表项骨架时重复次数
}
```

**视觉规范**：

- 背景：`var(--color-neutral-100)`
- 动画：脉冲 `opacity: 1 ↔ 0.4`，周期 1.5s，`ease-in-out`
- 圆角：`var(--radius-sm)`（text/list）/ `var(--radius-full)`（circle）
- Card 骨架：`<div className="w-full h-24 rounded-md bg-neutral-100 animate-skeleton-pulse" />`
- List-item 骨架：圆形（头像）+ 两行文字

---

### 3.8 Toast

```typescript
// 文件：mobile/components/ui/Toast.tsx

type ToastType = "success" | "error" | "warning" | "info";

interface ToastOptions {
  type: ToastType;
  message: string;
  duration?: number;            // 默认 4000ms
}

// 通过 Context + Hook 调用
interface ToastContextValue {
  showToast: (options: ToastOptions) => void;
}

function useToast(): ToastContextValue;
```

**视觉规范**：

- 位置：顶部，距安全区 8px
- 动画：从顶部滑入 + 淡入（Framer Motion）
- 背景色：success=`var(--color-success)` / error=`var(--color-danger)` / warning=`var(--color-warning)` / info=`var(--color-info)`
- 文字：`var(--color-white)`，14px
- 左侧图标：CheckCircle / AlertCircle / AlertTriangle / Info，20px
- 自动消失：4 秒（可配置），支持上滑手势关闭
- 最多同时显示 1 条（新 Toast 替换旧 Toast）

---

### 3.9 EmptyState

```typescript
// 文件：mobile/components/ui/EmptyState.tsx

interface EmptyStateProps {
  icon?: React.ReactNode;        // 默认：相关功能图标
  title: string;
  description?: string;
  action?: {
    label: string;
    onPress: () => void;
  };
}
```

**视觉规范**：

- 布局：flex-col，居中，距顶部约 35% 视口高度
- 图标：48px，`var(--color-neutral-300)`
- 标题：`text-h3`，`var(--color-neutral-900)`，距图标 16px
- 描述：`text-body-sm`，`var(--color-neutral-400)`，距标题 8px
- 操作按钮：`<Button variant="primary" size="md">`，距描述 16px

---

### 3.10 Badge

```typescript
// 文件：mobile/components/ui/Badge.tsx

type BadgeVariant = "default" | "success" | "warning" | "danger" | "info";

interface BadgeProps {
  variant?: BadgeVariant;
  children: React.ReactNode;       // 标签文字
  dot?: boolean;                   // 圆点模式（替代文字）
  count?: number;                  // 数字模式（TabBar 徽章）
}
```

**视觉规范（标签模式）**：

| variant | 背景 | 文字色 |
|---------|------|--------|
| default | `var(--color-neutral-100)` | `var(--color-neutral-600)` |
| success | `#D1FAE5` | `#065F46` |
| warning | `#FEF3C7` | `#92400E` |
| danger | `#FEE2E2` | `#991B1B` |
| info | `#E0E7FF` | `#3730A3` |

- 圆角：`var(--radius-full)`
- 内边距：2px 8px
- 字号：`text-caption`（12px Medium）

**圆点模式**：8px 直径圆点，用于列表项状态指示

**数字模式**：16px 高 × 最小 16px 宽，`var(--color-danger)` 背景，白色文字 10px

---

### 3.11 Chip

```typescript
// 文件：mobile/components/ui/Chip.tsx

type ChipVariant = "default" | "selected";

interface ChipProps {
  variant?: ChipVariant;
  label: string;
  icon?: React.ReactNode;
  onRemove?: () => void;          // 显示关闭按钮
  onClick?: () => void;
}
```

**视觉规范**：

- Default：`var(--color-neutral-100)` 背景，`var(--color-neutral-600)` 文字
- Selected：`var(--color-primary-50)` 背景，`var(--color-primary-600)` 文字，1px `var(--color-primary-500)` 边框
- 高度：32px，内边距：8px 12px
- 圆角：`var(--radius-full)`
- 字号：`text-body-sm`
- 关闭按钮：`X` 图标 14px，`var(--color-neutral-400)`，44px 点击区
- 间距：相邻 Chip 间距 8px，可横向滚动

---

### 3.12 SegmentedControl

```typescript
// 文件：mobile/components/ui/SegmentedControl.tsx

interface SegmentedControlProps {
  options: Array<{ value: string; label: string }>;
  value: string;
  onChange: (value: string) => void;
}
```

**视觉规范**：

- 整体：`var(--color-neutral-100)` 背景，`var(--radius-md)` 圆角，2px 内边距
- 单个选项：均分宽度，32px 高，`var(--radius-sm)` 圆角
- 选中态：`var(--color-white)` 背景 + `var(--shadow-card)` + `var(--color-primary-600)` 文字 + 字重 600
- 非选中态：透明背景，`var(--color-neutral-600)` 文字 + 字重 400
- 切换动画：Framer Motion `layoutId` 实现滑块平滑移动，duration 200ms
- 字号：`text-body-sm`
- 选项 ≤ 5

---

### 3.13 FAB

```typescript
// 文件：mobile/components/ui/FAB.tsx

interface FABProps {
  icon: React.ReactNode;
  onClick: () => void;
  mini?: boolean;                           // 小号（40px）
  extended?: boolean;                       // 扩展模式（含文字标签）
  label?: string;                           // 扩展模式的文字
  speedDialActions?: Array<{               // Speed Dial 菜单项
    icon: React.ReactNode;
    label: string;
    onPress: () => void;
  }>;
}
```

**视觉规范**：

- 位置：`position: fixed`，右下角，距右 16px，距底 16px + `var(--safe-bottom)` + `var(--tabbar-height)`
- 默认尺寸：56×56px 圆形，`var(--radius-full)`
- Mini 尺寸：40×40px 圆形
- 背景：`var(--color-primary-600)`
- 图标：24px 白色
- 阴影：`var(--shadow-fab)`
- 点击态：`scale(0.95)` + 旋转 45°（如果是 `plus` 图标 → `x`）
- Speed Dial：FAB 上方依次展开 3 个操作项，每项含图标 + 文字标签，从下往上 stagger 动画

---

### 3.14 Spinner

```typescript
// 文件：mobile/components/ui/Spinner.tsx

type SpinnerSize = "sm" | "md" | "lg";

interface SpinnerProps {
  size?: SpinnerSize;
  color?: string;                // 默认 var(--color-primary-600)
}
```

**视觉规范**：

| 尺寸 | 直径 | 描边宽度 |
|------|------|----------|
| sm | 16px | 2px |
| md | 24px | 2.5px |
| lg | 32px | 3px |

- 动画：CSS `animation: spin 1s linear infinite`
- 使用 Lucide `Loader2` 图标旋转（而不是手写 SVG）

---

### 3.15 ProgressBar

```typescript
// 文件：mobile/components/ui/ProgressBar.tsx

interface ProgressBarProps {
  value: number;                 // 0-100
  indeterminate?: boolean;       // 不确定模式（来回扫描）
  size?: "sm" | "md";
  color?: string;                // 默认 var(--color-primary-600)
}
```

**视觉规范**：

- 轨道：`var(--color-neutral-100)` 背景，2px（sm）/ 4px（md）高，`var(--radius-full)`
- 进度条：`var(--color-primary-600)` 背景，`var(--radius-full)`
- Indeterminate：1/3 宽度的渐变条左右来回滑动，动画周期 1.5s
- 宽度：100% 父容器

---

### 3.16 Avatar

```typescript
// 文件：mobile/components/ui/Avatar.tsx

type AvatarSize = "sm" | "md" | "lg";

interface AvatarProps {
  src?: string;
  name?: string;                 // 首字母回退（中文取第一个字）
  size?: AvatarSize;
  colorSeed?: string;            // 用于确定背景色（基于哈希）
}
```

**视觉规范**：

| 尺寸 | 直径 | 字号 |
|------|------|------|
| sm | 32px | 14px |
| md | 44px | 17px |
| lg | 72px | 28px |

- 背景色：6 色预设循环（`#DBEAFE`, `#D1FAE5`, `#FEE2E2`, `#FEF3C7`, `#E0E7FF`, `#FCE7F3`）
  - 通过 `name.charCodeAt(0) % 6` 确定
- 文字色：对应背景色的深色版本
- 图片模式：`<img>` 填充，`object-cover`

---

### 3.17 Switch

```typescript
// 文件：mobile/components/ui/Switch.tsx

interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}
```

**视觉规范**：

- 轨道：44px 宽 × 24px 高，`var(--radius-full)`
- 关闭轨：`var(--color-neutral-100)` 背景
- 开启轨：`var(--color-primary-600)` 背景
- 滑块：20×20px 圆形白色，`var(--shadow-card)`，距轨边缘 2px
- 过渡：`var(--transition-fast)`，滑块平移动画

---

### 3.18 SelectSheet（基于 BottomSheet 的选择器）

```typescript
// 文件：mobile/components/ui/SelectSheet.tsx

interface SelectOption {
  value: string;
  label: string;
  description?: string;
}

interface SelectSheetProps {
  open: boolean;
  onClose: () => void;
  options: SelectOption[];
  value: string | null;
  onChange: (value: string) => void;
  title?: string;
}
```

**视觉规范**：

- 基于 BottomSheet，高度 "auto"
- 标题：`text-h3`，居中，距顶 16px
- 选项列表：每项 52px 高，`text-body`，左对齐
- 选中项：右侧 `Check` 图标，`var(--color-primary-600)`，选项文字变 `var(--color-primary-600)` Semibold
- 分割线：1px `var(--color-neutral-100)`，仅选项之间
- 最大高度内可滚动

---

### 3.19 SafeArea

```typescript
// 文件：mobile/components/ui/SafeArea.tsx

type SafeAreaEdge = "top" | "bottom" | "both";

interface SafeAreaProps {
  edge?: SafeAreaEdge;
  children: React.ReactNode;
}
```

**用途**：包裹需要避开刘海/底部指示器的区域。渲染为 `<div>` 并在对应方向应用 `padding-top` / `padding-bottom` 值为 CSS 变量 `--safe-top` / `--safe-bottom`。

---

## 4. 业务组件（骨架定义）

### 4.1 EnterpriseCard

```typescript
// 文件：mobile/components/enterprise/EnterpriseCard.tsx
interface EnterpriseCardProps {
  enterprise: {
    id: string;
    name: string;
    industry: string;
    region: string;
    planCounts: { comprehensive: number; special: number; onsite: number };
  };
  onPress: () => void;
  onCreatePlan: () => void;
}
```

### 4.2 PlanCard

```typescript
// 文件：mobile/components/plan/PlanCard.tsx
interface PlanCardProps {
  plan: {
    id: string;
    title: string;
    planType: "comprehensive" | "special" | "onsite";
    status: "draft" | "generating" | "completed";
    updatedAt: string;
  };
  onPress: () => void;
}
```

### 4.3 ChapterTree

```typescript
// 文件：mobile/components/plan/ChapterTree.tsx
interface ChapterTreeProps {
  chapters: ChapterNode[];
  onSelect: (chapter: ChapterNode) => void;
}
```

### 4.4 MobileEditor

```typescript
// 文件：mobile/components/plan/MobileEditor.tsx
interface MobileEditorProps {
  content: string;
  onChange: (markdown: string) => void;
  readOnly?: boolean;
  placeholder?: string;
  onAIGenerate?: () => void;
}
```

### 4.5 AIGenerationSheet

```typescript
// 文件：mobile/components/plan/AIGenerationSheet.tsx
interface AIGenerationSheetProps {
  open: boolean;
  onClose: () => void;
  planId: string;
  sectionKey: string;
  sectionName: string;
  availableChapters?: Array<{ key: string; name: string }>;
  multiMode?: boolean;
  onGenerate: (selectedChapters: string[]) => void;
}
```

---

## 5. CSS 基础重置

### 5.1 文件：`mobile/styles/base.css`

```css
*,
*::before,
*::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html {
  -webkit-text-size-adjust: 100%;
  -webkit-tap-highlight-color: transparent;
  font-family: "Inter", "SF Pro Display", -apple-system, BlinkMacSystemFont,
    "PingFang SC", "Microsoft YaHei", sans-serif;
  font-size: 16px;
  line-height: 1.5;
  color: var(--color-neutral-900);
  background-color: var(--color-neutral-50);
}

body {
  min-height: 100dvh;
  overflow-x: hidden;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

input,
textarea,
button,
select {
  font: inherit;
  color: inherit;
}

button {
  cursor: pointer;
  border: none;
  background: none;
}

a {
  color: inherit;
  text-decoration: none;
}

img {
  max-width: 100%;
  display: block;
}

/* 隐藏滚动条但保留滚动能力 */
.hide-scrollbar {
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.hide-scrollbar::-webkit-scrollbar {
  display: none;
}

/* 安全区工具类 */
.safe-top {
  padding-top: var(--safe-top);
}
.safe-bottom {
  padding-bottom: var(--safe-bottom);
}

/* 骨架屏脉冲 */
@keyframes skeleton-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.animate-skeleton-pulse {
  animation: skeleton-pulse 1.5s ease-in-out infinite;
}
```

---

## 6. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| M01-01 | Button: 4 种 variant × 3 种 size × loading/disabled/icon/fullWidth 全部正确渲染 | 组件 Story / 截图对比 |
| M01-02 | Input: 5 种 type + error/disabled/focus 状态 + prefix/suffix icon | 同上 |
| M01-03 | NavBar: 标准/大标题模式 + 返回按钮 + 右侧操作 | 同上 |
| M01-04 | TabBar: 4 Tab 切换高亮 + Badge + 毛玻璃背景 | 同上 |
| M01-05 | Card: default/pressable/selected 三态 | 同上 |
| M01-06 | BottomSheet: 弹出/关闭动画 + 遮罩点击关闭 + 拖拽指示条 | 同上 |
| M01-07 | Skeleton: 4 种 variant + 脉冲动画 | 同上 |
| M01-08 | Toast: 4 种 type + 自动消失 + 手势关闭 | 同上 |
| M01-09 | EmptyState: 图标+标题+描述+操作按钮 | 同上 |
| M01-10 | Badge/Chip/SegmentedControl/FAB/Spinner/ProgressBar/Avatar/Switch 全部渲染正确 | 同上 |
| M01-11 | 所有组件不包含硬编码颜色值（grep 检查 CSS） | `rg "bg-\[#" mobile/components/ui/` 返回空 |
| M01-12 | 设计铁律逐条通过：零渐变、零彩色投影、零 > 12px 圆角、零装饰元素 | 代码审查 |
| M01-13 | 所有颜色引用来自 `tokens.css` 或 Tailwind 主题 | 代码审查 |
| M01-14 | 组件在 375px 和 428px 宽度均无溢出/重叠 | Playwright mobile viewport |

---

> **下一文档**：PRD-M02 移动端认证模块
