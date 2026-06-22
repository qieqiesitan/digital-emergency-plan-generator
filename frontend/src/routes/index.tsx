import { createBrowserRouter, Navigate, Outlet } from "react-router-dom";
import { AuthLayout } from "@/layouts/AuthLayout";
import { MainLayout } from "@/layouts/MainLayout";
import { ProtectedRoute } from "./ProtectedRoute";
import LoginPage from "@/pages/Login/LoginPage";
import RegisterPage from "@/pages/Register/RegisterPage";
import DashboardPage from "@/pages/Dashboard/DashboardPage";
import EnterpriseListPage from "@/pages/Enterprise/EnterpriseListPage";
import EnterpriseCreatePage from "@/pages/Enterprise/EnterpriseCreatePage";
import EnterpriseEditPage from "@/pages/Enterprise/EnterpriseEditPage";
import EnterpriseDetailPage from "@/pages/Enterprise/EnterpriseDetailPage";
import PlanCardsPage from "@/pages/Plan/PlanCardsPage";
import PlanListPage from "@/pages/Plan/PlanListPage";
import PlanCreatePage from "@/pages/Plan/PlanCreatePage";
import PlanEditorPage from "@/pages/Plan/PlanEditorPage";
import VersionListPage from "@/pages/Plan/VersionListPage";
import ExportPreviewPage from "@/pages/Plan/ExportPreviewPage";
import ProfilePage from "@/pages/Settings/ProfilePage";
import AIConfigPage from "@/pages/Settings/AIConfigPage";
import PromptManagePage from "@/pages/Settings/PromptManagePage";
import SystemConfigPage from "@/pages/Settings/SystemConfigPage";
import RiskAssessmentPreview from "@/pages/Enterprise/RiskAssessmentPreview";
import ResourceInvestigationPreview from "@/pages/Enterprise/ResourceInvestigationPreview";

// 桌面端 SPA 内收到 /m/* 路径时，强制整页重载
function MobileRedirect() {
  window.location.replace(window.location.pathname + window.location.search);
  return null;
}

// 中台 qiankun 模式下使用的简化布局（无侧栏/顶栏，仅内容区）
function QiankunContentLayout() {
  return (
    <div style={{ padding: 16, minHeight: "100%" }}>
      <Outlet />
    </div>
  );
}

// 共享的内容路由（两种模式共用）
const contentRoutes = [
  { index: true, element: <Navigate to="/dashboard" replace /> },
  { path: "/dashboard", element: <DashboardPage /> },
  { path: "/enterprises", element: <EnterpriseListPage /> },
  { path: "/enterprises/new", element: <EnterpriseCreatePage /> },
  { path: "/enterprises/:id", element: <EnterpriseDetailPage /> },
  { path: "/enterprises/:id/edit", element: <EnterpriseEditPage /> },
  { path: "/enterprises/:id/risk-assessment/preview", element: <RiskAssessmentPreview /> },
  { path: "/enterprises/:id/resource-investigation/preview", element: <ResourceInvestigationPreview /> },
  { path: "/plans", element: <PlanCardsPage /> },
  { path: "/enterprises/:enterprise_id/plans", element: <PlanListPage /> },
  { path: "/plans/new", element: <PlanCreatePage /> },
  { path: "/plans/:id/edit", element: <PlanEditorPage /> },
  { path: "/plans/:id/versions", element: <VersionListPage /> },
  { path: "/plans/:id/preview", element: <ExportPreviewPage /> },
  { path: "/settings/profile", element: <ProfilePage /> },
  { path: "/settings/ai-config", element: <AIConfigPage /> },
  { path: "/settings/system", element: <SystemConfigPage /> },
  { path: "/settings/prompts", element: <PromptManagePage /> },
];

export function createRouter(ywtMode: boolean) {
  if (ywtMode) {
    // 中台 qiankun 模式：无认证路由、无 ProtectedRoute、无 MainLayout
    return createBrowserRouter(
      [
        {
          element: <QiankunContentLayout />,
          children: contentRoutes,
        },
        { path: "*", element: <Navigate to="/dashboard" replace /> },
      ],
      { basename: "/emergency-plan" }
    );
  }

  // 独立模式：完整路由（认证 + MainLayout + 移动端）
  return createBrowserRouter([
    {
      element: <AuthLayout />,
      children: [
        { path: "/login", element: <LoginPage /> },
        { path: "/register", element: <RegisterPage /> },
      ],
    },
    {
      element: (
        <ProtectedRoute>
          <MainLayout />
        </ProtectedRoute>
      ),
      children: contentRoutes,
    },
    { path: "/m/*", element: <MobileRedirect /> },
    { path: "*", element: <Navigate to="/dashboard" replace /> },
  ]);
}
