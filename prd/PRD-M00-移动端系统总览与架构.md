# PRD-M00：移动端系统总览与架构

> **版本**：1.0 | **创建日期**：2026-06-09 | **依赖**：PRD-00（桌面端系统总览）、PRD-01~12 全部桌面端 PRD | **关联文档**：移动端设计方案 v1.0

---

## 1. 产品概述

### 1.1 产品定义

「数字化应急预案自动生成系统 — 移动版」是桌面端 Web 应用的移动端延伸。用户通过手机浏览器或 PWA 安装完成企业安全数据管理、AI 预案生成、文档导出的全流程操作。

**核心定位**：轻量化 + 全功能。不做功能阉割的「简化版」，而是针对移动端交互特点重新设计的完整产品。

### 1.2 与桌面端的关系

| 维度 | 桌面端 | 移动端 |
|------|--------|--------|
| 用户 | 相同（企业安全管理人员） | 相同 |
| 后端 API | 同一套 `/api/v1/*` | 完全复用，零新增 |
| 数据库 | 同一个 PostgreSQL | 完全复用 |
| 前端工程 | `frontend/src/` | 同一工程 `frontend/src/mobile/` |
| 构建产物 | 桌面端 SPA | 独立 PWA（同一 `vite build` — `manualChunks` 分离） |
| 入口分发 | `App.tsx` | `main.tsx` 根据 UA/屏幕宽度选择 `MobileApp` 或 `DesktopApp` |

### 1.3 设计风格：高端视觉

**强制执行的高端视觉设计约束**（贯穿所有移动端 PRD）：

1. **无渐变背景**：不使用任何渐变作为页面背景或卡片背景。纯色背景：`#F9FAFB`（页面）、`#FFFFFF`（卡片）。
2. **无玻璃拟态**：不使用 `backdrop-filter: blur()` 做玻璃拟态卡片。唯一的例外是底部 TabBar 的毛玻璃效果（`blur(20px)`）。
3. **无彩色投影/光晕**：阴影仅使用 `rgba(0,0,0,...)` 的无色投影。禁止彩色发光、弥散光晕、`box-shadow` 彩色值。
4. **无装饰性渐变图标**：图标使用纯色描边/填充，禁止多色渐变。
5. **无圆角 > 12px**：卡片 8px、模态框 12px、按钮 6px、头像/胶囊/浮动按钮 9999px。任何容器圆角不超过 12px。
6. **无多余装饰元素**：禁止装饰线、分隔花纹、装饰性 SVG、Orb/光球/Bokeh 效果。
7. **无花哨动画**：页面转场仅右滑/左滑，加载态仅脉冲骨架屏或旋转 Spinner，禁止弹跳/弹簧/旋转进入等花哨动效。
8. **字体栈**：`"Inter", "SF Pro Display", -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif`。禁止使用手写体、装饰体、非系统默认字体。
9. **色彩克制**：整个 App 仅 4 种主色阶（Primary）+ 5 种中性色阶 + 4 种语义色。禁止使用调色板之外的任何颜色。特别是禁止紫色/紫蓝色渐变、米色/奶油色/砂色、深蓝/石板色、棕色/橙色/浓缩咖啡色作为大面积主色调。
10. **间距统一为 4px 栅格**：所有 margin/padding/gap 必须为 4 的倍数。

---

## 2. 技术架构

