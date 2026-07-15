import { getApiBaseUrl } from "@/utils/platform";

export interface ChatMessage {
  role: "user" | "assistant" | "function";
  content: string | null;
  name?: string | null;
}

export interface ChatSSEEvent {
  type: "progress" | "chunk" | "function_result" | "error" | "done" | "conv_id";
  message?: string;
  content?: string;
  html?: boolean;
  name?: string;
  result?: string;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface MessageResponse {
  id: string;
  role: string;
  content: string;
  created_at: string;
}

// ─── SSE 聊天 ───

export function sendChatMessage(
  message: string,
  history: ChatMessage[],
  conversationId: string | null,
  onEvent: (event: ChatSSEEvent) => void,
  onError: (error: string) => void,
  onComplete: (convId?: string) => void,
): AbortController {
  const controller = new AbortController();
  const token = localStorage.getItem("access_token");

  fetch(`${getApiBaseUrl()}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ message, history, conversation_id: conversationId }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: "请求失败" }));
        onError(err.detail || err.message || "请求失败");
        return;
      }
      const reader = response.body?.getReader();
      if (!reader) { onError("无法读取响应流"); return; }

      const decoder = new TextDecoder();
      let buffer = "";
      let finalConvId: string | undefined;

      while (true) {
        const { done, value } = await reader.read();
        if (done) { onComplete(finalConvId); break; }
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const event: ChatSSEEvent = JSON.parse(line.slice(6));
              if (event.type === "conv_id" && event.content) {
                finalConvId = event.content;
              }
              onEvent(event);
            } catch { /* skip */ }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        onError(err.message || "网络错误");
      }
    });

  return controller;
}

// ─── 对话 CRUD ───

const headers = () => {
  const token = localStorage.getItem("access_token");
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
};

export async function fetchConversations(): Promise<Conversation[]> {
  const res = await fetch(`${getApiBaseUrl()}/chat/conversations`, { headers: headers() });
  if (!res.ok) throw new Error("获取对话列表失败");
  return res.json();
}

export async function createConversation(): Promise<Conversation> {
  const res = await fetch(`${getApiBaseUrl()}/chat/conversations`, { method: "POST", headers: headers() });
  if (!res.ok) throw new Error("创建对话失败");
  return res.json();
}

export async function deleteConversation(id: string): Promise<void> {
  const res = await fetch(`${getApiBaseUrl()}/chat/conversations/${id}`, { method: "DELETE", headers: headers() });
  if (!res.ok) throw new Error("删除对话失败");
}

export async function fetchMessages(convId: string): Promise<MessageResponse[]> {
  const res = await fetch(`${getApiBaseUrl()}/chat/conversations/${convId}/messages`, { headers: headers() });
  if (!res.ok) throw new Error("获取消息失败");
  return res.json();
}
