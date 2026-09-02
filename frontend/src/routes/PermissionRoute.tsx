import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { Button, Result, Spin } from "antd";
import { useAuth } from "@/contexts/AuthContext";

/**
 * 菜单权限路由守卫：无对应 menuPermissions 时显示「无权限」页，
 * 避免绕过侧边菜单直接输入 URL 访问管理页面。
 */
export function PermissionRoute({
  required,
  children,
}: {
  required: string;
  children: ReactNode;
}) {
  const { menuPermissions, menuLoading } = useAuth();
  const navigate = useNavigate();

  if (menuLoading) {
    return (
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          minHeight: 280,
        }}
      >
        <Spin size="large" description="加载中..." />
      </div>
    );
  }

  if (!menuPermissions.includes(required)) {
    return (
      <Result
        status="403"
        title="无权限访问"
        subTitle="当前账号没有访问该页面的权限，如有需要请联系管理员。"
        extra={
          <Button type="primary" onClick={() => navigate("/dashboard", { replace: true })}>
            返回工作台
          </Button>
        }
      />
    );
  }

  return <>{children}</>;
}
