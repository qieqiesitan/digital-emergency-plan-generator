import api from "./api";
import type { ApiResponse } from "@/types/common";
import type {
  HazardChecklistSuggestionResult,
  HazardChecklistTemplate,
  HazardChecklistTemplateAIResult,
  HazardChecklistTemplateCreate,
  HazardChecklistTemplateUpdate,
  HazardDashboardPayload,
  HazardGovernancePlanResult,
  HazardInspectionPlan,
  HazardInspectionPlanCreate,
  HazardInspectionPlanUpdate,
  HazardInspectionTask,
  HazardInspectionTaskDetail,
  HazardPlanBuilderResult,
  HazardPublicityItem,
  HazardPublicityTokenResult,
  HazardRecord,
  HazardRecordAssistResult,
  HazardRecordCreate,
  HazardRecordDetail,
  HazardRecordsResponse,
  HazardScheduleSuggestionResult,
  HazardSetupWizardResult,
  HazardTaskSubmitPayload,
  PublicHazardPublicityPayload,
  PublicHazardReportPayload,
  PublicHazardReportResult,
} from "@/types/hazard";

const BASE = (eid: string) => `/enterprises/${eid}/hazard-inspection`;

// ── 隐患记录：台账列表 / 详情 / 登记 / 状态机流转 ──

export const listRecords = (eid: string, params?: object) =>
  api.get<ApiResponse<HazardRecordsResponse>>(`${BASE(eid)}/records`, { params }).then(r => r.data.data);
export const getRecord = (eid: string, rid: string) =>
  api.get<ApiResponse<HazardRecordDetail>>(`${BASE(eid)}/records/${rid}`).then(r => r.data.data);
export const createRecord = (eid: string, data: HazardRecordCreate) =>
  api.post<ApiResponse<HazardRecord>>(`${BASE(eid)}/records`, data).then(r => r.data.data);

export const gradeRecord = (
  eid: string,
  rid: string,
  data: {
    level: string;
    grading_basis?: string | null;
    hazard_type?: string | null;
    rectification_plan?: Record<string, unknown> | null;
    rectification_user_id?: string | null;
    level_source?: "ai" | "manual";
  },
) => api.post<ApiResponse<HazardRecord>>(`${BASE(eid)}/records/${rid}/grade`, data).then(r => r.data.data);
export const approveRecord = (
  eid: string,
  rid: string,
  data?: { comment?: string | null; rectification_user_id?: string | null },
) => api.post<ApiResponse<HazardRecord>>(`${BASE(eid)}/records/${rid}/approve`, data ?? {}).then(r => r.data.data);
export const rejectRecord = (
  eid: string,
  rid: string,
  data?: { comment?: string | null },
) => api.post<ApiResponse<HazardRecord>>(`${BASE(eid)}/records/${rid}/reject`, data ?? {}).then(r => r.data.data);
export const rectifyRecord = (
  eid: string,
  rid: string,
  data: { content: string; evidence?: string[]; reviewer_user_id: string },
) => api.post<ApiResponse<HazardRecord>>(`${BASE(eid)}/records/${rid}/rectify`, data).then(r => r.data.data);
export const reviewRecord = (
  eid: string,
  rid: string,
  data: { result: "pass" | "fail"; comment?: string | null; evidence?: string[] },
) => api.post<ApiResponse<HazardRecord>>(`${BASE(eid)}/records/${rid}/review`, data).then(r => r.data.data);
export const closeRecord = (
  eid: string,
  rid: string,
  data?: { comment?: string | null },
) => api.post<ApiResponse<HazardRecord>>(`${BASE(eid)}/records/${rid}/close`, data ?? {}).then(r => r.data.data);

// ── 排查计划 CRUD ──

export const listHazardPlans = (eid: string) =>
  api.get<ApiResponse<HazardInspectionPlan[]>>(`${BASE(eid)}/plans`).then(r => r.data.data);
export const getHazardPlan = (eid: string, planId: string) =>
  api.get<ApiResponse<HazardInspectionPlan>>(`${BASE(eid)}/plans/${planId}`).then(r => r.data.data);
export const createHazardPlan = (eid: string, data: HazardInspectionPlanCreate) =>
  api.post<ApiResponse<HazardInspectionPlan>>(`${BASE(eid)}/plans`, data).then(r => r.data.data);
export const updateHazardPlan = (eid: string, planId: string, data: HazardInspectionPlanUpdate) =>
  api.put<ApiResponse<HazardInspectionPlan>>(`${BASE(eid)}/plans/${planId}`, data).then(r => r.data.data);
export const deleteHazardPlan = (eid: string, planId: string) =>
  api.delete(`${BASE(eid)}/plans/${planId}`);

// ── 排查任务：列表 / 详情 / 核对提交 / 一键转隐患 ──

export const listHazardTasks = (eid: string, params?: Record<string, unknown>) =>
  api.get<ApiResponse<HazardInspectionTask[]>>(`${BASE(eid)}/tasks`, { params }).then(r => r.data.data);
export const getHazardTask = (eid: string, taskId: string) =>
  api.get<ApiResponse<HazardInspectionTaskDetail>>(`${BASE(eid)}/tasks/${taskId}`).then(r => r.data.data);
export const submitHazardTask = (eid: string, taskId: string, data: HazardTaskSubmitPayload) =>
  api.put<ApiResponse<HazardInspectionTask>>(`${BASE(eid)}/tasks/${taskId}`, data).then(r => r.data.data);
