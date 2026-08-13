import { useState, useMemo } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Layout, Menu, Button, Dropdown, Avatar, theme, Alert } from "antd";
import {
  DashboardOutlined,
  BankOutlined,
  FileTextOutlined,
  SettingOutlined,
  UserOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  KeyOutlined,
  TeamOutlined,
  SafetyCertificateOutlined,
  EditOutlined,
} from "@ant-design/icons";
import { useAuth } from "@/contexts/AuthContext";
import FloatingChat from "@/components/common/FloatingChat";
import { stripAppBase } from "@/utils/platform";

const { Header, Sider, Content } = Layout;

const MENU_MAP: Record<string, string> = {
  "/dashboard": "menu:dashboard",
  "/enterprises": "menu:enterprises",
  "/plans": "menu:plans",
  "/settings/users": "menu:users",
  "/settings/roles": "menu:roles",
  "/settings/system": "menu:system_config",
  "/settings/prompts": "menu:prompts",
  "/settings/profile": "menu:profile",
  "/settings/ai-config": "menu:ai_config",
  "/settings/regulations": "menu:regulations",
};

const getStoredProMode = () => {
  try {
    return localStorage.getItem("pro_mode") === "1";
  } catch {
    return false;
  }
};

const setStoredProMode = (v: boolean) => {
  try {
    localStorage.setItem("pro_mode", v ? "1" : "0");
  } catch {
    /* 存储不可用时忽略 */
  }
};

export function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [proMode, setProMode] = useState(getStoredProMode);
  const togglePro = () => {
    const next = !proMode;
    setProMode(next);
    setStoredProMode(next);
  };
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout, menuPermissions, menuLoadFailed } = useAuth();
  const { token: themeToken } = theme.useToken();

  const hasMenu = (path: string) => menuPermissions.includes(MENU_MAP[path] ?? "");

  const showSystemGroup = hasMenu("/settings/users") || hasMenu("/settings/roles") || hasMenu("/settings/system");
  const showAIGroup = hasMenu("/settings/prompts");

  const settingsChildren = [
    ...(hasMenu("/settings/profile") ? [{ key: "/settings/profile", icon: <UserOutlined />, label: "个人资料" }] : []),
    ...(hasMenu("/settings/ai-config") ? [{ key: "/settings/ai-config", icon: <KeyOutlined />, label: "AI 配置" }] : []),
    ...(proMode && hasMenu("/settings/regulations") ? [{ key: "/settings/regulations", icon: <FileTextOutlined />, label: "法规库管理" }] : []),
  ];

  const menuItems = [
    ...(hasMenu("/dashboard") ? [{ key: "/dashboard", icon: <DashboardOutlined />, label: "工作台" }] : []),
    ...(hasMenu("/enterprises") ? [{ key: "/enterprises", icon: <BankOutlined />, label: "企业管理" }] : []),
    ...(hasMenu("/plans") ? [{ key: "/plans", icon: <FileTextOutlined />, label: "预案列表" }] : []),
    { type: "divider" as const },
    ...(proMode && showSystemGroup
      ? [{
          key: "system-group",
          label: "系统管理",
          children: [
            ...(hasMenu("/settings/users") ? [{ key: "/settings/users", icon: <TeamOutlined />, label: "用户管理" }] : []),
            ...(hasMenu("/settings/roles") ? [{ key: "/settings/roles", icon: <SafetyCertificateOutlined />, label: "角色管理" }] : []),
            ...(hasMenu("/settings/system") ? [{ key: "/settings/system", icon: <SettingOutlined />, label: "系统配置" }] : []),
          ],
        }]
      : []),
    ...(proMode && showAIGroup
      ? [{
          key: "ai-group",
          label: "AI 管理",
          children: [
            ...(hasMenu("/settings/prompts") ? [{ key: "/settings/prompts", icon: <EditOutlined />, label: "提示词管理" }] : []),
          ],
        }]
      : []),
    { type: "divider" as const },
    ...(settingsChildren.length > 0
      ? [{
          key: "settings",
          icon: <SettingOutlined />,
          label: "设置",
          children: settingsChildren,
        }]
      : []),
  ];

  const userMenuItems = [
    ...(hasMenu("/settings/profile") ? [{ key: "profile", icon: <UserOutlined />, label: "个人资料", onClick: () => navigate("/settings/profile") }] : []),
    ...(hasMenu("/settings/ai-config") ? [{ key: "ai-config", icon: <KeyOutlined />, label: "AI 配置", onClick: () => navigate("/settings/ai-config") }] : []),
    { type: "divider" as const },
    { key: "logout", icon: <LogoutOutlined />, label: "退出登录", onClick: logout },
  ];

  const defaultOpenKeys = useMemo(() => {
    const keys: string[] = [];
    if (proMode && showSystemGroup) keys.push("system-group");
    if (proMode && showAIGroup) keys.push("ai-group");
    if (settingsChildren.length > 0) keys.push("settings");
    return keys;
  }, [proMode, showSystemGroup, showAIGroup, settingsChildren.length]);

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        theme="light"
        style={{
          borderRight: `1px solid ${themeToken.colorBorderSecondary}`,
        }}
      >
        <div
          style={{
            height: 64,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            borderBottom: `1px solid ${themeToken.colorBorderSecondary}`,
          }}
        >
          <span style={{ fontWeight: 700, fontSize: collapsed ? 16 : 18, whiteSpace: "nowrap" }}>
            {collapsed ? "预案" : "数字化预案系统"}
          </span>
        </div>
        <Menu
          key={proMode ? "pro" : "basic"}
          mode="inline"
          selectedKeys={[stripAppBase(location.pathname)]}
          defaultOpenKeys={defaultOpenKeys}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ borderInlineEnd: "none" }}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            padding: "0 24px",
            background: "#fff",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: `1px solid ${themeToken.colorBorderSecondary}`,
          }}
        >
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
          />
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            {(showSystemGroup || showAIGroup || hasMenu("/settings/regulations")) && (
              <Button size="small" onClick={togglePro}>
                {proMode ? "专业模式 开" : "专业模式 关"}
              </Button>
            )}
            <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
              <div style={{ cursor: "pointer", display: "flex", alignItems: "center", gap: 8 }}>
                <Avatar size="small" icon={<UserOutlined />} />
                <span>{user?.name || "用户"}</span>
              </div>
            </Dropdown>
          </div>
        </Header>
        <Content
          style={{
            margin: 24,
            padding: 24,
            background: "#fff",
            borderRadius: 8,
            minHeight: 280,
            overflow: "auto",
          }}
        >
          {menuLoadFailed && (
            <Alert
              type="warning"
              showIcon
              closable
              message="部分菜单加载失败，已显示核心菜单"
              style={{ marginBottom: 16 }}
            />
          )}
          <Outlet />
        </Content>
      </Layout>
      <FloatingChat />
    </Layout>
  );
}
