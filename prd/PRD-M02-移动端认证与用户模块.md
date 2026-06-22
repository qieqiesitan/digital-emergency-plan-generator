# PRD-M02：移动端认证与用户模块

> **版本**：1.0 | **创建日期**：2026-06-09 | **依赖**：PRD-M00, PRD-M01, PRD-01（桌面端用户权限） | **关联文档**：移动端设计方案 §5.1~5.3, §5.16

---

## 1. 模块概述

提供移动端专属的完整认证闭环：启动屏品牌展示 → 登录/注册 → Token 管理 → 个人信息维护。复用桌面端全部认证 API（PRD-01 的 7 个端点），移动端仅重写 UI 层。

**核心流程**：启动屏（Token 检测）→ 有 Token 则直接进入工作台 / 无 Token 则登录页 → 登录获取 Token → 跳转工作台

**与本模块相关的文件**：

| 文件 | 职责 |
|------|------|
| `mobile/screens/SplashScreen.tsx` | 启动屏 |
| `mobile/screens/LoginScreen.tsx` | 登录页 |
| `mobile/screens/RegisterScreen.tsx` | 注册页 |
| `mobile/components/auth/LoginForm.tsx` | 登录表单 |
| `mobile/components/auth/RegisterForm.tsx` | 注册表单 |
| `mobile/components/auth/BiometricButton.tsx` | 生物识别登录按钮 |
| `mobile/hooks/useBiometricAuth.ts` | 生物识别 Hook |
| `mobile/screens/ProfileScreen.tsx` | 个人资料页 |
| `mobile/screens/ChangePasswordScreen.tsx` | 修改密码页 |
| `contexts/AuthContext.tsx` | 共享认证上下文（与桌面端共用） |
| `services/authService.ts` | 共享认证 API 服务 |

**复用的桌面端 API**（不做任何修改）：

| 端点 | 用途 |
|------|------|
| `POST /api/v1/auth/register` | 注册 |
| `POST /api/v1/auth/login` | 登录 |
| `POST /api/v1/auth/refresh` | 刷新 Token |
| `POST /api/v1/auth/logout` | 退出 |
| `GET /api/v1/users/me` | 获取个人信息 |
| `PUT /api/v1/users/me` | 更新个人信息 |
| `PUT /api/v1/users/me/password` | 修改密码 |

---

## 2. 页面详案

### 2.1 SplashScreen（启动屏）

**文件**：`mobile/screens/SplashScreen.tsx`

**路由**：`/m/splash`（App 冷启动默认路由）

**布局**（全屏，单列居中）：

```
┌──────────────────────────────┐
│                              │
│       [SafeArea Top]         │
│                              │
│                              │
│           [Logo]             │  ← 50×50px SVG 图标
│                              │     渐显 Scale 动画 0.8→1.0
│                              │     duration: 400ms, ease: ease-out
│                              │
│      应急预案生成系统          │  ← 28px Semibold（text-h1）
│                              │     Logo 淡入完成后 100ms 后淡入
│                              │
│   GB/T 29639-2020 标准合规   │  ← 14px Caption, Neutral 400
│                              │
│                              │
│         [加载指示器]          │  ← 底部：3 个圆点脉动动画
│                              │     或 Spinner size="md"
│                              │
└──────────────────────────────┘
```

**逻辑流程**：

```
SplashScreen mount
  │
  ├─ 检查 localStorage 是否有 access_token
  │   ├─ 有 → 尝试 GET /api/v1/users/me（验证 Token 有效性）
  │   │   ├─ 200 → navigate("/m/dashboard", { replace: true })
  │   │   ├─ 401 → 尝试 POST /api/v1/auth/refresh
  │   │   │   ├─ 200 → navigate("/m/dashboard", { replace: true })
  │   │   │   └─ 401 → navigate("/m/login", { replace: true })
  │   │   └─ 网络错误 → 展示错误提示 +「重试」按钮（离线时可用缓存数据进入）
  │   └─ 无 → 等待 1.5 秒品牌展示 → navigate("/m/login", { replace: true })
```

