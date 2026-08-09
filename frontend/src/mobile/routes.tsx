import { createBrowserRouter, Navigate } from "react-router-dom";
import { AuthGuard } from "@/mobile/components/auth/AuthGuard";
import MainTabsLayout from "@/mobile/layouts/MainTabsLayout";
import { lazy } from "react";

// 懒加载所有 Screen
const SplashScreen = lazy(() => import("@/mobile/screens/SplashScreen"));
const LoginScreen = lazy(() => import("@/mobile/screens/LoginScreen"));
const RegisterScreen = lazy(() => import("@/mobile/screens/RegisterScreen"));
const DashboardScreen = lazy(() => import("@/mobile/screens/DashboardScreen"));
const EnterpriseListScreen = lazy(() => import("@/mobile/screens/EnterpriseListScreen"));
const EnterpriseCreateScreen = lazy(() => import("@/mobile/screens/EnterpriseCreateScreen"));
const EnterpriseDetailScreen = lazy(() => import("@/mobile/screens/EnterpriseDetailScreen"));
const EnterpriseEditScreen = lazy(() => import("@/mobile/screens/EnterpriseEditScreen"));
const RiskManagementListScreen = lazy(() => import("@/mobile/screens/RiskManagementListScreen"));
const ResourceListScreen = lazy(() => import("@/mobile/screens/ResourceListScreen"));
const RiskAssessmentScreen = lazy(() => import("@/mobile/screens/RiskAssessmentScreen"));
const ResourceInvestigationScreen = lazy(() => import("@/mobile/screens/ResourceInvestigationScreen"));
const PlanCardsScreen = lazy(() => import("@/mobile/screens/PlanCardsScreen"));
const EnterprisePlanListScreen = lazy(() => import("@/mobile/screens/EnterprisePlanListScreen"));
const PlanCreateScreen = lazy(() => import("@/mobile/screens/PlanCreateScreen"));
const PlanEditorScreen = lazy(() => import("@/mobile/screens/PlanEditorScreen"));
const ExportPreviewScreen = lazy(() => import("@/mobile/screens/ExportPreviewScreen"));
const VersionListScreen = lazy(() => import("@/mobile/screens/VersionListScreen"));
const SettingsScreen = lazy(() => import("@/mobile/screens/SettingsScreen"));
const ProfileScreen = lazy(() => import("@/mobile/screens/ProfileScreen"));
const ChangePasswordScreen = lazy(() => import("@/mobile/screens/ChangePasswordScreen"));
const AIModelConfigScreen = lazy(() => import("@/mobile/screens/AIModelConfigScreen"));
const ChatScreen = lazy(() => import("@/mobile/screens/ChatScreen"));

export const mobileRouter = createBrowserRouter([
  // 启动屏
  { path: "/m/splash", element: <SplashScreen /> },

  // 认证（无需登录）
  { path: "/m/login", element: <LoginScreen /> },
  { path: "/m/register", element: <RegisterScreen /> },

  // 主应用（需登录）
  {
    path: "/m",
    element: (
      <AuthGuard>
        <MainTabsLayout />
      </AuthGuard>
    ),
    children: [
      { index: true, element: <DashboardScreen /> },
      { path: "dashboard", element: <DashboardScreen /> },

      // 企业
      { path: "enterprises", element: <EnterpriseListScreen /> },
      { path: "enterprises/new", element: <EnterpriseCreateScreen /> },
      { path: "enterprises/:id", element: <EnterpriseDetailScreen /> },
      { path: "enterprises/:id/edit", element: <EnterpriseEditScreen /> },
      { path: "enterprises/:id/risk-management", element: <RiskManagementListScreen /> },
      { path: "enterprises/:id/resources", element: <ResourceListScreen /> },
      { path: "enterprises/:id/risk-assessment", element: <RiskAssessmentScreen /> },
      { path: "enterprises/:id/resource-investigation", element: <ResourceInvestigationScreen /> },
      { path: "enterprises/:id/plans", element: <EnterprisePlanListScreen /> },

      // 预案
      { path: "plans", element: <PlanCardsScreen /> },
      { path: "plans/new", element: <PlanCreateScreen /> },
      { path: "plans/:id/edit", element: <PlanEditorScreen /> },
      { path: "plans/:id/versions", element: <VersionListScreen /> },
      { path: "plans/:id/preview", element: <ExportPreviewScreen /> },

      // 设置
      { path: "settings", element: <SettingsScreen /> },
      { path: "settings/profile", element: <ProfileScreen /> },
      { path: "settings/password", element: <ChangePasswordScreen /> },
      { path: "settings/ai-config", element: <AIModelConfigScreen /> },
      { path: "chat", element: <ChatScreen /> },
    ],
  },

  // 兜底
  { path: "*", element: <Navigate to="/m/dashboard" replace /> },
]);
