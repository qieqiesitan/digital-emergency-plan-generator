import { createContext, useContext } from "react";

export type ToastType = "success" | "error" | "warning" | "info";

export interface ToastOptions {
  type: ToastType;
  message: string;
  duration?: number;
}

interface ToastContextValue {
  showToast: (options: ToastOptions) => void;
}

/** Toast 上下文对象：ToastProvider 提供，useToast 消费 */
export const ToastContext = createContext<ToastContextValue>({
  showToast: () => {},
});

export function useToast() {
  return useContext(ToastContext);
}
