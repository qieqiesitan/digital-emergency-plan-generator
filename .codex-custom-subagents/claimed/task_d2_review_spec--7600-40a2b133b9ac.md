# Codex Custom Subagents task handoff v1

Task: task_d2_review_spec

## 任务：规格合规审查——task_d2_chat_screen

你是代码审查子智能体。请核验 D-2 移动端 AI 助手聊天页实现是否符合规格。只读 + 验证，不要修改任何文件。

### 审查对象

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。

审查命令：cd 到 worktree 后 `git diff 65126c6..HEAD` 或 `git show <提交>`，逐文件阅读实际代码。

### 规格要求（对照 docs/superpowers/plans/2026-08-09-usability-mobile.md 任务 D-2）

1. **ChatScreen.tsx（新建）**：复用 `@/services/chatService`（sendChatMessage/fetchConversations/createConversation/fetchMessages）；进入加载最近对话历史/无则创建；发送后 user 消息 + assistant 流式占位，SSE chunk/progress 追加内容；loading 与错误处理（toast）；历史传最近 10 条；返回按钮回 `/m/settings`；消息列表自动滚底。
2. **routes.tsx**：`lazy` 导入 ChatScreen；设置分组下 `{ path: "chat", element: <ChatScreen /> }`；ai-config 路由保留（D-3 再删）。
3. **SettingsScreen.tsx**：MENU_ITEMS 中 ai-config 项替换为「AI 助手」→ /m/chat；Bot 图标保留使用；无未使用导入残留。
4. 气泡/输入/按钮符合移动端规范：无 `#1677ff` 等硬编码色、无裸原生 input/button、无 `any`。

### 门禁

- `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
- `npx eslint` 改动文件不得新增 error（与 BASE 逐项对比）
- `git diff --check` 干净；diff 无 any；单提交、仅 3 个相关文件

### 汇报格式

```
结论：PASS / FAIL（✅ 符合规格 / ❌ 需修复）
逐项核验：...
参考建议（非阻塞）：...
```

