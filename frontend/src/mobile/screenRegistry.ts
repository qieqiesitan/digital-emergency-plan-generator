/**
 * 移动端页面注册表：集中声明全部懒加载 Screen。
 *
 * 背景：React Fast Refresh 只支持“一个文件只导出组件”。路由表 `routes.tsx` 只导出
 * `mobileRouter`（非组件），却在该文件内声明 22 个 lazy 组件，会触发
 * `react-refresh/only-export-components`。把懒加载声明拆到本文件后：
 * routes.tsx 只剩纯路由配置；页面清单也集中在一处，便于核对导航完整性。
 */
import { lazy } from "react";

export const SplashScreen = lazy(() => import("@/mobile/screens/SplashScreen"));
export const LoginScreen = lazy(() => import("@/mobile/screens/LoginScreen"));
export const RegisterScreen = lazy(() => import("@/mobile/screens/RegisterScreen"));
export const DashboardScreen = lazy(() => import("@/mobile/screens/DashboardScreen"));
export const EnterpriseListScreen = lazy(() => import("@/mobile/screens/EnterpriseListScreen"));
export const EnterpriseCreateScreen = lazy(() => import("@/mobile/screens/EnterpriseCreateScreen"));
export const EnterpriseDetailScreen = lazy(() => import("@/mobile/screens/EnterpriseDetailScreen"));
export const EnterpriseEditScreen = lazy(() => import("@/mobile/screens/EnterpriseEditScreen"));
export const RiskManagementListScreen = lazy(() => import("@/mobile/screens/RiskManagementListScreen"));
export const ResourceListScreen = lazy(() => import("@/mobile/screens/ResourceListScreen"));
export const RiskAssessmentScreen = lazy(() => import("@/mobile/screens/RiskAssessmentScreen"));
export const ResourceInvestigationScreen = lazy(() => import("@/mobile/screens/ResourceInvestigationScreen"));
export const PlanCardsScreen = lazy(() => import("@/mobile/screens/PlanCardsScreen"));
export const EnterprisePlanListScreen = lazy(() => import("@/mobile/screens/EnterprisePlanListScreen"));
export const PlanCreateScreen = lazy(() => import("@/mobile/screens/PlanCreateScreen"));
export const PlanEditorScreen = lazy(() => import("@/mobile/screens/PlanEditorScreen"));
export const ExportPreviewScreen = lazy(() => import("@/mobile/screens/ExportPreviewScreen"));
export const VersionListScreen = lazy(() => import("@/mobile/screens/VersionListScreen"));
export const SettingsScreen = lazy(() => import("@/mobile/screens/SettingsScreen"));
export const ProfileScreen = lazy(() => import("@/mobile/screens/ProfileScreen"));
export const ChangePasswordScreen = lazy(() => import("@/mobile/screens/ChangePasswordScreen"));
export const ChatScreen = lazy(() => import("@/mobile/screens/ChatScreen"));
