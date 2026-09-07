import { Navigate, useLocation } from "react-router-dom";
import { Spin } from "antd";
import { useAuth } from "@/contexts/AuthContext";
import { buildLoginPath } from "@/routing/loginRedirect";
import { stripAppBase } from "@/utils/platform";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
        <Spin size="large" description="加载中..." />
      </div>
    );
  }

  if (!isAuthenticated) {
    // 携带来源页，登录成功后回跳；只允许站内相对路径（buildLoginPath 内校验）
    const redirect = stripAppBase(location.pathname) + location.search;
    return <Navigate to={buildLoginPath(redirect)} replace />;
  }

  return <>{children}</>;
}
