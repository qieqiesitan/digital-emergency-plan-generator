# PRD-M08：移动端 PWA 与离线能力

> **版本**：1.0 | **创建日期**：2026-06-09 | **依赖**：PRD-M00 | **关联文档**：移动端设计方案 §10, §11

---

## 1. 模块概述

提供移动端 PWA（渐进式 Web 应用）完整能力：安装到主屏幕、离线启动、离线编辑、智能缓存、后台同步、推送通知。

**与本模块相关的文件**：

| 文件 | 职责 |
|------|------|
| `vite.config.ts` | PWA 插件配置（manifest + Workbox） |
| `public/icons/icon-192.png` | PWA 图标 192×192 |
| `public/icons/icon-512.png` | PWA 图标 512×512 |
| `public/sw.js` | Service Worker（由 Workbox 自动生成） |
| `mobile/hooks/useNetworkStatus.ts` | 网络状态监听 |
| `mobile/hooks/useOfflineSync.ts` | 离线草稿同步 |
| `mobile/store/draftStore.ts` | 离线草稿队列 |

---

## 2. PWA manifest

已在 PRD-M00 §5.1 定义，此处补充完整配置：

```json
{
  "name": "数字化应急预案生成系统",
  "short_name": "应急预案",
  "description": "基于 GB/T 29639-2020 的数字化应急预案自动生成系统",
  "start_url": "/m/dashboard",
  "display": "standalone",
  "background_color": "#FFFFFF",
  "theme_color": "#1A56DB",
  "orientation": "portrait-primary",
  "icons": [
    {
      "src": "/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any maskable"
    },
    {
      "src": "/icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ],
  "screenshots": [
    {
      "src": "/screenshots/mobile-dashboard.png",
      "sizes": "390x844",
      "type": "image/png",
      "form_factor": "narrow",
      "label": "工作台"
    }
  ],
  "categories": ["productivity", "business"],
  "lang": "zh-CN"
}
```

**图标要求**：
- 192×192 和 512×512 PNG 格式
- 品牌主色 `#1A56DB` 底色 + 白色系统 Logo（简化版，仅核心图形无文字）
- `purpose: "maskable"` 确保图标在 Android 自适应形状中正常显示

---

## 3. Service Worker 缓存策略（Workbox）

### 3.1 缓存分层

| 资源类型 | 策略 | 缓存名 | 最大条目 | 过期时间 |
|----------|------|--------|----------|----------|
| HTML（App Shell） | NetworkFirst | `app-shell` | 10 | 7 天 |
| JS / CSS（静态资源） | CacheFirst | `static-resources` | 100 | 30 天 |
| 字体（woff2） | CacheFirst | `fonts` | 20 | 永久 |
| API `/api/v1/*` | NetworkFirst | `api-cache` | 100 | 1 小时 |
| 图片 / 图标 | CacheFirst | `images` | 50 | 30 天 |

### 3.2 Workbox 实现（vite-plugin-pwa 配置）

已在 PRD-M00 §5.1 给出 `vite.config.ts` 中 `VitePWA` 的配置。下面补充完整的运行时缓存配置：

```typescript
workbox: {
  globPatterns: ["**/*.{js,css,html,svg,png,woff2,ico}"],
  // 预缓存关键静态资源（构建时自动注入）
  // 运行时缓存策略
  runtimeCaching: [
    {
      // API 请求：NetworkFirst（网络优先，失败时使用缓存）
      urlPattern: /^\/api\/v1\//,
      handler: "NetworkFirst",
      options: {
        cacheName: "api-cache",
        networkTimeoutSeconds: 5,
        expiration: {
          maxEntries: 100,
          maxAgeSeconds: 60 * 60,           // 1 小时
        },
        cacheableResponse: {
          statuses: [0, 200],
        },
      },
    },
    {
      // 字体文件：CacheFirst
      urlPattern: /\.(?:woff2?)$/,
      handler: "CacheFirst",
      options: {
        cacheName: "fonts",
        expiration: { maxEntries: 20, maxAgeSeconds: 365 * 24 * 60 * 60 },
      },
    },
    {
      // 图片：CacheFirst
      urlPattern: /\.(?:png|jpg|jpeg|svg|gif|webp)$/,
      handler: "CacheFirst",
      options: {
        cacheName: "images",
        expiration: { maxEntries: 50, maxAgeSeconds: 30 * 24 * 60 * 60 },
      },
    },
  ],
},
```

