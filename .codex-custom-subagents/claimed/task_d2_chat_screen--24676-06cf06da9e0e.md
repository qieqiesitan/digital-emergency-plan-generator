# Codex Custom Subagents task handoff v1

Task: task_d2_chat_screen

## 任务：D-2 移动端 AI 助手聊天页

你是实现子智能体。请实现移动端 AI 助手聊天页并提交。规格出处：`docs/superpowers/plans/2026-08-09-usability-mobile.md` 任务 D-2。

### 工作目录

`C:\Users\55061\Documents\数字化预案自动生成 2\.worktrees\usability-overhaul`（分支 codex/usability-overhaul）。必须 cd 到该目录操作，不要动主工作区。

### 交付内容

1. **新建 `frontend/src/mobile/screens/ChatScreen.tsx`**
   - 复用 `@/services/chatService` 的 `sendChatMessage` / `fetchConversations` / `createConversation` / `fetchMessages`（API 已确认：`sendChatMessage(message, history, conversationId, onEvent, onError, onComplete)` 返回 AbortController；`fetchConversations()`→`Conversation[]`；`fetchMessages(convId)`→`MessageResponse[]`）。
   - 功能：进入页面加载最近对话（列表第一条）历史，无对话则创建新对话；底部输入框 + 发送；发送后本地追加 user 消息 + assistant loading 占位，SSE 事件流式追加内容（`event.type === "chunk" | "progress"` 取 `content`/`message`），`conv_id` 事件更新会话 id；完成/错误处理（错误 toast、loading 复位）。
   - 历史上下文：`sendChatMessage` 传最近 10 条消息（role/content 映射为 `ChatMessage[]`）。
   - 卸载清理：保存 sendChatMessage 返回的 AbortController 并在组件卸载/切换会话时 abort，避免 setState on unmounted（用 ref 持有）。
   - UI 结构：`SafeArea` + `NavBar title="AI 助手"`（返回 `/m/settings`）+ 消息列表（可滚动，自动滚到底）+ 底部输入区 + `Toast`。
   - 消息气泡：用户气泡 `bg-primary-600 text-white`，AI 气泡 `bg-white border border-neutral-100 text-neutral-900`，`max-w-[82%]`、`whitespace-pre-wrap`、`rounded-md`；loading 占位显示「思考中…」（可加 Spinner/动画）。
   - 输入框用 `@/mobile/components/ui/Input`（`multiline` 支持回车发送/Shift 换行或保持简单回车发送），发送按钮用 `@/mobile/components/ui/Button`（icon={<Send/>}，`loading={loading}`）。禁止原生 `<input>`/`<button>` 裸写（与全 App 移动端一致）。
   - **禁止硬编码色**：不得出现 `#1677ff`/`#333`/`#f0f7ff` 等 antd 色或任意十六进制色，一律用移动端 token 类（`bg-primary-*`/`text-neutral-*`/`border-neutral-*`）。参考同屏其他移动端页面惯例。
   - **禁止 `any`**：SSE 事件用 `ChatSSEEvent` 类型、历史消息映射为 `ChatMessage`、`MessageResponse` 用其声明字段。文件可保留 `// @ts-nocheck`（移动端惯例），但新增代码类型必须写正确。

2. **修改 `frontend/src/mobile/routes.tsx`**
   - 增加 `const ChatScreen = lazy(() => import("@/mobile/screens/ChatScreen"));`
   - 在设置分组下加 `{ path: "chat", element: <ChatScreen /> }`（保持 ai-config 路由暂存，D-3 再删）。

3. **修改 `frontend/src/mobile/screens/SettingsScreen.tsx`**
   - `MENU_ITEMS` 将 `ai-config` 项替换为 `{ key: "ai-assistant", icon: <Bot size={20} />, label: "AI 助手", path: "/m/chat" }`（无 sub 文案，或保留简洁 sub 如「智能问答」均可）。
   - 保留 `Bot` 图标导入；确认删除后无未使用导入（若 `Bot` 仍在用则不动）。

### 质量门禁（必须全部通过）

1. `cd frontend && npx tsc -p tsconfig.app.json --noEmit` 退出码 0
2. `npx eslint src/mobile/screens/ChatScreen.tsx src/mobile/routes.tsx src/mobile/screens/SettingsScreen.tsx` 不得新增 error（既有错误需逐项说明）
3. `git diff --check` 干净
4. 改动文件不得新增 `any`；新增代码无 >100 字符行
5. 单提交、提交信息如 `feat(mobile): AI assistant chat screen and settings entry`，只含上述 3 个文件

### 提交

完成后 `git add` + `git commit`，运行 complete 脚本，报告：改动文件清单 + 提交 SHA、实现要点、门禁验证输出摘要。

