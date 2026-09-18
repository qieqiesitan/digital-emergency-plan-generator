import { createContext, useContext } from "react";
import type { Enterprise } from "@/types/enterprise";

export interface EnterpriseContextValue {
  currentEnterpriseId: string | null;
  enterprises: Enterprise[];
  isLoading: boolean;
  setCurrentEnterprise: (id: string) => void;
  refreshEnterprises: () => Promise<void>;
}

/** 当前企业上下文对象：EnterpriseProvider 提供，useCurrentEnterprise 消费 */
export const EnterpriseContext = createContext<EnterpriseContextValue | null>(null);

export function useCurrentEnterprise(): EnterpriseContextValue {
  const ctx = useContext(EnterpriseContext);
  if (!ctx) throw new Error("useCurrentEnterprise must be used within EnterpriseProvider");
  return ctx;
}