### 3.3 更新提示

Service Worker 检测到新版本时的更新策略：

```typescript
// 在 MobileApp.tsx 中注册
import { useRegisterSW } from "virtual:pwa-register/react";

function UpdatePrompt() {
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW();

  if (!needRefresh) return null;

  return (
    <div className="fixed bottom-20 left-md right-md z-50
                    bg-primary-600 text-white rounded-md shadow-modal p-md
                    flex items-center justify-between">
      <span className="text-body-sm">新版本可用</span>
      <Button variant="secondary" size="sm" onClick={() => updateServiceWorker(true)}>
        更新
      </Button>
    </div>
  );
}
```

- 新版本检测到后：底部浮层显示「新版本可用」+「更新」按钮
- 点击「更新」→ Service Worker 激活新版本 → 页面自动刷新
- 不强制更新（用户可忽略，下次启动自动生效）

---

## 4. 离线能力实现

### 4.1 网络状态监听 — useNetworkStatus

```typescript
// 文件：mobile/hooks/useNetworkStatus.ts

function useNetworkStatus(): {
  isOnline: boolean;
  wasOffline: boolean;            // 刚刚从离线恢复
}

// 实现：
// - 监听 window "online" / "offline" 事件
// - 监听 navigator.onLine
// - wasOffline: 从 offline 变为 online 时，持续 true 5 秒后重置
```

**UI 响应**：
- 从在线 → 离线：顶部 Toast「网络连接已断开」（Warning）
- 从离线 → 在线：顶部 Toast「网络已恢复」+ 触发后台同步

### 4.2 离线草稿存储 — draftStore

已在 PRD-M00 §4.2 定义。核心要点：

- **存储位置**：IndexedDB（通过 `idb-keyval`）
- **数据结构**：`{ planId, sectionKey, content (Markdown), updatedAt (timestamp), synced: boolean }`
- **写入时机**：编辑器自动保存失败（API 返回非 2xx 或网络错误）时
- **读取时机**：编辑器进入编辑模式时，检查是否有未同步的草稿（`updatedAt` > 服务端 `updatedAt`），有则提示用户恢复

### 4.3 离线同步 — useOfflineSync

```typescript
// 文件：mobile/hooks/useOfflineSync.ts

function useOfflineSync(): {
  isSyncing: boolean;
  lastSyncAt: number | null;
  syncNow: () => Promise<void>;
}

// 实现流程：
// 1. 从 draftStore 获取 pendingSyncDrafts
// 2. 对每个草稿：
//    a. GET /api/v1/plans/{id}/sections/{key} → 获取服务端 updated_at
//    b. 比较时间戳：
//       - 服务端无更新（或不存在）→ PUT 本地内容
//       - 服务端有更新 → 跳过此项 + 记录冲突
//    c. PUT 成功 → draftStore.markSynced
// 3. 所有冲突项 → Toast「X 个章节在服务端已更新，请在编辑器中手动处理」
```

**触发时机**：
- `useNetworkStatus.wasOffline` 变为 true（刚从离线恢复）
- Service Worker `sync` 事件（Background Sync API）
- 用户手动下拉刷新（在列表页）

### 4.4 离线功能矩阵

| 功能 | 离线可用 | 行为 |
|------|----------|------|
| 查看 Dashboard | 部分 | 统计数字可能过期，显示缓存时间戳 |
| 查看企业列表 | ✓ | 使用 IndexedDB 缓存 |
| 查看预案章节 | ✓ | 使用上次加载的缓存 |
| 编辑章节 | ✓ | 存 draftStore，联网后同步 |
| 新建预案 | ✓ | 本地创建（存 draftStore），联网后 POST |
| AI 生成 | ✗ | 提示「AI 生成需要网络连接」 |
| 导出 .docx | ✗ | 提示「导出功能需要网络连接」 |
| 登录 | ✗ | 提示「登录需要网络连接」 |

