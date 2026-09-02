import { getApiBaseUrl } from "@/utils/platform";
import { sseFetch } from "./sseFetch";

export interface ChatMessage {
  role: "user" | "assistant" | "function";
  content: string | null;
  name?: string | null;
}

export interface ToolCallStep {
  id: string;
  round_no: number;
  fn_name: string;
  status: "running" | "success" | "error";
  duration_ms: number | null;
  created_at: string;
}

export interface ChatSSEEvent {
  type: "progress" | "chunk" | "function_result" | "tool_step" | "error" | "done" | "conv_id";
  message?: string;
  content?: string;
  html?: boolean;
  name?: string;
  result?: string;
  status?: "success" | "error";
  duration_ms?: number;
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
  name?: string | null;
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
  let finalConvId: string | undefined;

  sseFetch({
    path: "/chat",
    method: "POST",
    body: { message, history, conversation_id: conversationId },
    signal: controller.signal,
    errorMessage: "请求失败",
    onData: (data) => {
      try {
        const event: ChatSSEEvent = JSON.parse(data);
        if (event.type === "conv_id" && event.content) {
          finalConvId = event.content;
        }
        onEvent(event);
      } catch {
        // skip malformed events
      }
    },
    onComplete: () => onComplete(finalConvId),
    onError,
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

export async function fetchToolCalls(convId: string): Promise<ToolCallStep[]> {
  const res = await fetch(`${getApiBaseUrl()}/chat/conversations/${convId}/tool-calls`, { headers: headers() });
  if (!res.ok) throw new Error("获取工具步骤失败");
  return res.json();
}
