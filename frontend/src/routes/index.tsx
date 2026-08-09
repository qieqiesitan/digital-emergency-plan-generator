import { createBrowserRouter, Navigate } from "react-router-dom";
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
import RiskAssessmentPreview from "@/pages/Enterprise/RiskAssessmentPreview";
import ResourceInvestigationPreview from "@/pages/Enterprise/ResourceInvestigationPreview";
import RiskOverviewPage from "@/pages/Enterprise/RiskOverviewPage";
import RiskMethodListPage from "@/pages/Enterprise/RiskMethodListPage";
import RiskMethodEditorPage from "@/pages/Enterprise/RiskMethodEditorPage";
import RiskMappingWorkbenchPage from "@/pages/Enterprise/RiskMappingWorkbenchPage";
import ChatPage from "@/pages/Chat";
import OnboardingPage from "@/pages/Onboarding/OnboardingPage";

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
  { path: "/plans", element: <PlanCardsPage /> },
  { path: "/plans/all", element: <PlanListPage /> },
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
    { path: "/m/*", element: <MobileRedirect /> },
    { path: "*", element: <Navigate to="/dashboard" replace /> },
  ]);
}
