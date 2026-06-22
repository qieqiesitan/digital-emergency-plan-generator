# PRD-M07：移动端导出、版本管理与设置

> **版本**：1.0 | **创建日期**：2026-06-09 | **依赖**：PRD-M00, PRD-M01, PRD-06, PRD-07, PRD-09 | **关联文档**：移动端设计方案 §5.12~5.15

---

## 1. 模块概述

本模块覆盖三个相对独立但共享底层服务的功能区域：文档导出、版本管理、系统设置（AI 配置 + 个人资料）。

**与本模块相关的文件**：

| 文件 | 职责 |
|------|------|
| `mobile/screens/ExportPreviewScreen.tsx` | 导出预览 + 下载触发 |
| `mobile/screens/VersionListScreen.tsx` | 版本列表 |
| `mobile/screens/SettingsScreen.tsx` | 设置主页（导航入口） |
| `mobile/screens/AIModelConfigScreen.tsx` | AI 模型配置 |
| `mobile/components/plan/ExportProgress.tsx` | 导出进度条 |
| `services/exportService.ts` | 共享导出 API |
| `services/versionService.ts` | 共享版本 API |

**复用的后端 API**（不做任何修改）：

| 端点 | 用途 |
|------|------|
| `GET /api/v1/plans/{id}/export/preview` | 导出预览 HTML |
| `POST /api/v1/plans/{id}/export/docx` | 生成 .docx（异步，返回 task_id） |
| `GET /api/v1/plans/{id}/export/status/{task_id}` | 查询导出进度 |
| `GET /api/v1/plans/{id}/versions` | 版本列表 |
| `GET /api/v1/plans/{id}/versions/{vid}` | 版本详情（只读预案内容） |
| `POST /api/v1/plans/{id}/versions/rollback` | 回滚到指定版本 |
| `GET/PUT /api/v1/settings/ai-config` | AI 配置读写 |
| `POST /api/v1/settings/ai-config/test` | AI 连接测试 |

---

## 2. ExportPreviewScreen（导出预览 + 下载）

**文件**：`mobile/screens/ExportPreviewScreen.tsx`

**路由**：`/m/plans/:id/preview`

**布局**：

```
┌──────────────────────────────────────┐
│ ← 导出预览                           │
├──────────────────────────────────────┤
│                                      │
│  ┌─ 预览区（WebView / HTML render）──┐│
│  │                                  ││  ← 完整预案 HTML 渲染
│  │  封面页                          ││     支持双指缩放
│  │  目录                            ││     支持目录侧边抽屉（左侧滑出）
│  │  正文...                         ││
│  │                                  ││
│  └──────────────────────────────────┘│
│                                      │
│  ┌──────────────────────────────┐    │
│  │         ⬇ 导出 .docx         │    │  ← Button primary lg fullWidth
│  └──────────────────────────────┘    │     sticky bottom
│                                      │
│  导出进度：[████████░░] 75%          │  ← ExportProgress（条件显示）
│                                      │
└──────────────────────────────────────┘
```

**预览渲染**：
- 使用 `dangerouslySetInnerHTML` 嵌入 `GET /api/v1/plans/{id}/export/preview` 返回的 HTML
- 使用 `<iframe>` 方式更安全（独立上下文，CSS 不污染 App 样式）
- 推荐方案：`<iframe srcDoc={previewHtml} className="w-full h-full" />`
- 双指缩放：`<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0">`

**目录抽屉**：
- 左侧滑出 Menu（Framer Motion `animate={{ x: open ? 0 : "-100%" }}`）
- 背景遮罩 `rgba(0,0,0,0.3)`
- 章节列表，点击 → iframe 内滚动到对应位置（通过 `window.postMessage` 通信）

**导出流程**：
1. 点击「导出 .docx」→ `POST /api/v1/plans/{id}/export/docx` → 获取 `task_id`
2. 开始轮询 `GET /api/v1/plans/{id}/export/status/{task_id}`（每 2s）
3. 显示 ExportProgress 组件（进度条 + 状态文字）：
   - `status: "processing"` →「正在生成文档…」
   - `status: "completed"` → 触发下载 → Toast「文档已导出」
   - `status: "failed"` → Toast error「导出失败，请重试」