export const taskToRecord = (
  eid: string,
  taskId: string,
  data: { item_id: string; title?: string | null; description?: string | null },
) => api.post<ApiResponse<HazardRecord>>(`${BASE(eid)}/tasks/${taskId}/to-record`, data).then(r => r.data.data);

// ── 检查表模板 CRUD / 复制 ──

export const listHazardTemplates = (eid: string) =>
  api.get<ApiResponse<HazardChecklistTemplate[]>>(`${BASE(eid)}/templates`).then(r => r.data.data);
export const createHazardTemplate = (eid: string, data: HazardChecklistTemplateCreate) =>
  api.post<ApiResponse<HazardChecklistTemplate>>(`${BASE(eid)}/templates`, data).then(r => r.data.data);
export const updateHazardTemplate = (eid: string, templateId: string, data: HazardChecklistTemplateUpdate) =>
  api.put<ApiResponse<HazardChecklistTemplate>>(`${BASE(eid)}/templates/${templateId}`, data).then(r => r.data.data);
export const copyHazardTemplate = (eid: string, templateId: string) =>
  api.post<ApiResponse<HazardChecklistTemplate>>(`${BASE(eid)}/templates/${templateId}/copy`).then(r => r.data.data);
export const deleteHazardTemplate = (eid: string, templateId: string) =>
  api.delete(`${BASE(eid)}/templates/${templateId}`);

// ── 隐患公示 / 驾驶舱 ──

export const getHazardPublicity = (eid: string, scope?: string) =>
  api.get<ApiResponse<HazardPublicityItem[]>>(`${BASE(eid)}/publicity`, { params: scope ? { scope } : {} }).then(r => r.data.data);
export const resetHazardPublicityToken = (eid: string) =>
  api.post<ApiResponse<HazardPublicityTokenResult>>(`${BASE(eid)}/publicity-token`).then(r => r.data.data);
export const getHazardDashboard = (eid: string) =>
  api.get<ApiResponse<HazardDashboardPayload>>(`${BASE(eid)}/dashboard`).then(r => r.data.data);

// ── 公开端点（免登录，§8 扫码上报 / §11.2 公示公开页） ──

export const submitPublicHazardReport = (token: string, data: PublicHazardReportPayload) =>
  api.post<ApiResponse<PublicHazardReportResult>>(`/public/hazard/report/${token}`, data).then(r => r.data.data);
export const fetchPublicHazard = (token: string, scope?: string) =>
  api.get<ApiResponse<PublicHazardPublicityPayload>>(`/public/hazard/${token}`, { params: scope ? { scope } : {} }).then(r => r.data.data);

// ── AI 辅助（失败均降级 available:false，§16） ──

export const aiRecordAssist = (eid: string, data: { description: string; object_id?: string | null; measure_id?: string | null }) =>
  api.post<ApiResponse<HazardRecordAssistResult>>(`${BASE(eid)}/ai/record-assist`, data).then(r => r.data.data);
export const aiGradeHazard = (eid: string, data: { description: string; judgment_points?: string | null; measures_text?: string | null }) =>
  api.post<ApiResponse<import("@/types/hazard").HazardAiGradeResult>>(`${BASE(eid)}/ai/grade`, data).then(r => r.data.data);
export const aiGovernancePlan = (eid: string, data: { description: string; judgment_points?: string | null; measures_text?: string | null }) =>
  api.post<ApiResponse<HazardGovernancePlanResult>>(`${BASE(eid)}/ai/governance-plan`, data).then(r => r.data.data);
export const aiPlanBuilder = (eid: string, data: { areas: string; frequency_preference: string }) =>
  api.post<ApiResponse<HazardPlanBuilderResult>>(`${BASE(eid)}/ai/plan-builder`, data).then(r => r.data.data);
export const aiScheduleSuggestion = (eid: string, data: { plan_draft: string; zone_risk_hints?: string | null; history_hints?: string | null }) =>
  api.post<ApiResponse<HazardScheduleSuggestionResult>>(`${BASE(eid)}/ai/schedule-suggestion`, data).then(r => r.data.data);
export const aiChecklistSuggestion = (eid: string, data: { task_context: string }) =>
  api.post<ApiResponse<HazardChecklistSuggestionResult>>(`${BASE(eid)}/ai/checklist`, data).then(r => r.data.data);
export const aiSetupWizard = (eid: string, data: { industry: string; areas: string; employee_count?: string | null; frequency_preference?: string | null }) =>
  api.post<ApiResponse<HazardSetupWizardResult>>(`${BASE(eid)}/ai/setup-wizard`, data).then(r => r.data.data);
export const aiChecklistTemplate = (eid: string, data: { industry: string; risk_points: string }) =>
  api.post<ApiResponse<HazardChecklistTemplateAIResult>>(`${BASE(eid)}/ai/checklist-template`, data).then(r => r.data.data);

// ── 导出（blob 下载，与 exportControlList 惯例一致：保留响应体供页面构造下载） ──

export const exportHazardLedger = (eid: string) =>
  api.get<Blob>(`${BASE(eid)}/export/ledger.xlsx`, { responseType: "blob" });
export const exportHazardReport = (eid: string) =>
  api.get<Blob>(`${BASE(eid)}/export/report.xlsx`, { responseType: "blob" });
