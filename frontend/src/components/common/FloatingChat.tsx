import { useState, useRef, useCallback, useEffect } from "react";
import { Drawer } from "antd";
import { CloseOutlined } from "@ant-design/icons";
import { useChatDrawer } from "@/contexts/ChatDrawerContext";
import ChatPanel from "@/pages/Chat";

// SVG: AI chip icon - hexagonal neural network pattern
const AIIcon = () => (
  <svg width="26" height="26" viewBox="0 0 26 26" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M13 2L23 7.5V18.5L13 24L3 18.5V7.5L13 2Z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
    <circle cx="13" cy="13" r="4" stroke="white" strokeWidth="1.5"/>
    <path d="M13 9V7" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
    <path d="M13 19V17" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
    <path d="M9 13H7" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
    <path d="M19 13H17" stroke="white" strokeWidth="1.5" strokeLinecap="round"/>
    <circle cx="13" cy="13" r="1.2" fill="white"/>
  </svg>
);

export default function FloatingChat() {
  const { open, setOpen } = useChatDrawer();
  const [top, setTop] = useState(() => {
    const saved = localStorage.getItem("chat_btn_top");
    return saved ? Number(saved) : window.innerHeight * 0.4;
  });
  const dragging = useRef(false);
  const startY = useRef(0);
  const startTop = useRef(0);
  const btnRef = useRef<HTMLDivElement>(null);
  const [hovered, setHovered] = useState(false);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    startY.current = e.clientY;
    startTop.current = top;
    document.body.style.userSelect = "none";
  }, [top]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current) return;
      const dy = e.clientY - startY.current;
      const newTop = Math.max(60, Math.min(window.innerHeight - 80, startTop.current + dy));
      setTop(newTop);
    };
    const onUp = () => {
      if (dragging.current) {
        dragging.current = false;
        document.body.style.userSelect = "";
        localStorage.setItem("chat_btn_top", String(top));
      }
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [top]);

  const handleClick = () => {
    if (!dragging.current) {
      setOpen(true);
    }
  };

  return (
    <>
      <div
        ref={btnRef}
        onMouseDown={onMouseDown}
        onClick={handleClick}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        style={{
          position: "fixed",
          right: 0,
          top,
          display: "flex",
          alignItems: "center",
          cursor: "grab",
          zIndex: 1000,
          userSelect: "none",
          transition: dragging.current ? "none" : "all 0.3s ease",
        }}
        title="AI 助手（可上下拖动）"
      >
        {/* Label that slides out on hover */}
        <div
          style={{
            background: "rgba(15, 23, 42, 0.9)",
            backdropFilter: "blur(12px)",
            color: "#fff",
            fontSize: 12,
            fontWeight: 600,
            padding: "6px 14px 6px 18px",
            borderRadius: "20px 0 0 20px",
            whiteSpace: "nowrap",
            letterSpacing: 1,
            opacity: hovered ? 1 : 0,
            transform: hovered ? "translateX(0)" : "translateX(20px)",
            transition: "all 0.3s ease",
            pointerEvents: "none",
            position: "absolute",
            right: 42,
            boxShadow: "0 0 20px rgba(99, 102, 241, 0.15)",
          }}
        >
          AI 助手
        </div>
        {/* Icon button */}
        <div
          style={{
            width: 50,
            height: 50,
            background: "linear-gradient(135deg, #1e1b4b 0%, #312e81 40%, #4338ca 100%)",
            borderRadius: "14px 0 0 14px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 0 24px rgba(99, 102, 241, 0.4), -2px 2px 16px rgba(0,0,0,0.2)",
            animation: "chat-btn-glow 2s ease-in-out infinite",
            position: "relative",
          }}
        >
          <AIIcon />
        </div>
      </div>

      {/* keyframes for glow animation */}
      <style>{`
        @keyframes chat-btn-glow {
          0%, 100% { box-shadow: 0 0 24px rgba(99, 102, 241, 0.4), -2px 2px 16px rgba(0,0,0,0.2); }
          50% { box-shadow: 0 0 36px rgba(139, 92, 246, 0.6), -2px 2px 24px rgba(0,0,0,0.25); }
        }
      `}</style>

      <Drawer
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <AIIcon />
            <span style={{ fontWeight: 600 }}>AI 助手</span>
          </div>
        }
        placement="right"
        width={420}
        open={open}
        onClose={() => setOpen(false)}
        closeIcon={<CloseOutlined />}
        destroyOnClose={false}
        styles={{ body: { padding: "12px 16px", height: "100%" } }}
      >
        <ChatPanel embedded />
      </Drawer>
    </>
  );
}