4. 下载方式：创建 `<a download>` + `URL.createObjectURL(blob)` 触发下载
   - 或在支持 Web Share API 的设备上调用 `navigator.share()` 触发系统分享面板

**ExportProgress 组件**：

```typescript
interface ExportProgressProps {
  status: "idle" | "processing" | "completed" | "failed";
  progress?: number;    // 0-100
}
```

- `idle`：不显示
- `processing`：ProgressBar indeterminate（蓝色）+「正在生成文档，请稍候…」
- `completed`：绿色 CheckCircle +「文档已生成」→ 自动触发下载
- `failed`：红色 AlertCircle +「导出失败」+「重试」按钮

---

## 3. VersionListScreen（版本列表）

**文件**：`mobile/screens/VersionListScreen.tsx`

**路由**：`/m/plans/:id/versions`

**布局**：

```
┌──────────────────────────────────────┐
│ ← 版本管理                           │
├──────────────────────────────────────┤
│  当前版本：v3.0                      │  ← Badge info
├──────────────────────────────────────┤
│                                      │
│ ┌─ v3.0（当前）─────────────────────┐│  ← 最新版本，高亮 bg-primary-50
│ │ 2026-06-09 14:30  ·  手动创建     ││     左滑 →「预览」+「回滚」
│ │ 更新了应急响应章节                ││
│ └──────────────────────────────────┘│
│                                      │
│ ┌─ v2.0 ───────────────────────────┐│
│ │ 2026-06-08 10:15  ·  自动创建     ││  ← bot 图标（灰色）
│ │ AI 生成前自动保存                 ││
│ └──────────────────────────────────┘│
│                                      │
│ ┌─ v1.0 ───────────────────────────┐│
│ │ 2026-06-05 09:00  ·  手动创建     ││  ← user 图标（蓝色）
│ │ 初始版本                          ││
│ └──────────────────────────────────┘│
│                                      │
└──────────────────────────────────────┘
```

**列表项**：
- Card pressable
- 版本号（`text-h3` Semibold）+ Badge「当前」（仅最新版本）
- 时间 + 创建方式图标（`bot` / `user`）+ 类型文字
- 描述：`text-body-sm` Neutral 600，最多 2 行
- 左滑操作（仅非当前版本）：
  - 「预览」→ 跳转预览页（只读编辑器模式）
  - 「回滚」→ 确认 Dialog → `POST /api/v1/plans/{id}/versions/rollback` → 成功 → Toast「已回滚到 vX.X」

**版本预览**：
- 点击版本 → 进入只读编辑器（`MobileEditor readOnly=true`）
- NavBar 显示版本号 + 左侧返回按钮

**回滚确认 Dialog**：
```
确定回滚到 v2.0？
当前版本 v3.0 将保存为新版本，当前内容将被 v2.0 的内容替换。
[取消] [确认回滚]
```

---

## 4. SettingsScreen（设置主页）

**文件**：`mobile/screens/SettingsScreen.tsx`

**路由**：`/m/settings`

**布局**（分组菜单列表）：

```
┌──────────────────────────────────────┐
│  设置                                │  ← NavBar largeTitle
├──────────────────────────────────────┤
│                                      │
│  ┌─ 账户信息 ───────────────────────┐│
│  │ [Avatar md] 张三                 ││  ← 个人资料入口
│  │             user@example.com     ││     pressable → ProfileScreen
│  │                             →    ││
│  └──────────────────────────────────┘│
│                                      │
│  ┌─ 修改密码 ────────────────── → ─┐│
│  └──────────────────────────────────┘│
│                                      │
│  ┌─ AI 模型配置 ─────────────── → ─┐│
│  │ DeepSeek  ·  deepseek-chat       ││  ← 显示当前配置摘要
│  └──────────────────────────────────┘│
│                                      │
│  ┌─ 关于 ──────────────────────────┐│
│  │ 版本 1.0.0                       ││
│  │ GB/T 29639-2020 标准合规         ││
│  └──────────────────────────────────┘│
│                                      │
│  ┌─ 退出登录 ──────────────────────┐│
│  │          [退出登录]              ││  ← Button danger ghost 居中
│  └──────────────────────────────────┘│
│                                      │
└──────────────────────────────────────┘
```

