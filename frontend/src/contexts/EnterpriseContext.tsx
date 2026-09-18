import { useState, useEffect, useCallback, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { listEnterprises } from "@/services/enterpriseService";
import { useAuth } from "@/contexts/useAuth";
import { EnterpriseContext } from "@/contexts/useCurrentEnterprise";

export function EnterpriseProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [currentEnterpriseId, setCurrentEnterpriseId] = useState<string | null>(
    () => localStorage.getItem("currentEnterpriseId")
  );
  const queryClient = useQueryClient();

  const { data: enterprisesData, isLoading } = useQuery({
    queryKey: ["enterprises"],
    queryFn: async () => {
      const res = await listEnterprises({ page_size: 100 });
      return res.data.items;
    },
    // 未认证时不发起企业列表请求（登录页也会挂载本 Provider，避免无 token 时 401 刷屏）
    enabled: isAuthenticated,
  });

  const enterprises = enterprisesData || [];

  const setCurrentEnterprise = useCallback((id: string) => {
    localStorage.setItem("currentEnterpriseId", id);
    setCurrentEnterpriseId(id);
  }, []);

  // 当前企业不在列表中时回落到第一个：渲染期派生（避免 effect 内 setState）
  const effectiveEnterpriseId =
    enterprises.some((e) => e.id === currentEnterpriseId)
      ? currentEnterpriseId
      : (enterprises[0]?.id ?? null);

  // 派生值变化时同步本地存储（只写外部系统，不动 React 状态）
  useEffect(() => {
    if (effectiveEnterpriseId) {
      localStorage.setItem("currentEnterpriseId", effectiveEnterpriseId);
    }
  }, [effectiveEnterpriseId]);

  const refreshEnterprises = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ["enterprises"] });
  }, [queryClient]);

  return (
    <EnterpriseContext.Provider
      value={{ currentEnterpriseId: effectiveEnterpriseId, enterprises, isLoading, setCurrentEnterprise, refreshEnterprises }}
    >
      {children}
    </EnterpriseContext.Provider>
  );
}

