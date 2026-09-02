import { useMemo } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";
import { ConfigProvider, App as AntApp } from "antd";
import zhCN from "antd/locale/zh_CN";
import { AuthProvider } from "@/contexts/AuthContext";
import { EnterpriseProvider } from "@/contexts/EnterpriseContext";
import { ChatDrawerProvider } from "@/contexts/ChatDrawerContext";
import { createRouter } from "@/routes";
import "@/styles/global.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // F4：服务端已返回 4xx/5xx 的错误不再自动重试（避免拦截器全局错误 toast 重复弹出），
      // 仅网络/超时类无响应错误重试一次。
      retry: (failureCount, error) => {
        if (failureCount >= 1) return false;
        return !(error as { response?: unknown })?.response;
      },
      staleTime: 30000,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  const router = useMemo(() => createRouter(), []);

  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider locale={zhCN} theme={{ token: { colorPrimary: "#1677ff" } }}>
        <AntApp>
          <AuthProvider>
            <EnterpriseProvider>
              <ChatDrawerProvider>
                <RouterProvider router={router} />
              </ChatDrawerProvider>
            </EnterpriseProvider>
          </AuthProvider>
        </AntApp>
      </ConfigProvider>
    </QueryClientProvider>
  );
}