### 4.5 离线状态 UI 指示

- 无网络时：
  - TabBar 上方显示 4px 高度的橙色条纹（`bg-warning`）
  - 所有触发网络请求的操作：Toast「当前处于离线模式，操作将在联网后同步」
- 离线期间创建/编辑的内容：列表项右下角显示橙色小圆点，表示「待同步」

---

## 5. 推送通知（P1）

**使用场景**：
- AI 批量生成完成 →「[预案名] 的 X 个章节已生成完毕」
- 导出完成 →「[预案名] 的 .docx 文档已生成，点击下载」

**实现**：
- 基于 Web Push API
- 需要后端支持 VAPID 密钥生成和推送消息下发（超出本次 PRD 范围，标记为 P1）

**权限请求**：
- 首次进入 AI 生成或导出功能时，请求通知权限
- 用户拒绝后不重复请求（最多请求 3 次，每次间隔 5 天）

---

## 6. 安装到主屏幕（A2HS）提示

**触发时机**（满足所有条件）：
1. 用户访问 3 次以上
2. 用户已登录（有活跃会话）
3. 设备支持 PWA 安装（`beforeinstallprompt` 事件存在）
4. 距离上次提示 ≥ 7 天

**UI**：
- BottomSheet 弹出：
  ```
  添加到主屏幕
  将应急预案生成系统添加到手机桌面，随时随地管理应急预案。
  [以后再说]   [添加到桌面]
  ```
- 点击「添加到桌面」→ 调用 `deferredPrompt.prompt()`
- 用户接受 → Toast「已添加到桌面」
- 用户拒绝 → 下次满足条件再提示

---

## 7. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| M08-01 | PWA 安装提示正常弹出 + 安装成功 | Android Chrome / iOS Safari |
| M08-02 | 离线启动：断网后打开 App → 显示缓存的 Dashboard | 手动（断网） |
| M08-03 | 离线查看预案内容（缓存数据） | 手动 |
| M08-04 | 离线编辑 → 存 IndexedDB → 联网 → 自动同步 | 手动 |
| M08-05 | 离线时 TabBar 上方出现橙色离线指示条 | 手动 |
| M08-06 | 联网恢复 → Toast「网络已恢复」+ 自动同步 | 手动 |
| M08-07 | Service Worker 新版本提示 → 更新按钮 → 页面刷新 | 手动 |
| M08-08 | API 缓存：NetworkFirst 策略生效 | Chrome DevTools → Cache Storage |
| M08-09 | AI 生成 / 导出：离线时禁用并提示 | 手动 |
| M08-10 | manifest.json 所有字段正确 | Lighthouse PWA Audit |
| M08-11 | PWA 图标 192/512 正确加载 | Chrome DevTools → Manifest |

---

> **=== 移动端 PRD 系列完 ===**
>
> 全部 9 篇 PRD 汇总：
> - [PRD-M00](/prd/PRD-M00-移动端系统总览与架构.md) — 项目结构、工程配置、路由、状态管理
> - [PRD-M01](/prd/PRD-M01-移动端视觉设计系统与组件库.md) — 19 个基础 UI 组件 + 设计铁律
> - [PRD-M02](/prd/PRD-M02-移动端认证与用户模块.md) — 登录/注册/启动屏/生物识别/个人资料
> - [PRD-M03](/prd/PRD-M03-移动端工作台.md) — Dashboard 信息流 + FAB Speed Dial
> - [PRD-M04](/prd/PRD-M04-移动端企业管理模块.md) — 企业 CRUD + 风险源 + 应急资源 + 调查报告
> - [PRD-M05](/prd/PRD-M05-移动端预案编辑器.md) — 双态编辑器 + 章节导航 + TipTap + 自动保存
> - [PRD-M06](/prd/PRD-M06-移动端AI生成体验.md) — SSE 流式打字机 + 批量生成 + BottomSheet 确认面板
> - [PRD-M07](/prd/PRD-M07-移动端导出与设置.md) — .docx 导出 + 版本管理 + AI 配置
> - [PRD-M08](/prd/PRD-M08-移动端PWA与离线能力.md) — PWA 安装 + 离线缓存 + 草稿同步 + 推送通知