### 2.1 架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                     同一前端工程：frontend/                         │
├──────────────────────────────┬───────────────────────────────────┤
│   桌面端 SPA                  │   移动端 PWA                        │
│   React 18 + Ant Design 5   │   React 18 + 自研 Design System     │
│   Vite + React Router       │   Vite + React Router + Framer M    │
│   侧边栏 + 内容区            │   页面栈 + 底部 TabBar + 手势导航     │
├──────────────────────────────┴───────────────────────────────────┤
│                   共享层：services/ types/ hooks/ utils/            │
├───────────────────────────────────────────────────────────────────┤
│              共用后端 API：/api/v1/* (FastAPI + PostgreSQL)         │
└───────────────────────────────────────────────────────────────────┘
```

### 2.2 技术栈

| 层级 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 框架 | React | 18.x | UI 框架 |
| 语言 | TypeScript | 5.x | 类型安全 |
| 路由 | React Router | 6.x | 移动端路由表 |
| 动画 | Framer Motion | 11.x | 页面转场、Bottom Sheet、弹性滚动 |
| 样式 | Tailwind CSS | 4.x | 原子化 CSS |
| 样式隔离 | CSS Modules | — | 组件级样式（Tailwind 不覆盖的场景） |
| 状态管理 | Zustand | 5.x | 全局状态（企业切换、离线草稿） |
| 服务端状态 | React Query (@tanstack) | 5.x | API 缓存、请求去重 |
| 富文本 | TipTap (ProseMirror) | 2.x | 移动端编辑器（与桌面端共享内核） |
| 离线存储 | idb-keyval | 8.x | IndexedDB 封装 |
| PWA | vite-plugin-pwa + Workbox | 0.20+ | Service Worker、离线缓存、安装提示 |
| 图标 | Lucide React | 0.400+ | 统一图标库 |
| HTTP | Axios | 1.x | API 请求（与桌面端共享实例） |

### 2.3 项目目录结构

```
frontend/
├── src/
│   ├── main.tsx                        # 入口：检测设备 → 加载 MobileApp 或 DesktopApp
│   ├── App.tsx                          # 桌面端根组件（保持不变）
│   ├── mobile/                          # === 移动端专用 ===
│   │   ├── MobileApp.tsx               # 移动端根组件（Provider 包裹）
│   │   ├── routes.tsx                  # 移动端路由表
│   │   │
│   │   ├── components/                 # 移动端组件库
│   │   │   ├── ui/                     # 基础 UI 组件（见 PRD-M01）
│   │   │   │   ├── Button.tsx
│   │   │   │   ├── Input.tsx
│   │   │   │   ├── NavBar.tsx
│   │   │   │   ├── TabBar.tsx
│   │   │   │   ├── Card.tsx
│   │   │   │   ├── BottomSheet.tsx
│   │   │   │   ├── Skeleton.tsx
│   │   │   │   ├── Toast.tsx
│   │   │   │   ├── EmptyState.tsx
│   │   │   │   ├── Badge.tsx
│   │   │   │   ├── Chip.tsx
│   │   │   │   ├── SegmentedControl.tsx
│   │   │   │   ├── FAB.tsx
│   │   │   │   ├── Spinner.tsx
│   │   │   │   ├── ProgressBar.tsx
│   │   │   │   ├── Avatar.tsx
│   │   │   │   ├── Switch.tsx
│   │   │   │   ├── SelectSheet.tsx
│   │   │   │   └── SafeArea.tsx
│   │   │   ├── enterprise/             # 企业相关组件
│   │   │   │   ├── EnterpriseCard.tsx
│   │   │   │   ├── EnterpriseForm.tsx
│   │   │   │   ├── RiskSourceItem.tsx
│   │   │   │   └── ResourceItem.tsx
│   │   │   ├── plan/                   # 预案相关组件
│   │   │   │   ├── PlanCard.tsx
│   │   │   │   ├── ChapterTree.tsx
│   │   │   │   ├── MobileEditor.tsx    # TipTap 移动端封装
│   │   │   │   ├── EditorToolbar.tsx
│   │   │   │   ├── AIGenerationSheet.tsx
│   │   │   │   └── ExportProgress.tsx
│   │   │   └── auth/                   # 认证组件
│   │   │       ├── LoginForm.tsx
│   │   │       ├── RegisterForm.tsx
│   │   │       └── BiometricButton.tsx
│   │   │
│   │   ├── screens/                    # 页面级组件
│   │   │   ├── SplashScreen.tsx
│   │   │   ├── LoginScreen.tsx
│   │   │   ├── RegisterScreen.tsx
│   │   │   ├── DashboardScreen.tsx
│   │   │   ├── EnterpriseListScreen.tsx
│   │   │   ├── EnterpriseCreateScreen.tsx
│   │   │   ├── EnterpriseDetailScreen.tsx
│   │   │   ├── EnterpriseEditScreen.tsx
│   │   │   ├── RiskSourceListScreen.tsx
│   │   │   ├── ResourceListScreen.tsx
│   │   │   ├── PlanCardsScreen.tsx
│   │   │   ├── EnterprisePlanListScreen.tsx
│   │   │   ├── PlanCreateScreen.tsx
│   │   │   ├── PlanEditorScreen.tsx
│   │   │   ├── ExportPreviewScreen.tsx
│   │   │   ├── VersionListScreen.tsx
│   │   │   ├── ProfileScreen.tsx
│   │   │   ├── ChangePasswordScreen.tsx
│   │   │   ├── AIModelConfigScreen.tsx
│   │   │   ├── RiskAssessmentScreen.tsx
│   │   │   └── ResourceInvestigationScreen.tsx
│   │   │
│   │   ├── hooks/                      # 移动端专用 Hooks
│   │   │   ├── useKeyboard.ts          # 键盘可见性 + 高度
│   │   │   ├── useNetworkStatus.ts     # online/offline 检测
│   │   │   ├── useOfflineSync.ts       # IndexedDB 离线同步
│   │   │   ├── useBiometricAuth.ts     # WebAuthn 生物识别
│   │   │   ├── useScrollToTop.ts       # TabBar 双击回顶
│   │   │   └── useSafeArea.ts          # 安全区尺寸
│   │   │
│   │   ├── store/                      # Zustand 状态管理
│   │   │   ├── appStore.ts             # 全局状态
│   │   │   └── draftStore.ts           # 离线草稿队列
│   │   │
│   │   ├── styles/
│   │   │   ├── tokens.css              # CSS 自定义属性（Design Token）
│   │   │   ├── base.css                # 基础重置样式
│   │   │   └── animations.css          # Framer Motion 预设变体
│   │   │
│   │   └── utils/
│   │       ├── platform.ts             # 平台检测（isMobile, isIOS, isAndroid）
│   │       └── haptics.ts              # 触觉反馈封装
│   │
│   ├── pages/                          # 桌面端页面（保持不变）
│   ├── components/                     # 桌面端组件（保持不变）
│   ├── services/                       # === 共享 API 服务层 ===
│   │   ├── api.ts                      # Axios 实例 + 拦截器
│   │   ├── authService.ts
│   │   ├── enterpriseService.ts
│   │   ├── planService.ts
│   │   ├── generationService.ts
│   │   ├── exportService.ts
│   │   └── riskAssessmentService.ts
│   ├── hooks/                          # 共享 Hooks
│   ├── types/                          # === 共享 TypeScript 类型 ===
│   │   ├── auth.ts
│   │   ├── enterprise.ts
│   │   ├── plan.ts
│   │   ├── generation.ts
│   │   └── api.ts
│   └── utils/                          # 共享工具函数
│
├── public/
│   └── icons/                          # PWA 图标
│       ├── icon-192.png
│       └── icon-512.png
├── package.json
├── vite.config.ts
├── tailwind.config.ts
└── tsconfig.json
```

---

## 3. 移动端路由表

### 3.1 路由前缀

所有移动端路由统一使用 `/m` 前缀，便于与桌面端路由区分：

```
/m/login           → LoginScreen
/m/register        → RegisterScreen
/m/dashboard       → DashboardScreen
/m/enterprises     → EnterpriseListScreen
...
```

### 3.2 完整路由定义

```typescript
// mobile/routes.tsx
import { createBrowserRouter } from "react-router-dom";

export const mobileRouter = createBrowserRouter([
  // === 认证（未登录） ===
  {
    path: "/m/login",
    element: <LoginScreen />,
  },
  {
    path: "/m/register",
    element: <RegisterScreen />,
  },

  // === 主应用（需登录，TabBar 包裹） ===
  {
    path: "/m",
    element: <AuthGuard><MainTabsLayout /></AuthGuard>,
    children: [
      // Tab: 工作台
      {
        index: true,
        element: <DashboardScreen />,
      },
      {
        path: "dashboard",
        element: <DashboardScreen />,
      },

      // Tab: 企业
      {
        path: "enterprises",
        element: <EnterpriseListScreen />,
      },
      {
        path: "enterprises/new",
        element: <EnterpriseCreateScreen />,
      },
      {
        path: "enterprises/:id",
        element: <EnterpriseDetailScreen />,
      },
      {
        path: "enterprises/:id/edit",
        element: <EnterpriseEditScreen />,
      },
      {
        path: "enterprises/:id/risk-sources",
        element: <RiskSourceListScreen />,
      },
      {
        path: "enterprises/:id/resources",
        element: <ResourceListScreen />,
      },
      {
        path: "enterprises/:id/risk-assessment",
        element: <RiskAssessmentScreen />,
      },
      {
        path: "enterprises/:id/resource-investigation",
        element: <ResourceInvestigationScreen />,
      },
      {
        path: "enterprises/:id/plans",
        element: <EnterprisePlanListScreen />,
      },

      // Tab: 预案
      {
        path: "plans",
        element: <PlanCardsScreen />,
      },
      {
        path: "plans/new",
        element: <PlanCreateScreen />,
      },
      {
        path: "plans/:id/edit",
        element: <PlanEditorScreen />,
      },
      {
        path: "plans/:id/versions",
        element: <VersionListScreen />,
      },
      {
        path: "plans/:id/preview",
        element: <ExportPreviewScreen />,
      },

      // Tab: 设置
      {
        path: "settings",
        element: <SettingsScreen />,
      },
      {
        path: "settings/profile",
        element: <ProfileScreen />,
      },
      {
        path: "settings/password",
        element: <ChangePasswordScreen />,
      },
      {
        path: "settings/ai-config",
        element: <AIModelConfigScreen />,
      },
    ],
  },

  // 启动屏
  {
    path: "/m/splash",
    element: <SplashScreen />,
  },

  // 404
  {
    path: "*",
    element: <Navigate to="/m/dashboard" replace />,
  },
]);
```

### 3.3 TabBar 对应的路由范围

```typescript
const TAB_ROUTES = {
  dashboard: ["/m/dashboard", "/m"],
  enterprises: [
    "/m/enterprises",
    "/m/enterprises/:id",
    "/m/enterprises/:id/edit",
    "/m/enterprises/:id/risk-sources",
    "/m/enterprises/:id/resources",
    "/m/enterprises/:id/risk-assessment",
    "/m/enterprises/:id/resource-investigation",
    "/m/enterprises/:id/plans",
  ],
  plans: [
    "/m/plans",
    "/m/plans/:id/edit",
    "/m/plans/:id/versions",
    "/m/plans/:id/preview",
  ],
  settings: [
    "/m/settings",
    "/m/settings/profile",
    "/m/settings/password",
    "/m/settings/ai-config",
  ],
};
```

---

## 4. 状态管理

### 4.1 Zustand Store 设计

```typescript
// mobile/store/appStore.ts
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AppState {
  // 当前选中的企业
  currentEnterpriseId: string | null;
  currentEnterpriseName: string | null;
  setCurrentEnterprise: (id: string, name: string) => void;
  clearCurrentEnterprise: () => void;

  // 当前活跃的 TabBar 索引
  activeTab: "dashboard" | "enterprises" | "plans" | "settings";
  setActiveTab: (tab: AppState["activeTab"]) => void;

  // 网络状态
  isOnline: boolean;
  setOnline: (online: boolean) => void;

  // 键盘可见性
  isKeyboardVisible: boolean;
  keyboardHeight: number;
  setKeyboard: (visible: boolean, height: number) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      currentEnterpriseId: null,
      currentEnterpriseName: null,
      setCurrentEnterprise: (id, name) =>
        set({ currentEnterpriseId: id, currentEnterpriseName: name }),
      clearCurrentEnterprise: () =>
        set({ currentEnterpriseId: null, currentEnterpriseName: null }),

      activeTab: "dashboard",
      setActiveTab: (tab) => set({ activeTab: tab }),

      isOnline: navigator.onLine,
      setOnline: (online) => set({ isOnline: online }),

      isKeyboardVisible: false,
      keyboardHeight: 0,
      setKeyboard: (visible, height) =>
        set({ isKeyboardVisible: visible, keyboardHeight: height }),
    }),
    {
      name: "mobile-app-store",
      partialize: (state) => ({
        currentEnterpriseId: state.currentEnterpriseId,
        currentEnterpriseName: state.currentEnterpriseName,
      }),
    }
  )
);
```

```typescript
// mobile/store/draftStore.ts
import { create } from "zustand";

interface DraftItem {
  sectionKey: string;
  planId: string;
  content: string;       // Markdown
  updatedAt: number;     // Unix timestamp
  synced: boolean;       // 是否已同步到服务端
}

interface DraftState {
  drafts: DraftItem[];
  addDraft: (draft: Omit<DraftItem, "synced">) => void;
  removeDraft: (planId: string, sectionKey: string) => void;
  getPendingSyncDrafts: () => DraftItem[];
  markSynced: (planId: string, sectionKey: string) => void;
}

export const useDraftStore = create<DraftState>((set, get) => ({
  drafts: [],
  addDraft: (draft) =>
    set((state) => {
      const filtered = state.drafts.filter(
        (d) => !(d.planId === draft.planId && d.sectionKey === draft.sectionKey)
      );
      return { drafts: [...filtered, { ...draft, synced: false }] };
    }),
  removeDraft: (planId, sectionKey) =>
    set((state) => ({
      drafts: state.drafts.filter(
        (d) => !(d.planId === planId && d.sectionKey === sectionKey)
      ),
    })),
  getPendingSyncDrafts: () => get().drafts.filter((d) => !d.synced),
  markSynced: (planId, sectionKey) =>
    set((state) => ({
      drafts: state.drafts.map((d) =>
        d.planId === planId && d.sectionKey === sectionKey
          ? { ...d, synced: true }
          : d
      ),
    })),
}));
```

### 4.3 React Query 配置

移动端共享桌面端的 QueryClient 配置，额外添加离线行为：

```typescript
// mobile/MobileApp.tsx
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      // 离线时不报错，使用缓存数据
      networkMode: "offlineFirst",
    },
    mutations: {
      // 离线时排队，联网后重试
      networkMode: "offlineFirst",
    },
  },
});
```

---

## 5. 工程配置

### 5.1 Vite 配置

```typescript
// vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import path from "path";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icons/icon-192.png", "icons/icon-512.png"],
      manifest: {
        name: "数字化应急预案生成",
        short_name: "应急预案",
        description: "基于 GB/T 29639-2020 的数字化应急预案自动生成系统",
        theme_color: "#1A56DB",
        background_color: "#FFFFFF",
        display: "standalone",
        start_url: "/m/dashboard",
        icons: [
          { src: "icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icons/icon-512.png", sizes: "512x512", type: "image/png" },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,svg,png,woff2}"],
        runtimeCaching: [
          {
            urlPattern: /^\/api\/v1\//,
            handler: "NetworkFirst",
            options: {
              cacheName: "api-cache",
              expiration: { maxEntries: 100, maxAgeSeconds: 60 * 60 },
            },
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          "mobile-vendor": ["react", "react-dom", "react-router-dom"],
          "mobile-ui": ["framer-motion"],
          desktop: ["antd", "@ant-design/icons"],
        },
      },
    },
  },
});
```

### 5.2 Tailwind 配置

```typescript
// tailwind.config.ts
import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#EFF6FF",
          500: "#3B82F6",
          600: "#1A56DB",
        },
        neutral: {
          50: "#F9FAFB",
          100: "#F3F4F6",
          400: "#9CA3AF",
          600: "#4B5563",
          900: "#111827",
        },
        danger: "#DC2626",
        warning: "#F59E0B",
        success: "#10B981",
        info: "#6366F1",
      },
      borderRadius: {
        sm: "6px",
        md: "8px",
        lg: "12px",
        full: "9999px",
      },
      spacing: {
        xs: "4px",
        sm: "8px",
        md: "16px",
        lg: "24px",
        xl: "32px",
        "safe-top": "env(safe-area-inset-top, 0px)",
        "safe-bottom": "env(safe-area-inset-bottom, 0px)",
      },
      fontSize: {
        display: ["34px", { lineHeight: "41px", fontWeight: "700" }],
        h1: ["28px", { lineHeight: "34px", fontWeight: "600" }],
        h2: ["22px", { lineHeight: "28px", fontWeight: "600" }],
        h3: ["17px", { lineHeight: "22px", fontWeight: "600" }],
        body: ["16px", { lineHeight: "24px", fontWeight: "400" }],
        "body-sm": ["14px", { lineHeight: "20px", fontWeight: "400" }],
        caption: ["12px", { lineHeight: "16px", fontWeight: "500" }],
      },
      fontFamily: {
        sans: [
          '"Inter"',
          '"SF Pro Display"',
          "-apple-system",
          "BlinkMacSystemFont",
          '"PingFang SC"',
          '"Microsoft YaHei"',
          "sans-serif",
        ],
      },
      boxShadow: {
        card: "0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)",
        modal: "0 20px 25px rgba(0,0,0,0.1), 0 10px 10px rgba(0,0,0,0.04)",
        fab: "0 4px 12px rgba(26,86,219,0.35)",
      },
      animation: {
        "skeleton-pulse": "skeleton-pulse 1.5s ease-in-out infinite",
        "spin-slow": "spin 2s linear infinite",
      },
      keyframes: {
        "skeleton-pulse": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
```

### 5.3 入口分发逻辑

```typescript
// src/main.tsx
import { isMobile } from "@/mobile/utils/platform";
import MobileApp from "@/mobile/MobileApp";
import DesktopApp from "@/App";
import ReactDOM from "react-dom/client";

const App = isMobile() ? MobileApp : DesktopApp;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

```typescript
// mobile/utils/platform.ts
export function isMobile(): boolean {
  // 1. UA 检测
  if (/Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) {
    return true;
  }
  // 2. 屏幕宽度检测（平板竖屏 ≤ 768px）
  if (window.innerWidth <= 768) {
    return true;
  }
  return false;
}

export function isIOS(): boolean {
  return /iPhone|iPad|iPod/i.test(navigator.userAgent);
}

export function isAndroid(): boolean {
  return /Android/i.test(navigator.userAgent);
}
```

---

## 6. 全局组件

### 6.1 MobileApp.tsx（根组件）

```typescript
// mobile/MobileApp.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { EnterpriseProvider } from "@/contexts/EnterpriseContext";
import { mobileRouter } from "@/mobile/routes";
import { ToastProvider } from "@/mobile/components/ui/Toast";
import "@/mobile/styles/tokens.css";
import "@/mobile/styles/base.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      networkMode: "offlineFirst",
    },
    mutations: {
      networkMode: "offlineFirst",
    },
  },
});

export default function MobileApp() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <EnterpriseProvider>
            <RouterProvider router={mobileRouter} />
          </EnterpriseProvider>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}
```

### 6.2 MainTabsLayout（TabBar 包裹布局）

```typescript
// mobile/components/ui/TabBar.tsx 所在布局文件

interface MainTabsLayoutProps {
  // 通过 React Router Outlet 渲染子路由
}

// 文件：mobile/layouts/MainTabsLayout.tsx
export default function MainTabsLayout() {
  const location = useLocation();
  const { activeTab, setActiveTab } = useAppStore();

  // 根据 location 自动更新 activeTab
  useEffect(() => {
    for (const [tab, patterns] of Object.entries(TAB_ROUTES)) {
      if (matchPath(patterns, location.pathname)) {
        setActiveTab(tab as typeof activeTab);
        break;
      }
    }
  }, [location.pathname]);

  return (
    <div className="flex flex-col h-dvh bg-neutral-50">
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
      <TabBar />
    </div>
  );
}
```

---

## 7. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| M00-01 | 移动端 UA 检测正确分发 MobileApp | 真机访问 → 加载移动端路由 |
| M00-02 | 桌面端浏览器不加载移动端 Bundle | Lighthouse → mobile chunk 不在首屏 JS |
| M00-03 | 所有移动端路由可访问（22 条路由） | Playwright mobile viewport 自动化 |
| M00-04 | TabBar 自动高亮当前路由所在 Tab | 手动验证 4 个 Tab 切换 |
| M00-05 | 共享 services/ 层 API 调用正常 | 登录后获取企业列表 |
| M00-06 | 共享 types/ 类型定义无冲突 | `tsc --noEmit` 通过 |
| M00-07 | PWA manifest 可识别 | Chrome DevTools → Application → Manifest |
| M00-08 | Service Worker 注册成功 | Chrome DevTools → Application → Service Workers |
| M00-09 | 设计风格无违规：无渐变背景、无玻璃拟态、无彩色投影、无 > 12px 圆角 | 代码审查（grep 检查 CSS） |
| M00-10 | Framer Motion 页面转场动画 60fps | Chrome DevTools Performance 录制 |

---

> **下一文档**：PRD-M01 移动端视觉设计系统与组件库
