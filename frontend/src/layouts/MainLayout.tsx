import { useState, useMemo } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Layout, Menu, Button, Dropdown, Avatar, theme } from "antd";
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
import { EnterpriseSwitcher } from "@/components/enterprise/EnterpriseSwitcher";

const { Header, Sider, Content } = Layout;

// ponytail: menu path -> permission code mapping
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

export function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout, menuPermissions } = useAuth();
  const { token: themeToken } = theme.useToken();

  const hasMenu = (path: string) => menuPermissions.includes(MENU_MAP[path] ?? "");

  // ponytail: derive groups from menu permissions
  const showSystemGroup = hasMenu("/settings/users") || hasMenu("/settings/roles") || hasMenu("/settings/system");
  const showAIGroup = hasMenu("/settings/prompts");

  const menuItems = [
    ...(hasMenu("/dashboard") ? [{ key: "/dashboard", icon: <DashboardOutlined />, label: "工作台" }] : []),
    ...(hasMenu("/enterprises") ? [{ key: "/enterprises", icon: <BankOutlined />, label: "企业管理" }] : []),
    ...(hasMenu("/plans") ? [{ key: "/plans", icon: <FileTextOutlined />, label: "预案列表" }] : []),
    { type: "divider" as const },
    ...(showSystemGroup
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
    ...(showAIGroup
      ? [{
          key: "ai-group",
          label: "AI 管理",
          children: [
            ...(hasMenu("/settings/prompts") ? [{ key: "/settings/prompts", icon: <EditOutlined />, label: "提示词管理" }] : []),
          ],
        }]
      : []),
    { type: "divider" as const },
    {
      key: "settings",
      icon: <SettingOutlined />,
      label: "设置",
      children: [
        ...(hasMenu("/settings/profile") ? [{ key: "/settings/profile", icon: <UserOutlined />, label: "个人资料" }] : []),
        ...(hasMenu("/settings/ai-config") ? [{ key: "/settings/ai-config", icon: <KeyOutlined />, label: "AI 配置" }] : []),
        { key: "/settings/regulations", icon: <FileTextOutlined />, label: "法规库管理" },
      ],
    },
  ];

  const userMenuItems = [
    ...(hasMenu("/settings/profile") ? [{ key: "profile", icon: <UserOutlined />, label: "个人资料", onClick: () => navigate("/settings/profile") }] : []),
    ...(hasMenu("/settings/ai-config") ? [{ key: "ai-config", icon: <KeyOutlined />, label: "AI 配置", onClick: () => navigate("/settings/ai-config") }] : []),
    { type: "divider" as const },
    { key: "logout", icon: <LogoutOutlined />, label: "退出登录", onClick: logout },
  ];

  const defaultOpenKeys = useMemo(() => {
    const keys: string[] = [];
    if (showSystemGroup) keys.push("system-group");
    if (showAIGroup) keys.push("ai-group");
    keys.push("settings");
    return keys;
  }, [showSystemGroup, showAIGroup]);

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
          mode="inline"
          selectedKeys={[location.pathname]}
          defaultOpenKeys={defaultOpenKeys}
          items={menuItems}
          onClick={({ key }) => {
            const externalUrls = {
            };
            if (key in externalUrls) {
              window.open(externalUrls[key as keyof typeof externalUrls], "_blank");
            } else {
              navigate(key);
            }
          }}
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
            <EnterpriseSwitcher />
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
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
