import React, { useEffect, useCallback } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import TabBar from "@/mobile/components/ui/TabBar";
import NetworkStatusBanner from "@/mobile/components/ui/NetworkStatusBanner";
import { ErrorBoundary } from "@/mobile/components/ui/ErrorBoundary";
import { useAppStore } from "@/mobile/store/appStore";
import {
  LayoutDashboard,
  Building2,
  FileText,
  Settings,
} from "lucide-react";

// Tab 路由匹配规则
const TAB_PATTERNS: Record<string, RegExp> = {
  dashboard: /^\/m(\/dashboard)?$/,
  enterprises: /^\/m\/enterprises/,
  plans: /^\/m\/plans/,
  settings: /^\/m\/settings/,
};

const TAB_ROUTES: Record<string, string> = {
  dashboard: "/m/dashboard",
  enterprises: "/m/enterprises",
  plans: "/m/plans",
  settings: "/m/settings",
};

// 判断哪些路由应该隐藏 TabBar
const HIDE_TABBAR_PATTERNS = [/^\/m\/login$/, /^\/m\/register$/, /^\/m\/splash$/];

function shouldHideTabBar(pathname: string): boolean {
  return HIDE_TABBAR_PATTERNS.some((p) => p.test(pathname));
}

const TAB_ITEMS = [
  { key: "dashboard", icon: <LayoutDashboard size={24} />, label: "工作台" },
  { key: "enterprises", icon: <Building2 size={24} />, label: "企业" },
  { key: "plans", icon: <FileText size={24} />, label: "预案" },
  { key: "settings", icon: <Settings size={24} />, label: "设置" },
];

// 页面转场动画
const pageVariants = {
  initial: { opacity: 0, x: 20 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -20 },
};

export default function MainTabsLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { activeTab, setActiveTab } = useAppStore();
  const hideTabBar = shouldHideTabBar(location.pathname);

  // 根据路由自动更新 activeTab
  useEffect(() => {
    for (const [tab, pattern] of Object.entries(TAB_PATTERNS)) {
      if (pattern.test(location.pathname)) {
        if (activeTab !== tab) {
          setActiveTab(tab as typeof activeTab);
        }
        break;
      }
    }
  }, [location.pathname, setActiveTab, activeTab]);

  // Tab 点击 → 路由跳转
  const handleTabChange = useCallback((key: string) => {
    setActiveTab(key as typeof activeTab);
    navigate(TAB_ROUTES[key] || "/m/dashboard");
  }, [navigate, setActiveTab, activeTab]);

  return (
    <ErrorBoundary>
      <div className="flex flex-col h-dvh bg-neutral-50">
        <NetworkStatusBanner />
        <main
          className="flex-1 overflow-y-auto"
          style={{ paddingBottom: hideTabBar ? 0 : "var(--tabbar-height)" }}
        >
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              variants={pageVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              transition={{ duration: 0.2, ease: "easeOut" }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
        {!hideTabBar && (
          <TabBar
            items={TAB_ITEMS}
            activeKey={activeTab}
            onChange={handleTabChange}
          />
        )}
      </div>
    </ErrorBoundary>
  );
}