**最长显示**：3 秒。超时未完成检测 → 直接跳转登录页。

**Props / State**：无外部 Props。所有逻辑在组件内 `useEffect` 完成。

**视觉约束**：
- Logo：SVG 内联，颜色 `var(--color-primary-600)`
- 背景：`var(--color-white)`
- 无动画背景、无渐变、无粒子效果、无品牌标语之外的任何文字
- 底部加载指示器使用 3 个圆点脉动（CSS 动画），不使用 Lottie（避免额外依赖）

---

### 2.2 LoginScreen（登录页）

**文件**：`mobile/screens/LoginScreen.tsx`

**路由**：`/m/login`

**布局**（上下分区，Form 在键盘弹出时自动上推）：

```
┌──────────────────────────────┐
│       [SafeArea Top]         │
│                              │
│  登录                         │  ← text-display (34px Bold)
│  欢迎回到应急预案管理           │  ← text-body, Neutral 600
│                              │
│                              │
│  ┌─ Input: 邮箱 ────────────┐│  ← prefixIcon: Mail
│  │                           ││     height 52px, rounded-sm
│  └───────────────────────────┘│
│                              │
│  ┌─ Input: 密码 ────────────┐│  ← prefixIcon: Lock
│  │                           ││     suffixIcon: Eye/EyeOff toggle
│  └───────────────────────────┘│
│                              │
│         忘记密码？             │  ← text-body-sm, Primary 500, 右对齐
│                              │
│  ┌───────────────────────────┐│
│  │          登录              ││  ← Button variant="primary"
│  └───────────────────────────┘│     size="lg" fullWidth
│                              │
│  ┌───────────────────────────┐│  ← BiometricButton（条件渲染）
│  │    🔐 使用面容/指纹登录    ││     仅已存 Token + 设备支持时显示
│  └───────────────────────────┘│
│                              │
│     没有账号？立即注册          │  ← text-body-sm
│                              │     "没有账号？" Neutral 600
│                              │     "立即注册" Primary 500 Link
│                              │
└──────────────────────────────┘
```

**登录中状态**：

- 登录按钮变化：文字 → `<Spinner size="sm" />` +「验证中…」
- 按钮 `disabled`
- 输入框保持可读（不清空）

**错误状态**：

- 顶部 Toast 横幅出现：红色背景 + AlertCircle 图标 + 错误信息
  - 错误码 10004：「邮箱或密码错误」
  - 错误码 10005：「账号已被禁用」
  - 网络错误：「网络连接失败，请检查网络后重试」
- Toast 出现后键盘收起

**Props**：无外部 Props。

**State**：

```typescript
interface LoginFormState {
  email: string;
  password: string;
  showPassword: boolean;
  isSubmitting: boolean;
  error: string | null;
}
```

**关键交互**：
- 邮箱 Input：`type="email"` `autocomplete="email"` `keyboardType="email-address"`
- 密码 Input：`type={showPassword ? "text" : "password"}` `autocomplete="current-password"`
- 表单验证：邮箱非空 + 密码非空 + 密码 ≥ 8 位（before API call）
- 登录成功：存储 Token → `navigate("/m/dashboard", { replace: true })`
- 键盘「完成」按钮：触发登录

---

### 2.3 BiometricButton（生物识别登录）

**文件**：`mobile/components/auth/BiometricButton.tsx`

**显示条件**：
1. 用户之前登录过（localStorage 有 refresh_token）
2. 设备支持 WebAuthn / 平台认证

**逻辑**：

```typescript
// mobile/hooks/useBiometricAuth.ts
function useBiometricAuth() {
  const isAvailable: boolean;    // 设备是否支持
  const savedEmail: string | null; // 上次登录的邮箱

  async function authenticate(): Promise<{
    success: boolean;
    email?: string;
    error?: string;
  }>;
}
```

