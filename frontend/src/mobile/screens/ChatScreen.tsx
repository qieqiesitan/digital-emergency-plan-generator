import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Bot, Send } from "lucide-react";
import NavBar from "@/mobile/components/ui/NavBar";
import SafeArea from "@/mobile/components/ui/SafeArea";
import Spinner from "@/mobile/components/ui/Spinner";
import Input from "@/mobile/components/ui/Input";
import Button from "@/mobile/components/ui/Button";
import { useToast } from "@/mobile/components/ui/Toast";
import {
  sendChatMessage,
  fetchConversations,
  createConversation,
  fetchMessages,
  type ChatMessage,
  type ChatSSEEvent,
} from "@/services/chatService";

interface DisplayMessage {
  role: "user" | "assistant";
  content: string;
  loading?: boolean;
}

export default function ChatScreen() {
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [convId, setConvId] = useState<string | null>(null);
  const [initializing, setInitializing] = useState(true);

  const listRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // 进入页面：加载最近对话（列表第一条）历史，无对话则创建新对话
  useEffect(() => {
    let cancelled = false;
    const init = async () => {
      try {
        const list = await fetchConversations();
        if (cancelled) return;
        if (list.length > 0) {
          const conv = list[0];
          setConvId(conv.id);
          const msgs = await fetchMessages(conv.id);
          if (cancelled) return;
          setMessages(
            msgs.map((m) => ({
              role: m.role === "assistant" ? "assistant" : "user",
              content: m.content,
            }))
          );
        } else {
          const conv = await createConversation();
          if (cancelled) return;
          setConvId(conv.id);
        }
      } catch {
        if (!cancelled) {
          showToast?.({ type: "error", message: "加载对话失败" });
        }
      } finally {
        if (!cancelled) setInitializing(false);
      }
    };
    init();
    return () => {
      cancelled = true;
      abortRef.current?.abort();
    };
  }, [showToast]);

  // 消息变化自动滚动到底部
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || loading) return;
    abortRef.current?.abort();

    setInput("");
    setLoading(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: text },
      { role: "assistant", content: "", loading: true },
    ]);

    const history: ChatMessage[] = messages.slice(-10).map((m) => ({
      role: m.role,
      content: m.content,
    }));

    let buf = "";

    const controller = sendChatMessage(
      text,
      history,
      convId,
      (event: ChatSSEEvent) => {
        if (event.type === "chunk" || event.type === "progress") {
          buf += event.content || event.message || "";
        }
        if (event.type === "conv_id" && event.content) {
          setConvId(event.content);
        }
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (!last || last.role !== "assistant") return prev;
          return [
            ...prev.slice(0, -1),
            { ...last, content: buf, loading: false },
          ];
        });
      },
      (err: string) => {
        setLoading(false);
        showToast?.({ type: "error", message: err || "生成失败" });
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (!last || last.role !== "assistant") return prev;
          return [
            ...prev.slice(0, -1),
            {
              ...last,
              content: (last.content || "") + `\n❌ ${err || "生成失败"}`,
              loading: false,
            },
          ];
        });
      },
      (convIdFromServer?: string) => {
        setLoading(false);
        if (convIdFromServer) setConvId(convIdFromServer);
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (!last || last.role !== "assistant") return prev;
          return [
            ...prev.slice(0, -1),
            { ...last, content: last.content || "（无回复）", loading: false },
          ];
        });
      }
    );
    abortRef.current = controller;
  }, [input, loading, messages, convId, showToast]);

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <SafeArea className="bg-neutral-50 min-h-dvh flex flex-col">
      <NavBar title="AI 助手" showBack onBack={() => navigate("/m/settings")} />

      {/* 消息列表 */}
      <div ref={listRef} className="flex-1 overflow-y-auto px-md py-md space-y-sm">
        {initializing ? (
          <div className="flex flex-col items-center justify-center py-20">
            <Spinner size="lg" />
            <p className="text-body text-neutral-500 mt-md">加载对话中…</p>
          </div>
        ) : messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <Bot size={40} className="text-neutral-300" />
            <p className="text-body text-neutral-500 mt-md">
              你好！我是 AI 助手，可以帮你解答预案相关问题。
            </p>
          </div>
        ) : (
          messages.map((m, i) => (
            <div
              key={i}
              className={m.role === "user" ? "flex justify-end" : "flex justify-start"}
            >
              <div
                className={`max-w-[82%] whitespace-pre-wrap rounded-md px-md py-sm text-body-sm ${
                  m.role === "user"
                    ? "bg-primary-600 text-white"
                    : "bg-white border border-neutral-100 text-neutral-900"
                }`}
                style={{
                  maxWidth: "82%",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {m.loading ? (
                  <span className="flex items-center gap-xs text-neutral-400">
                    <Spinner size="sm" /> 思考中…
                  </span>
                ) : (
                  m.content
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* 底部输入区 */}
      <div
        className="flex items-center gap-sm px-md py-sm bg-white border-t border-neutral-100"
        style={{ paddingBottom: "calc(8px + var(--safe-bottom))" }}
      >
        <div className="flex-1 min-w-0" onKeyDown={handleKeyDown}>
          <Input
            multiline
            value={input}
            onChange={(v) => setInput(v)}
            placeholder="输入消息… 回车发送，Shift+Enter 换行"
            disabled={loading}
          />
        </div>
        <Button
          variant="primary"
          size="md"
          icon={<Send size={18} />}
          loading={loading}
          disabled={!input.trim()}
          onClick={handleSend}
          aria-label="发送"
        />
      </div>
    </SafeArea>
  );
}
