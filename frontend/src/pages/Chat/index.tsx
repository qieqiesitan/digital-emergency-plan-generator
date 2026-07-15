import { useState, useRef, useEffect, useCallback } from "react";
import { Input, Button, Typography, Spin, message, Popconfirm } from "antd";
import { SendOutlined, RobotOutlined, UserOutlined, PlusOutlined, DeleteOutlined, MessageOutlined, CloseOutlined } from "@ant-design/icons";
import {
  sendChatMessage,
  fetchConversations,
  createConversation,
  deleteConversation,
  fetchMessages,
  type ChatMessage,
  type ChatSSEEvent,
  type Conversation,
} from "@/services/chatService";

const { Text, Paragraph } = Typography;

interface DisplayMessage {
  role: "user" | "assistant" | "function";
  content: string;
  html?: boolean;
  name?: string;
  loading?: boolean;
}

interface ChatPanelProps {
  embedded?: boolean;
}

export default function ChatPanel({ embedded = false }: ChatPanelProps) {
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [convLoading, setConvLoading] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // 加载对话列表
  const loadConversations = useCallback(async () => {
    try {
      const list = await fetchConversations();
      setConversations(list);
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  // 切换对话 → 加载历史
  const switchConversation = useCallback(async (convId: string) => {
    setActiveConvId(convId);
    setConvLoading(true);
    try {
      const msgs = await fetchMessages(convId);
      const display: DisplayMessage[] = msgs.map((m) => ({
        role: m.role as DisplayMessage["role"],
        content: m.content,
      }));
      setMessages(display);
      // 构建 history（最近10轮）
      const chatMsgs: ChatMessage[] = [];
      for (const m of msgs) {
        chatMsgs.push({ role: m.role as ChatMessage["role"], content: m.content });
      }
      setHistory(chatMsgs.slice(-20)); // 保留最近10轮（20条）
    } catch {
      message.error("加载对话失败");
    } finally {
      setConvLoading(false);
    }
  }, []);

  // 新建对话
  const handleNewConv = useCallback(async () => {
    try {
      const conv = await createConversation();
      setConversations((prev) => [conv, ...prev]);
      setActiveConvId(conv.id);
      setMessages([]);
      setHistory([]);
    } catch {
      message.error("创建对话失败");
    }
  }, []);

  // 删除对话
  const handleDeleteConv = useCallback(async (convId: string) => {
    try {
      await deleteConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));
      if (activeConvId === convId) {
        setActiveConvId(null);
        setMessages([]);
        setHistory([]);
      }
    } catch {
      message.error("删除对话失败");
    }
  }, [activeConvId]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");

    const userMsg: DisplayMessage = { role: "user", content: text };
    const assistantMsg: DisplayMessage = { role: "assistant", content: "", loading: true };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setLoading(true);

    let contentBuf = "";
    let isHtml = false;

    const controller = sendChatMessage(
      text,
      history,
      activeConvId,
      (event: ChatSSEEvent) => {
        switch (event.type) {
          case "progress":
            contentBuf += `${event.message}\n`;
            break;
          case "chunk":
            if (event.html) {
              isHtml = true;
              contentBuf = event.content || "";
            } else {
              contentBuf += event.content || "";
            }
            break;
          case "error":
            contentBuf += `\n❌ ${event.message}`;
            break;
        }
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last && last.role === "assistant") {
            last.content = contentBuf;
            last.html = isHtml;
            last.loading = false;
          }
          return [...next];
        });
      },
      (err) => {
        setLoading(false);
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last && last.role === "assistant") {
            last.content = (last.content || "") + `\n❌ ${err}`;
            last.loading = false;
          }
          return next;
        });
      },
      (convId) => {
        setLoading(false);
        const finalContent = contentBuf || "（无回复）";
        setHistory((prev) => [
          ...prev,
          { role: "user", content: text },
          { role: "assistant", content: finalContent },
        ]);
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last && last.role === "assistant") {
            last.content = finalContent;
            last.html = isHtml;
            last.loading = false;
          }
          return next;
        });
        // 如果是新对话，刷新列表（标题已更新）
        if (!activeConvId && convId) {
          setActiveConvId(convId);
          loadConversations();
        }
      }
    );
    abortRef.current = controller;
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleStop = () => {
    abortRef.current?.abort();
    setLoading(false);
  };

  // ─── 内嵌模式（浮动按钮 Drawer）：不显示对话列表 ───
  // ─── 内嵌模式（浮动按钮 Drawer）───
  if (embedded) {
    return (
      <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
        {/* 对话选择 + 新建 */}
        <div style={{ display: "flex", gap: 6, marginBottom: 8, alignItems: "center" }}>
          <div
            style={{
              flex: 1,
              display: "flex",
              gap: 4,
              overflowX: "auto",
              paddingBottom: 2,
              scrollbarWidth: "none",
            } as React.CSSProperties}
          >
            {conversations.map((c) => (
              <div
                key={c.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 2,
                  padding: "3px 4px 3px 10px",
                  borderRadius: 12,
                  fontSize: 12,
                  cursor: "pointer",
                  whiteSpace: "nowrap",
                  flexShrink: 0,
                  maxWidth: 150,
                  background: activeConvId === c.id ? "#1677ff" : "#f0f0f0",
                  color: activeConvId === c.id ? "#fff" : "#666",
                  fontWeight: activeConvId === c.id ? 500 : 400,
                  transition: "all 0.2s",
                }}
              >
                <span
                  onClick={() => switchConversation(c.id)}
                  style={{ overflow: "hidden", textOverflow: "ellipsis" }}
                >
                  {c.title}
                </span>
                <Popconfirm
                  title="删除？"
                  onConfirm={(e) => { e?.stopPropagation(); handleDeleteConv(c.id); }}
                  onCancel={(e) => e?.stopPropagation()}
                  okText="删"
                  cancelText="否"
                  placement="bottom"
                >
                  <CloseOutlined
                    onClick={(e) => e.stopPropagation()}
                    style={{
                      fontSize: 10,
                      padding: 2,
                      borderRadius: "50%",
                      color: activeConvId === c.id ? "rgba(255,255,255,0.7)" : "#999",
                      flexShrink: 0,
                    }}
                  />
                </Popconfirm>
              </div>
            ))}
          </div>
          <Button size="small" icon={<PlusOutlined />} onClick={handleNewConv} disabled={loading} style={{ flexShrink: 0 }} />
        </div>
        <div
          ref={listRef}
          style={{
            flex: 1,
            overflow: "auto",
            marginBottom: 8,
            background: "#fff",
            borderRadius: 8,
            padding: 8,
          }}
        >
          {convLoading ? (
            <div style={{ textAlign: "center", paddingTop: 40 }}><Spin size="small" /></div>
          ) : messages.length === 0 ? (
            <div style={{ textAlign: "center", color: "#999", paddingTop: 40 }}>
              <RobotOutlined style={{ fontSize: 36, marginBottom: 12 }} />
              <Paragraph type="secondary" style={{ fontSize: 12 }}>
                你好！可以问我系统里的数据：
              </Paragraph>
              <Paragraph type="secondary" style={{ fontSize: 12 }}>
                "查看仪表盘" · "列出企业" · "生成系统概览报告"
              </Paragraph>
            </div>
          ) : (
            messages.map((msg, i) => (
              <div
                key={i}
                style={{
                  marginBottom: 8,
                  display: "flex",
                  justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
                }}
              >
                <div
                  style={{
                    maxWidth: msg.role === "user" ? "75%" : "95%",
                    padding: msg.role === "user" ? "8px 14px" : "12px 16px",
                    borderRadius: 12,
                    background: msg.role === "user" ? "#1677ff" : "#fff",
                    color: msg.role === "user" ? "#fff" : "#333",
                    border: msg.role === "assistant" ? "1px solid #e8e8e8" : "none",
                    fontSize: 13,
                    overflow: "hidden",
                  }}
                >
                  {msg.loading ? (
                    <Spin size="small" />
                  ) : msg.role === "user" ? (
                    <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{msg.content}</div>
                  ) : msg.html ? (
                    <div dangerouslySetInnerHTML={{ __html: msg.content }} />
                  ) : (
                    <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{msg.content}</div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入消息..."
            autoSize={{ minRows: 1, maxRows: 3 }}
            disabled={loading}
            style={{ flex: 1, fontSize: 13 }}
          />
          {loading ? (
            <Button danger size="small" onClick={handleStop}>停止</Button>
          ) : (
            <Button type="primary" size="small" icon={<SendOutlined />} onClick={handleSend} disabled={!input.trim()} />
          )}
        </div>
      </div>
    );
  }
  // ─── 全屏模式（/chat 路由）：对话列表 + 消息区 ───
  return (
    <div style={{ display: "flex", height: "calc(100vh - 200px)", gap: 0 }}>
      {/* 对话列表侧边 */}
      <div
        style={{
          width: 220,
          borderRight: "1px solid #f0f0f0",
          display: "flex",
          flexDirection: "column",
          background: "#fafafa",
        }}
      >
        <div style={{ padding: "12px 12px 8px", borderBottom: "1px solid #f0f0f0" }}>
          <Button type="primary" block icon={<PlusOutlined />} onClick={handleNewConv}>
            新建对话
          </Button>
        </div>
        <div style={{ flex: 1, overflow: "auto", padding: 4 }}>
          {conversations.map((c) => (
            <div
              key={c.id}
              onClick={() => switchConversation(c.id)}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "8px 10px",
                margin: "2px 4px",
                borderRadius: 8,
                cursor: "pointer",
                background: activeConvId === c.id ? "#e6f4ff" : "transparent",
                transition: "background 0.2s",
              }}
            >
              <div style={{ flex: 1, overflow: "hidden" }}>
                <Text
                  style={{
                    fontSize: 13,
                    fontWeight: activeConvId === c.id ? 600 : 400,
                    display: "block",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  <MessageOutlined style={{ marginRight: 6, fontSize: 11 }} />
                  {c.title}
                </Text>
              </div>
              <Popconfirm
                title="删除此对话？"
                onConfirm={(e) => {
                  e?.stopPropagation();
                  handleDeleteConv(c.id);
                }}
                onCancel={(e) => e?.stopPropagation()}
                okText="删除"
                cancelText="取消"
              >
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={(e) => e.stopPropagation()}
                  style={{ opacity: 0.4, flexShrink: 0 }}
                />
              </Popconfirm>
            </div>
          ))}
          {conversations.length === 0 && (
            <div style={{ textAlign: "center", color: "#bbb", paddingTop: 30, fontSize: 12 }}>
              暂无对话
            </div>
          )}
        </div>
      </div>

      {/* 消息区 */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "0 16px" }}>
        {!activeConvId ? (
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", color: "#999" }}>
            <RobotOutlined style={{ fontSize: 48, marginBottom: 16, color: "#d9d9d9" }} />
            <Text type="secondary">选择左侧对话或新建一个</Text>
          </div>
        ) : convLoading ? (
          <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Spin />
          </div>
        ) : (
          <>
            <div
              ref={listRef}
              style={{
                flex: 1,
                overflow: "auto",
                marginBottom: 12,
                borderRadius: 8,
                padding: 12,
              }}
            >
              {messages.map((msg, i) => (
                <div
                  key={i}
                  style={{
                    marginBottom: 10,
                    display: "flex",
                    justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
                  }}
                >
                  <div
                    style={{
                      maxWidth: msg.role === "user" ? "60%" : "85%",
                      padding: msg.role === "user" ? "8px 14px" : "12px 16px",
                      borderRadius: 12,
                      background: msg.role === "user" ? "#1677ff" : "#f5f5f5",
                      color: msg.role === "user" ? "#fff" : "#333",
                      fontSize: 14,
                      overflow: "hidden",
                    }}
                  >
                    {msg.loading ? (
                      <Spin size="small" />
                    ) : msg.role === "user" ? (
                      <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{msg.content}</div>
                    ) : msg.html ? (
                      <div dangerouslySetInnerHTML={{ __html: msg.content }} />
                    ) : (
                      <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{msg.content}</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", gap: 8, paddingBottom: 8 }}>
              <Input.TextArea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入消息... Enter 发送，Shift+Enter 换行"
                autoSize={{ minRows: 1, maxRows: 4 }}
                disabled={loading}
                style={{ flex: 1, fontSize: 14 }}
              />
              {loading ? (
                <Button danger onClick={handleStop}>停止</Button>
              ) : (
                <Button type="primary" icon={<SendOutlined />} onClick={handleSend} disabled={!input.trim()}>发送</Button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
