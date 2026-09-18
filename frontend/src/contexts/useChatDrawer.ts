import { createContext, useContext } from "react";

export interface ChatDrawerContextValue {
  open: boolean;
  setOpen: (v: boolean) => void;
}

/** 悬浮对话抽屉上下文对象：ChatDrawerProvider 提供，useChatDrawer 消费 */
export const ChatDrawerContext = createContext<ChatDrawerContextValue | null>(null);

export function useChatDrawer(): ChatDrawerContextValue {
  const ctx = useContext(ChatDrawerContext);
  if (!ctx) throw new Error("useChatDrawer must be used within ChatDrawerProvider");
  return ctx;
}
