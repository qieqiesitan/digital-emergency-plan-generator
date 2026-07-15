import { createContext, useContext, useState, type ReactNode } from "react";

interface ChatDrawerContextValue {
  open: boolean;
  setOpen: (v: boolean) => void;
}

const ChatDrawerContext = createContext<ChatDrawerContextValue | null>(null);

export function ChatDrawerProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <ChatDrawerContext.Provider value={{ open, setOpen }}>
      {children}
    </ChatDrawerContext.Provider>
  );
}

export function useChatDrawer(): ChatDrawerContextValue {
  const ctx = useContext(ChatDrawerContext);
  if (!ctx) throw new Error("useChatDrawer must be used within ChatDrawerProvider");
  return ctx;
}