- 点击 BiometricButton → 调用 `navigator.credentials.get()` → 获取平台凭据
- 凭据中提取邮箱 → 自动填充邮箱 → 用存储的 refresh_token 换新 Token
- 换 Token 成功 → 直接进入工作台
- 换 Token 失败 → 回退到手动密码输入

**视觉**：

- `<Button variant="secondary" size="lg" fullWidth icon={<Fingerprint />}>使用面容/指纹登录</Button>`
- 加载态：图标变为 Spinner
- 失败态：红色 Toast「生物识别失败，请使用密码登录」

---

### 2.4 RegisterScreen（注册页）

**文件**：`mobile/screens/RegisterScreen.tsx`

**路由**：`/m/register`

**布局**（与 LoginScreen 一致结构）：

```
┌──────────────────────────────┐
│       [SafeArea Top]         │
│                              │
│  创建账号                     │  ← text-display
│  开始管理您的应急预案          │  ← text-body
│                              │
│  ┌─ Input: 姓名 ────────────┐│
│  └───────────────────────────┘│
│                              │
│  ┌─ Input: 邮箱 ────────────┐│
│  └───────────────────────────┘│
│                              │
│  ┌─ Input: 密码 ────────────┐│
│  └───────────────────────────┘│
│  ≥8位 含字母和数字 两次密码一致 │  ← 3 个 Chip 实时校验指示器
│                              │
│  ┌─ Input: 确认密码 ────────┐│
│  └───────────────────────────┘│
│                              │
│  ┌───────────────────────────┐│
│  │          注册              ││  ← 所有校验通过后才可点击
│  └───────────────────────────┘│     (disabled = 灰色直到通过)
│                              │
│     已有账号？去登录           │
│                              │
└──────────────────────────────┘
```

**密码实时校验指示器**（3 个 Chip，位于密码 Input 下方 8px）：

```
≥8位    [✓] ← 内联检测，通过 → Chip variant="selected"（success 色）
含字母和数字 [✓] ← 同上
两次密码一致 [✓] ← 确认密码 blur 后检测
```

每个 Chip：32px 高，`rounded-full`，12px 字。未通过 → `Chip variant="default"`（灰色），通过 → `Chip variant="selected"`（绿色变体）。

**注册成功**：

- 自动调用 `POST /api/v1/auth/login`（使用注册时的邮箱+密码）
- 登录成功 → `navigate("/m/dashboard", { replace: true })`
- 无需用户再手动登录

**错误处理**：

- 10001（邮箱已注册）：Input 下方 error 提示「该邮箱已被注册」
- 10002（密码不符合要求）：前端已拦截（Chip 校验），不会触发
- 10003（两次密码不一致）：前端已拦截，不会触发
- 网络错误：Toast

---

### 2.5 ProfileScreen（个人资料页）

**文件**：`mobile/screens/ProfileScreen.tsx`

**路由**：`/m/settings/profile`

**布局**：

```
┌──────────────────────────────┐
│ ← 个人资料                    │  ← NavBar
├──────────────────────────────┤
│                              │
│         [Avatar lg]          │  ← 72px 首字母头像
│         张                    │
│                              │
│  ┌─ 姓名 ───────────────────┐│
│  │ 张三                [编辑] ││  ← 点击进入编辑模式（inline）
│  └───────────────────────────┘│
│                              │
│  ┌─ 邮箱 ───────────────────┐│
│  │ user@example.com    🔒   ││  ← 只读，灰色文字
│  └───────────────────────────┘│
│                              │
│  ┌─ 注册时间 ───────────────┐│
│  │ 2026-06-05               ││  ← 只读
│  └───────────────────────────┘│
│                              │
│  ┌───────────────────────────┐│
│  │        修改密码            ││  ← 跳转 ChangePasswordScreen
│  └───────────────────────────┘│
│                              │
│  ┌───────────────────────────┐│
│  │        退出登录            ││  ← Button variant="danger" ghost
│  └───────────────────────────┘│
│                              │
└──────────────────────────────┘
```

