import { useState, type ReactNode } from "react";
import { ChatDrawerContext } from "@/contexts/useChatDrawer";

export function ChatDrawerProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <ChatDrawerContext.Provider value={{ open, setOpen }}>
      {children}
    </ChatDrawerContext.Provider>
  );
}

