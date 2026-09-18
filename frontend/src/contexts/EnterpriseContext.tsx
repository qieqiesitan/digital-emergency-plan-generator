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

  // 如果当前企业不在列表中，自动选择第一个
  useEffect(() => {
    if (enterprises.length > 0) {
      const exists = enterprises.some((e) => e.id === currentEnterpriseId);
      if (!exists) {
        setCurrentEnterprise(enterprises[0].id);
      }
    }
  }, [enterprises, currentEnterpriseId, setCurrentEnterprise]);

  const refreshEnterprises = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ["enterprises"] });
  }, [queryClient]);

  return (
    <EnterpriseContext.Provider
      value={{ currentEnterpriseId, enterprises, isLoading, setCurrentEnterprise, refreshEnterprises }}
    >
      {children}
    </EnterpriseContext.Provider>
  );
}

