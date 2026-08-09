# 易用性整体优化 · 计划 D（移动端）实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 移动端对齐——首页完成度卡片 + 各模块直达入口、AI 助手入口与聊天页、移除用户级 AI 模型配置。

**架构：** 复用桌面 `chatService`（后端 `/chat` 能力一致）；`DashboardScreen` 增加完成度卡片（复用 `getEnterpriseCompletion`）；`SettingsScreen` 移除 AI 配置入口并增加 AI 助手入口；新增 `ChatScreen`。

**技术栈：** React Native Web（自研 UI 组件）+ TypeScript + TanStack Query。

**规格依据：** `docs/superpowers/specs/2026-08-08-usability-enhancement-design.md` 第 13 节。

**依赖：** 先执行计划 A（死按钮修复）、B（completion 接口）。

**基线：** master 已合入预案附图扩展（94cc4bf）。本计划不涉及附图扩展改动文件，无冲突。

---

## 文件结构

| 文件 | 职责 | 动作 |
|------|------|------|
| `frontend/src/mobile/screens/ChatScreen.tsx` | AI 助手聊天页 | 新建 |
| `frontend/src/mobile/screens/DashboardScreen.tsx` | 完成度卡片 + 直达入口 | 修改 |
| `frontend/src/mobile/screens/SettingsScreen.tsx` | 移除 AI 配置、增加 AI 助手入口 | 修改 |
| `frontend/src/mobile/routes.tsx` | 增加 `/m/chat`、移除 `/m/settings/ai-config` | 修改 |

---

### 任务 D-1：完成度卡片（DashboardScreen）

**文件：**
- 修改：`frontend/src/mobile/screens/DashboardScreen.tsx`

- [ ] **步骤 1：实现完成度卡片**

在 `frontend/src/mobile/screens/DashboardScreen.tsx` 中：

1. 引入查询：

```tsx
import { getEnterpriseCompletion } from "@/services/onboardingService";

const completionQuery = useQuery({
  queryKey: ["completion", activeEnterpriseId],
  queryFn: () => getEnterpriseCompletion(activeEnterpriseId!),
  enabled: !!activeEnterpriseId,
});
```

2. 在统计卡之前渲染完成度卡片（移动端样式）：

```tsx
{completionQuery.data && (
  <div className="mx-md mt-md" style={{ border: "1px solid #1677ff", borderRadius: 10, padding: 12, background: "#f0f7ff" }}>
    <div className="flex justify-between items-center mb-sm">
      <p className="text-body font-semibold">企业数据完成度 {completionQuery.data.percent}%</p>
    </div>
    <div style={{ height: 6, background: "#d9d9d9", borderRadius: 3, overflow: "hidden", marginBottom: 8 }}>
      <div style={{ width: `${completionQuery.data.percent}%`, height: "100%", background: "#1677ff" }} />
    </div>
    <div className="flex flex-wrap gap-xs mb-sm">
      {completionQuery.data.modules
        .filter((m: any) => !m.done)
        .map((m: any) => (
          <span key={m.key} style={{ fontSize: 11, background: "#fff7e6", border: "1px solid #ffe7ba", borderRadius: 4, padding: "1px 6px" }}>
            {m.label}
          </span>
        ))}
    </div>
    <button
      className="bg-primary-500 text-white rounded-md px-sm py-xs text-body-sm"
      onClick={() => navigate(`/m/onboarding?enterprise_id=${activeEnterpriseId}`)}
    >
      去补数据 / 直达入口
    </button>
  </div>
)}
```

3. 各模块「去补 XX」直达入口（映射到移动端已有路由：组织架构→`/m/enterprises/{id}`、风险→`/m/enterprises/{id}/risk-management`、资源→`/m/enterprises/{id}/resources`、周边→`/m/enterprises/{id}`）。

（`/m/onboarding` 路由在 D-3 说明：移动端不建完整引导页，此按钮直接跳企业详情对应模块，或跳企业详情页；实现时选择跳转 `activeEnterpriseId` 详情页。）

- [ ] **步骤 2：tsc 验证并 Commit**

运行：`cd frontend && npx tsc --noEmit`

预期：无类型错误。

```bash
git add frontend/src/mobile/screens/DashboardScreen.tsx
git commit -m "feat(mobile): completion card on dashboard with module shortcuts"
```

---

### 任务 D-2：AI 助手聊天页

**文件：**
- 新建：`frontend/src/mobile/screens/ChatScreen.tsx`
- 修改：`frontend/src/mobile/routes.tsx`
- 修改：`frontend/src/mobile/screens/SettingsScreen.tsx`

- [ ] **步骤 1：实现 ChatScreen（复用 chatService）**

新建 `frontend/src/mobile/screens/ChatScreen.tsx`：

