import { createBrowserRouter, Navigate } from "react-router-dom";
import { APP_BASE } from "@/utils/platform";
import { AuthGuard } from "@/mobile/components/auth/AuthGuard";
import MainTabsLayout from "@/mobile/layouts/MainTabsLayout";
import {
  SplashScreen,
  LoginScreen,
  RegisterScreen,
  DashboardScreen,
  EnterpriseListScreen,
  EnterpriseCreateScreen,
  EnterpriseDetailScreen,
  EnterpriseEditScreen,
  RiskManagementListScreen,
  ResourceListScreen,
  RiskAssessmentScreen,
  ResourceInvestigationScreen,
  PlanCardsScreen,
  EnterprisePlanListScreen,
  PlanCreateScreen,
  PlanEditorScreen,
  ExportPreviewScreen,
  VersionListScreen,
  SettingsScreen,
  ProfileScreen,
  ChangePasswordScreen,
  ChatScreen,
} from "@/mobile/screenRegistry";

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
      { path: "chat", element: <ChatScreen /> },
    ],
  },

  // 兜底
  { path: "*", element: <Navigate to="/m/dashboard" replace /> },
], { basename: APP_BASE || undefined });
