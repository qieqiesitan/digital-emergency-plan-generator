# Codex Custom Subagents task handoff v1

Task: task_a5_review_spec

## 任务：规格合规审查——task_a5_menu_permissions 实现是否匹配任务要求

你是一个规格合规审查子智能体。目的：验证实现者是否构建了所要求的内容（不多不少）。关键：不要信任实现者的报告，必须独立阅读实际代码验证。

### 实现位置

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。审查提交 `50a3abc`：

git show 50a3abc --stat 与 git show 50a3abc

### 要求的内容（任务 A5 原文）

1. AuthContext.tsx：
   - AuthContextValue/AuthState 增加 menuLoadFailed: boolean，初始 false，所有初始化/重置位置覆盖（login/register 成功、logout、auth:logout handler）
   - loadMenuPermissions catch 降级为核心菜单（menu:dashboard/menu:enterprises/menu:plans/menu:profile）+ menuLoadFailed: true
2. MainLayout.tsx：
   - 从 useAuth 解构 menuLoadFailed
   - Content 顶部（Outlet 前）渲染可关闭 Alert「部分菜单加载失败，已显示核心菜单」
   - 移除 AI 助手菜单项与 /chat onClick 特殊分支（统一 navigate(key)），RobotOutlined 不再使用时删除导入
   - 法规库管理纳入 hasMenu("/settings/regulations") 过滤
   - FloatingChat 保留不动
3. tsc -p tsconfig.app.json --noEmit 无类型错误。
4. Commit：fix(menu): filter regulations menu, remove AI assistant entry, degrade menus on permission load failure。
5. 只改 2 个文件。

### 实现者声称构建了什么

- AuthContext menuLoadFailed 全覆盖（含 loadMenuPermissions 成功分支重置，属合理补充）
- MainLayout Alert、AI 助手移除（含 MENU_MAP /chat 死条目、useChatDrawer 清理）、法规库过滤
- tsc 通过；提交 50a3abc（2 文件）

### 你的工作

阅读实际代码并验证：menuLoadFailed 各状态是否覆盖？AI 助手菜单是否彻底移除且无残留（含 ChatDrawer 使用是否合理保留）？法规库是否过滤？Alert 位置是否正确？只改 2 个文件？

通过阅读代码来验证，而非信任报告。

### 汇报格式

- ✅ 符合规格（如果经过代码检查后一切匹配）
- ❌ 发现问题：[具体列出缺失或多余的内容，附带 file:line 引用]