```tsx
// @ts-nocheck
import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Send } from "lucide-react";
import NavBar from "@/mobile/components/ui/NavBar";
import SafeArea from "@/mobile/components/ui/SafeArea";
import Toast, { useToast } from "@/mobile/components/ui/Toast";
import {
  sendChatMessage,
  fetchConversations,
  createConversation,
  fetchMessages,
} from "@/services/chatService";

export default function ChatScreen() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [messages, setMessages] = useState<Array<{ role: string; content: string; loading?: boolean }>>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [convId, setConvId] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchConversations().then(async (list) => {
      if (list.length > 0) {
        setConvId(list[0].id);
        const msgs = await fetchMessages(list[0].id);
        setMessages(msgs.map((m: any) => ({ role: m.role, content: m.content })));
      } else {
        const conv = await createConversation();
        setConvId(conv.id);
      }
    }).catch(() => showToast?.("加载对话失败", "error"));
  }, []);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text }, { role: "assistant", content: "", loading: true }]);
    setLoading(true);
    let buf = "";
    sendChatMessage(text, messages.slice(-10), convId, (event: any) => {
      if (event.type === "chunk" || event.type === "progress") buf += event.content || event.message || "";
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last && last.role === "assistant") { last.content = buf; last.loading = false; }
        return [...next];
      });
    }, (err) => {
      setLoading(false);
      showToast?.(err || "生成失败", "error");
    }, () => setLoading(false));
  };

  return (
    <SafeArea className="bg-neutral-50 min-h-dvh">
      <NavBar
        title="AI 助手"
        left={<ArrowLeft size={20} onClick={() => navigate("/m/settings")} />}
      />
      <div ref={listRef} className="flex-1 overflow-y-auto px-md py-md space-y-sm" style={{ height: "calc(100dvh - 160px)" }}>
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
            <div
              className="inline-block rounded-md px-md py-sm text-body-sm"
              style={{ background: m.role === "user" ? "#1677ff" : "#fff", color: m.role === "user" ? "#fff" : "#333", maxWidth: "82%", whiteSpace: "pre-wrap" }}
            >
              {m.loading ? "思考中…" : m.content || ""}
            </div>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-sm px-md py-sm bg-white border-t border-neutral-100">
        <input
          className="flex-1 rounded-md border border-neutral-200 px-sm py-xs text-body-sm"
          placeholder="问 AI 助手…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
        />
        <button className="bg-primary-500 text-white rounded-md p-xs" onClick={handleSend} disabled={loading}>
          <Send size={18} />
        </button>
      </div>
      <Toast />
    </SafeArea>
  );
}
```

- [ ] **步骤 2：路由 + 设置入口**

`frontend/src/mobile/routes.tsx` 增加：

```tsx
const ChatScreen = lazy(() => import("@/mobile/screens/ChatScreen"));
...
{ path: "chat", element: <ChatScreen /> },
```

`frontend/src/mobile/screens/SettingsScreen.tsx`：

1. `MENU_ITEMS` 增加：

```tsx
{
  key: "ai-assistant",
  icon: <Bot size={20} />,
  label: "AI 助手",
  path: "/m/chat",
},
```

2. 删除 `ai-config` 菜单项（保留 `Bot` 图标导入给 AI 助手用）。

- [ ] **步骤 3：tsc 验证并 Commit**

运行：`cd frontend && npx tsc --noEmit`

预期：无类型错误。

```bash
git add frontend/src/mobile/screens/ChatScreen.tsx frontend/src/mobile/routes.tsx frontend/src/mobile/screens/SettingsScreen.tsx
git commit -m "feat(mobile): AI assistant chat screen and settings entry"
```

---

### 任务 D-3：移除用户级 AI 模型配置

**文件：**
- 修改：`frontend/src/mobile/routes.tsx`
- 删除：`frontend/src/mobile/screens/AIModelConfigScreen.tsx`

- [ ] **步骤 1：移除路由与页面**

`frontend/src/mobile/routes.tsx`：

- 删除 `{ path: "settings/ai-config", element: <AIModelConfigScreen /> }`。
- 删除 `const AIModelConfigScreen = lazy(...)` 导入。

删除文件 `frontend/src/mobile/screens/AIModelConfigScreen.tsx`。

- [ ] **步骤 2：tsc 验证并 Commit**

运行：`cd frontend && npx tsc --noEmit`

预期：无类型错误（确保无其它文件引用 AIModelConfigScreen）。

```bash
git add -A frontend/src/mobile/routes.tsx frontend/src/mobile/screens/AIModelConfigScreen.tsx
git commit -m "chore(mobile): remove user-level AI model config screen"
```

---

### 任务 D-4：全量验证

**文件：** 无新增修改

- [ ] **步骤 1：前端全量验证**

运行：`cd frontend && npx tsc --noEmit && npx vitest run`

预期：tsc 无错误，vitest 全部通过。

- [ ] **步骤 2：移动端构建验证**

运行：`cd frontend && npm run build -- --mode mobile 2>&1 | Select-String -Pattern "error"`（或按项目现有移动端构建命令）

预期：构建无错误。

- [ ] **步骤 3：Commit（如有残留）**

```bash
git status --short
```

---

## 计划 D 自检

**规格覆盖度：** 第 13 节移动端（完成度卡片、AI 助手入口、移除用户级 AI 配置、死按钮修复[计划 A]）→ D-1/D-2/D-3。无遗漏。

**占位符扫描：** 无 TODO/待定；`/m/onboarding` 跳转说明明确（移动端不建引导页，直达企业详情）。

**类型一致性：** `chatService` 的 `sendChatMessage(text, history, convId, onEvent, onError, onComplete)` 签名与桌面一致；`completionQuery.data.percent/modules` 与计划 B 返回结构一致。
