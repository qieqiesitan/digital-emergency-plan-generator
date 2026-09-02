import api from "./api";
import type { AxiosRequestConfig } from "axios";
import type { ApiResponse, PaginatedResponse, PaginationParams } from "@/types/common";
import type {
  PlanProject, PlanCreate, PlanUpdate, EnterprisePlanSummary,
  PlanSection, SectionUpdate,
  PlanTemplate, PlanType,
  PlanVersion, PlanVersionDetail, VersionCompare,
} from "@/types/plan";

export interface PlanQueryParams extends PaginationParams {
  enterprise_id?: string;
  plan_type?: string;
  status?: string;
  search?: string;
}

export async function listPlans(params: PlanQueryParams): Promise<PaginatedResponse<PlanProject>> {
  const res = await api.get<PaginatedResponse<PlanProject>>("/plans", { params });
  return res.data;
}

export async function getPlan(id: string): Promise<PlanProject> {
  const res = await api.get<ApiResponse<PlanProject>>(`/plans/${id}`);
  return res.data.data;
}

export async function createPlan(data: PlanCreate, config?: AxiosRequestConfig): Promise<PlanProject> {
  const res = await api.post<ApiResponse<PlanProject>>("/plans", data, config);
  return res.data.data;
}

export async function updatePlan(id: string, data: PlanUpdate, config?: AxiosRequestConfig): Promise<PlanProject> {
  const res = await api.put<ApiResponse<PlanProject>>(`/plans/${id}`, data, config);
  return res.data.data;
}

export async function deletePlan(id: string, config?: AxiosRequestConfig): Promise<void> {
  await api.delete(`/plans/${id}`, config);
}

export async function duplicatePlan(id: string, config?: AxiosRequestConfig): Promise<PlanProject> {
  const res = await api.post<ApiResponse<PlanProject>>(`/plans/${id}/duplicate`, undefined, config);
  return res.data.data;
}

export async function getEnterprisePlanSummary(): Promise<EnterprisePlanSummary[]> {
  const res = await api.get<ApiResponse<EnterprisePlanSummary[]>>("/plans/enterprise-summary");
  return res.data.data;
}

// ── Sections (from sectionService) ──

export async function listSections(planId: string): Promise<PlanSection[]> {
  const res = await api.get<ApiResponse<PlanSection[]>>(`/plans/${planId}/sections`);
  return res.data.data;
}

export async function getSection(planId: string, sectionKey: string): Promise<PlanSection> {
  const res = await api.get<ApiResponse<PlanSection>>(`/plans/${planId}/sections/${sectionKey}`);
  return res.data.data;
}

export async function updateSection(planId: string, sectionKey: string, data: SectionUpdate, config?: AxiosRequestConfig): Promise<PlanSection> {
  const res = await api.put<ApiResponse<PlanSection>>(`/plans/${planId}/sections/${sectionKey}`, data, config);
  return res.data.data;
}

export async function autofillSection(planId: string, sectionKey: string, config?: AxiosRequestConfig): Promise<PlanSection> {
  const res = await api.post<ApiResponse<PlanSection>>(`/plans/${planId}/sections/${sectionKey}/autofill`, undefined, config);
  return res.data.data;
}

export async function regenerateMissingDiagrams(
  planId: string,
  config?: AxiosRequestConfig
): Promise<{ regenerated: number; skipped: number; placeholders_remaining: number }> {
  const res = await api.post<ApiResponse<{ regenerated: number; skipped: number; placeholders_remaining: number }>>(
    `/plans/${planId}/diagrams/regenerate-missing`,
    undefined,
    config
  );
  return res.data.data;
}

// ── Templates (from templateService) ──

export async function listTemplates(planType?: PlanType): Promise<PaginatedResponse<PlanTemplate>> {
  const params = planType ? { plan_type: planType } : undefined;
  const res = await api.get<PaginatedResponse<PlanTemplate>>("/templates", { params });
  return res.data;
}

export async function getTemplate(id: string): Promise<PlanTemplate> {
  const res = await api.get<ApiResponse<PlanTemplate>>(`/templates/${id}`);
  return res.data.data;
}

// ── Versions (from versionService) ──

export async function listVersions(planId: string): Promise<PlanVersion[]> {
  const res = await api.get<ApiResponse<PlanVersion[]>>(`/plans/${planId}/versions`);
  return res.data.data;
}

export async function getVersion(planId: string, versionId: string): Promise<PlanVersionDetail> {
  const res = await api.get<ApiResponse<PlanVersionDetail>>(`/plans/${planId}/versions/${versionId}`);
  return res.data.data;
}

export async function createVersion(planId: string, description?: string, config?: AxiosRequestConfig): Promise<PlanVersion> {
  const res = await api.post<ApiResponse<PlanVersion>>(`/plans/${planId}/versions`, { description }, config);
  return res.data.data;
}

export async function compareVersions(planId: string, versionA: number, versionB: number): Promise<VersionCompare> {
  const res = await api.get<ApiResponse<VersionCompare>>(`/plans/${planId}/versions/compare`, {
    params: { a: versionA, b: versionB },
  });
  return res.data.data;
}

export async function rollbackVersion(planId: string, versionId: string, config?: AxiosRequestConfig): Promise<void> {
  await api.post(`/plans/${planId}/versions/${versionId}/rollback`, undefined, config);
}

// ── AI Review ──

export interface PlanReviewIssue {
  section_key: string;
  section_title: string;
  issue?: string;
  warning?: string;
  evidence?: string;
}

export interface PlanReviewResult {
  plan_id: string;
  title: string;
  issues: PlanReviewIssue[];
  warnings: PlanReviewIssue[];
}

export interface PlanReviewApplyResult {
  plan_id: string;
  applied: string[];
  snapshot_version: number;
}

export async function fetchPlanReview(planId: string, config?: AxiosRequestConfig): Promise<PlanReviewResult> {
  const res = await api.get<ApiResponse<PlanReviewResult>>(`/plans/${planId}/review`, config);
  return res.data.data;
}

export async function applyPlanReview(
  planId: string,
  mode: "auto" | "llm",
  sectionKeys?: string[],
  config?: AxiosRequestConfig
): Promise<PlanReviewApplyResult> {
  const res = await api.post<ApiResponse<PlanReviewApplyResult>>(`/plans/${planId}/review/apply`, {
    mode,
    section_keys: sectionKeys ?? null,
  }, config);
  return res.data.data;
}
