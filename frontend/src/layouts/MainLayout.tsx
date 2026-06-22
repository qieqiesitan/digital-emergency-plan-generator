import { useState } from "react";
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
  BookOutlined,
  MenuOutlined,
  EditOutlined,
  ApiOutlined,
  RobotOutlined,
} from "@ant-design/icons";
import { useAuth } from "@/contexts/AuthContext";
import { EnterpriseSwitcher } from "@/components/enterprise/EnterpriseSwitcher";

const { Header, Sider, Content } = Layout;

export function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { token: themeToken } = theme.useToken();

  const menuItems = [
    {
      key: "/dashboard",
      icon: <DashboardOutlined />,
      label: "工作台",
    },
    {
      key: "/enterprises",
      icon: <BankOutlined />,
      label: "企业管理",
    },
    {
      key: "/plans",
      icon: <FileTextOutlined />,
      label: "预案列表",
    },
    {
      type: "divider" as const,
    },
    {
      key: "system-group",
      label: "系统管理",
      children: [
        {
          key: "/system/dicts",
          icon: <BookOutlined />,
          label: "字典管理",
        },
        {
          key: "/system/menus",
          icon: <MenuOutlined />,
          label: "菜单管理",
        },
        {
          key: "/settings/system",
          icon: <SettingOutlined />,
          label: "系统配置",
        },
      ],
    },
    {
      key: "ai-group",
      label: "AI 管理",
      children: [
        {
          key: "/settings/prompts",
          icon: <EditOutlined />,
          label: "提示词管理",
        },
        {
          key: "/ai/provider",
          icon: <ApiOutlined />,
          label: "供应商管理",
        },
        {
          key: "/ai/model",
          icon: <RobotOutlined />,
          label: "模型管理",
        },
      ],
    },
    {
      type: "divider" as const,
    },
    {
      key: "settings",
      icon: <SettingOutlined />,
      label: "设置",
      children: [
        {
          key: "/settings/profile",
          icon: <UserOutlined />,
          label: "个人资料",
        },
        {
          key: "/settings/ai-config",
          icon: <KeyOutlined />,
          label: "AI 配置",
        },
      ],
    },
  ];

  const userMenuItems = [
    {
      key: "profile",
      icon: <UserOutlined />,
      label: "个人资料",
      onClick: () => navigate("/settings/profile"),
    },
    {
      key: "ai-config",
      icon: <KeyOutlined />,
      label: "AI 配置",
      onClick: () => navigate("/settings/ai-config"),
    },
    { type: "divider" as const },
    {
      key: "logout",
      icon: <LogoutOutlined />,
      label: "退出登录",
      onClick: logout,
    },
  ];

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
          defaultOpenKeys={["settings", "system-group", "ai-group"]}
          items={menuItems}
          onClick={({ key }) => {
            const externalUrls = {
              "/system/dicts": "http://localhost/system/dict",
              "/system/menus": "http://localhost/system/menu",
              "/ai/provider": "http://localhost/ai/provider",
              "/ai/model": "http://localhost/ai/model",
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
