import { useEffect, useMemo, useState } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { Layout, Menu, Button, Dropdown, Avatar, theme, Alert } from "antd";
import {
  SettingOutlined,
  UserOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  KeyOutlined,
  TeamOutlined,
  SafetyCertificateOutlined,
  DashboardOutlined,
  AppstoreOutlined,
  FileTextOutlined,
  RobotOutlined,
  BookOutlined,
  DatabaseOutlined,
  FileProtectOutlined,
  GlobalOutlined,
} from "@ant-design/icons";
import { useAuth } from "@/contexts/AuthContext";
import FloatingChat from "@/components/common/FloatingChat";
import { stripAppBase } from "@/utils/platform";
import { MENU_MAP } from "@/utils/menuMap";
import { getPageMeta } from "@/routing/pageMeta";

const { Header, Sider, Content } = Layout;

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
  const appPath = stripAppBase(location.pathname);
  const { user, logout, menuPermissions, menuLoadFailed } = useAuth();
  const { token: themeToken } = theme.useToken();

  // 页面标题 + 菜单高亮：动态路径（企业/预案详情等）由元数据规则推导，不再字符串精确匹配
  useEffect(() => {
    const meta = getPageMeta(appPath);
    document.title = meta.title ? `${meta.title} - 数字化预案系统` : "数字化预案系统";
  }, [appPath]);

  // 路由切换后回到页面顶部，避免长列表底部切页后停留在旧滚动位置
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    document.getElementById("app-content")?.scrollTo({ top: 0 });
  }, [location.pathname]);

  const selectedMenuKeys = useMemo(() => {
    const menuKey = getPageMeta(appPath).menuKey;
    return menuKey ? [menuKey] : [];
  }, [appPath]);

  const hasMenu = (path: string) => menuPermissions.includes(MENU_MAP[path] ?? "");

  const showSystemGroup =
    hasMenu("/settings/users") ||
    hasMenu("/settings/roles") ||
    hasMenu("/settings/system") ||
    hasMenu("/settings/data-dicts") ||
    hasMenu("/settings/chemical-library");
  const showAIGroup = hasMenu("/settings/prompts");

  const settingsChildren = [
    ...(hasMenu("/settings/profile") ? [{ key: "/settings/profile", icon: <UserOutlined />, label: "个人资料" }] : []),
    ...(hasMenu("/settings/ai-config") ? [{ key: "/settings/ai-config", icon: <RobotOutlined />, label: "AI 配置" }] : []),
    ...(hasMenu("/settings/third-party-config") ? [{ key: "/settings/third-party-config", icon: <GlobalOutlined />, label: "第三方接口配置" }] : []),
    ...(proMode && hasMenu("/settings/regulations") ? [{ key: "/settings/regulations", icon: <BookOutlined />, label: "法规库管理" }] : []),
  ];

  const menuItems = [
    ...(hasMenu("/dashboard") ? [{ key: "/dashboard", icon: <DashboardOutlined />, label: "工作台" }] : []),
    ...(hasMenu("/enterprises") ? [{ key: "/enterprises", icon: <AppstoreOutlined />, label: "企业管理" }] : []),
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
            ...(hasMenu("/settings/data-dicts") ? [{ key: "/settings/data-dicts", icon: <DatabaseOutlined />, label: "数据字典管理" }] : []),
            ...(hasMenu("/settings/chemical-library") ? [{ key: "/settings/chemical-library", icon: <DatabaseOutlined />, label: "化学品库管理" }] : []),
          ],
        }]
      : []),
    ...(proMode && showAIGroup
      ? [{
          key: "ai-group",
          label: "AI 管理",
          children: [
            ...(hasMenu("/settings/prompts") ? [{ key: "/settings/prompts", icon: <FileProtectOutlined />, label: "提示词管理" }] : []),
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
    ...(hasMenu("/settings/third-party-config") ? [{ key: "third-party-config", icon: <GlobalOutlined />, label: "第三方接口配置", onClick: () => navigate("/settings/third-party-config") }] : []),
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
          selectedKeys={selectedMenuKeys}
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
          id="app-content"
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