---

## 5. AIModelConfigScreen（AI 模型配置）

**文件**：`mobile/screens/AIModelConfigScreen.tsx`

**路由**：`/m/settings/ai-config`

**布局**：

```
┌──────────────────────────────────────┐
│ ← AI 模型配置                        │
├──────────────────────────────────────┤
│                                      │
│  选择提供商                           │
│  ┌────────┐┌────────┐┌────┐┌──────┐│
│  │ OpenAI ││ 通义   ││文心││DeepSe││  ← SegmentedControl (4 项)
│  └────────┘└────────┘└────┘└──────┘│
│                                      │
│  API Key                             │
│  ┌──────────────────────────────┐    │  ← Input type="password"
│  │ sk-••••••••••        [👁]    │    │     showPasswordToggle
│  └──────────────────────────────┘    │
│                                      │
│  模型                                │
│  ┌──────────────────────────────┐    │  ← SelectSheet
│  │ deepseek-chat           ▼    │    │     根据 provider 动态选项
│  └──────────────────────────────┘    │
│                                      │
│  高级参数                    [展开]  │  ← 折叠面板
│  ┌──────────────────────────────┐    │
│  │ Temperature          0.7     │    │  ← 滑块 (0-2, step 0.1)
│  │ [==========○===========]     │    │
│  │                              │    │
│  │ Max Tokens           4096    │    │  ← Input type="number"
│  │ [                   ]       │    │
│  │                              │    │
│  │ Top P                1.0     │    │  ← 滑块 (0-1, step 0.05)
│  │ [====================○]     │    │
│  └──────────────────────────────┘    │
│                                      │
│  ┌──────────────────────────────┐    │
│  │          测试连接             │    │  ← Button secondary lg fullWidth
│  └──────────────────────────────┘    │
│                                      │
│  测试结果：[✓ 连接成功 — deepseek]   │  ← 绿色 Badge / 红色 Badge
│                                      │
│  ┌──────────────────────────────┐    │
│  │          保存配置             │    │  ← Button primary lg fullWidth
│  └──────────────────────────────┘    │     sticky bottom
└──────────────────────────────────────┘
```

**测试连接逻辑**：
1. `POST /api/v1/settings/ai-config/test`
2. 按钮变化为 `<Spinner sm />` +「测试中…」
3. 成功：绿色 Badge「✓ 连接成功 — 模型：deepseek-chat」
4. 失败：红色 Badge「✗ 连接失败 — {错误信息}」

**保存逻辑**：
- `PUT /api/v1/settings/ai-config` → 成功 → Toast「AI 配置已保存」→ navigate(-1)

---

## 6. 验收标准

| 编号 | 验收项 | 验证方法 |
|------|--------|----------|
| M07-01 | 导出预览 HTML 渲染正确（封面+目录+正文） | 自动化 |
| M07-02 | 导出 .docx → 轮询进度 → 下载触发 | 自动化 |
| M07-03 | 版本列表正确渲染（时间、类型、说明） | 自动化 |
| M07-04 | 版本回滚 → 确认 → 成功 | 自动化 |
| M07-05 | 设置主页导航入口全部可用 | 自动化 |
| M07-06 | AI 配置：4 个提供商切换 + 测试连接 | 自动化 |
| M07-07 | AI 配置保存 → Toast 提示 | 自动化 |
| M07-08 | 视觉铁律通过 | 代码审查 |

---

> **下一文档**：PRD-M08 PWA 与离线能力