**姓名编辑**：点击「编辑」→ 文字变成 Input + 右侧「保存」文字按钮。保存调用 `PUT /api/v1/users/me`。

---

### 2.6 ChangePasswordScreen（修改密码页）

**文件**：`mobile/screens/ChangePasswordScreen.tsx`

**路由**：`/m/settings/password`

**表单**（同注册页校验逻辑）：

- 原密码：`type="password"` + toggle
- 新密码：`type="password"` + toggle + 3 Chip 实时校验
- 确认新密码：`type="password"` + toggle

**修改成功**：

- Toast：绿色「密码已修改，请重新登录」
- 清除所有 Token → `navigate("/m/login", { replace: true })`

**错误处理**：

- 10007（原密码错误）：Input error「原密码错误」

---

## 3. AuthGuard（路由守卫）

**文件**：`mobile/components/auth/AuthGuard.tsx`（或在 `mobile/MobileApp.tsx` 内联）

```typescript
function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();  // 来自共享 AuthContext

  if (isLoading) {
    return <SplashScreen />;
  }

  if (!user) {
    return <Navigate to="/m/login" replace />;
  }

  return <>{children}</>;
}
```

**所有 `/m/*` 路由（除 `/m/login`、`/m/register`、`/m/splash` 外）均包裹 AuthGuard。**

---

## 4. 无障碍

- 所有输入框关联 `<label>`（通过 `htmlFor` 或 `aria-label`）
- 登录/注册按钮：`aria-label="登录"` / `aria-label="注册"`
- 错误 Toast：`role="alert"` `aria-live="assertive"`
- 密码切换按钮：`aria-label={showPassword ? "隐藏密码" : "显示密码"}`
- 生物识别按钮：`aria-label="使用面容或指纹登录"`

---

## 5. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| M02-01 | Splash 有 Token 且有效 → 自动跳转 Dashboard | 自动化 |
| M02-02 | Splash 无 Token → 1.5s 品牌展示 → 跳转 Login | 自动化 |
| M02-03 | Splash Token 过期 → 自动 Refresh → 成功跳转 | 自动化 |
| M02-04 | Splash Refresh 也过期 → 跳转 Login | 自动化 |
| M02-05 | 登录成功 → Token 存储 + 跳转 Dashboard | 自动化 |
| M02-06 | 错误邮箱/密码 → 红色 Toast + 按钮恢复 | 自动化 |
| M02-07 | 注册 → 表单校验 → 成功自动登录 → 跳转 Dashboard | 自动化 |
| M02-08 | 密码 Chip 校验实时正确（3 项全部通过才能点注册） | 手动 |
| M02-09 | 重复邮箱注册 → Input error「该邮箱已被注册」 | 自动化 |
| M02-10 | 生物识别：有 Token + 设备支持 → 按钮可见 + 认证成功跳转 | iOS Safari + Android Chrome |
| M02-11 | 修改姓名 → API 调用成功 → 页面更新 | 自动化 |
| M02-12 | 修改密码 → 清除 Token → 跳转登录页 | 自动化 |
| M02-13 | 退出登录 → 清除 Token → 跳转登录页 | 自动化 |
| M02-14 | 未登录直接访问 `/m/dashboard` → 跳转 `/m/login` | 自动化 |
| M02-15 | 键盘弹出时登录表单自动上推，不遮挡输入框 | 真机测试 |
| M02-16 | 密码可见/不可见切换正常工作 | 手动 |
| M02-17 | 视觉铁律：无渐变、无彩色阴影、无 > 12px 圆角 | 代码审查 |
| M02-18 | Toast 4 秒后自动消失 | 手动 |

---

> **下一文档**：PRD-M03 移动端工作台
