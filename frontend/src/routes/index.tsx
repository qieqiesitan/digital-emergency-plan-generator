import { createBrowserRouter, Navigate } from "react-router-dom";
import { APP_BASE } from "@/utils/platform";
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
import UserManagePage from "@/pages/Settings/UserManagePage";
import RoleManagePage from "@/pages/Settings/RoleManagePage";
import SystemConfigPage from "@/pages/Settings/SystemConfigPage";
import RegulationManagePage from "@/pages/Settings/RegulationManagePage";
import DataDictManagePage from "@/pages/Settings/DataDictManagePage";
import RiskAssessmentPreview from "@/pages/Enterprise/RiskAssessmentPreview";
import ResourceInvestigationPreview from "@/pages/Enterprise/ResourceInvestigationPreview";
import RiskOverviewPage from "@/pages/Enterprise/RiskOverviewPage";
import RiskMethodListPage from "@/pages/Enterprise/RiskMethodListPage";
import RiskMethodEditorPage from "@/pages/Enterprise/RiskMethodEditorPage";
import RiskMappingWorkbenchPage from "@/pages/Enterprise/RiskMappingWorkbenchPage";
import RiskNoticeCardPage from "@/pages/Enterprise/RiskNoticeCardPage";
import RiskNoticeCardPreviewPage from "@/pages/Enterprise/RiskNoticeCardPreviewPage";
import RiskControlListPage from "@/pages/Enterprise/RiskControlListPage";
import RiskPublicityPage from "@/pages/Enterprise/RiskPublicityPage";
import EnterpriseDictConfigPage from "@/pages/Enterprise/EnterpriseDictConfigPage";
import EnterpriseOrgPage from "@/pages/Enterprise/EnterpriseOrgPage";
import PublicRiskNoticePage from "@/pages/PublicRiskNoticePage";
import PublicRiskPage from "@/pages/PublicRiskPage";
import HazardPlanPage from "@/pages/Hazard/HazardPlanPage";
import HazardTaskPage from "@/pages/Hazard/HazardTaskPage";
import HazardRecordDetailPage from "@/pages/Hazard/HazardRecordDetailPage";
import HazardDashboardPage from "@/pages/Hazard/HazardDashboardPage";
import HazardTemplatePage from "@/pages/Hazard/HazardTemplatePage";
import HazardPublicityPage from "@/pages/Hazard/HazardPublicityPage";
import PublicHazardReportPage from "@/pages/Hazard/PublicHazardReportPage";
import PublicHazardPage from "@/pages/Hazard/PublicHazardPage";
import ChatPage from "@/pages/Chat";
import OnboardingPage from "@/pages/Onboarding/OnboardingPage";

// eslint-disable-next-line react-refresh/only-export-components -- 本文件同时导出 createRouter 工厂，属既有结构
function MobileRedirect() {
  window.location.replace(window.location.pathname + window.location.search);
  return null;
}

const contentRoutes = [
  { index: true, element: <Navigate to="/dashboard" replace /> },
  { path: "/dashboard", element: <DashboardPage /> },
  { path: "/chat", element: <ChatPage /> },
  { path: "/onboarding", element: <OnboardingPage /> },
  { path: "/enterprises", element: <EnterpriseListPage /> },
  { path: "/enterprises/new", element: <EnterpriseCreatePage /> },
  { path: "/enterprises/:id", element: <EnterpriseDetailPage /> },
  { path: "/enterprises/:id/edit", element: <EnterpriseEditPage /> },
  { path: "/enterprises/:id/risk-assessment/preview", element: <RiskAssessmentPreview /> },
  { path: "/enterprises/:id/resource-investigation/preview", element: <ResourceInvestigationPreview /> },
  { path: "/enterprises/:id/risk-overview", element: <RiskOverviewPage /> },
  { path: "/enterprises/:id/risk-methods", element: <RiskMethodListPage /> },
  { path: "/enterprises/:id/risk-methods/:methodId", element: <RiskMethodEditorPage /> },
  { path: "/enterprises/:id/risk-mapping-workbench", element: <RiskMappingWorkbenchPage /> },
  { path: "/enterprises/:id/risk-notice-cards", element: <RiskNoticeCardPage /> },
  { path: "/enterprises/:id/risk-notice-cards/:objectId", element: <RiskNoticeCardPreviewPage /> },
  { path: "/enterprises/:id/risk-control-list", element: <RiskControlListPage /> },
  { path: "/enterprises/:id/risk-publicity", element: <RiskPublicityPage /> },
  { path: "/enterprises/:id/org", element: <EnterpriseOrgPage /> },
  // 隐患模块路由组（任务 14-16 已全部替换为真实页面）
  { path: "/enterprises/:id/hazard/plans", element: <HazardPlanPage /> },
  { path: "/enterprises/:id/hazard/tasks", element: <HazardTaskPage /> },
  { path: "/enterprises/:id/hazard/records/:rid", element: <HazardRecordDetailPage /> },
  { path: "/enterprises/:id/hazard/templates", element: <HazardTemplatePage /> },
  { path: "/enterprises/:id/hazard/dashboard", element: <HazardDashboardPage /> },
  { path: "/enterprises/:id/hazard/publicity", element: <HazardPublicityPage /> },
  { path: "/plans", element: <PlanCardsPage /> },
  { path: "/enterprises/:enterprise_id/plans", element: <PlanListPage /> },
  { path: "/plans/new", element: <PlanCreatePage /> },
  { path: "/plans/:id/edit", element: <PlanEditorPage /> },
  { path: "/plans/:id/versions", element: <VersionListPage /> },
  { path: "/plans/:id/preview", element: <ExportPreviewPage /> },
  { path: "/settings/profile", element: <ProfilePage /> },
  { path: "/settings/ai-config", element: <AIConfigPage /> },
  { path: "/settings/users", element: <UserManagePage /> },
  { path: "/settings/roles", element: <RoleManagePage /> },
  { path: "/settings/system", element: <SystemConfigPage /> },
  { path: "/settings/prompts", element: <PromptManagePage /> },
  { path: "/settings/regulations", element: <RegulationManagePage /> },
  { path: "/settings/data-dicts", element: <DataDictManagePage /> },
  { path: "/enterprises/:id/data-dicts", element: <EnterpriseDictConfigPage /> },
];

export function createRouter() {
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
    // 公开只读页：无登录守卫（token 无效由后端返回 404）
    { path: "/r/:token", element: <PublicRiskNoticePage /> },
    { path: "/p/risk/:token", element: <PublicRiskPage /> },
    // 隐患公开页（§15：公开公示 /h/:token、扫码上报 /h/report/:token，均免登录）
    { path: "/h/report/:token", element: <PublicHazardReportPage /> },
    { path: "/h/:token", element: <PublicHazardPage /> },
    { path: "/m/*", element: <MobileRedirect /> },
    { path: "*", element: <Navigate to="/dashboard" replace /> },
  ], { basename: APP_BASE || undefined });
}
