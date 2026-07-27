import api from "./api";
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

export async function createPlan(data: PlanCreate): Promise<PlanProject> {
  const res = await api.post<ApiResponse<PlanProject>>("/plans", data);
  return res.data.data;
}

export async function updatePlan(id: string, data: PlanUpdate): Promise<PlanProject> {
  const res = await api.put<ApiResponse<PlanProject>>(`/plans/${id}`, data);
  return res.data.data;
}

export async function deletePlan(id: string): Promise<void> {
  await api.delete(`/plans/${id}`);
}

export async function duplicatePlan(id: string): Promise<PlanProject> {
  const res = await api.post<ApiResponse<PlanProject>>(`/plans/${id}/duplicate`);
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

export async function updateSection(planId: string, sectionKey: string, data: SectionUpdate): Promise<PlanSection> {
  const res = await api.put<ApiResponse<PlanSection>>(`/plans/${planId}/sections/${sectionKey}`, data);
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

export async function createVersion(planId: string, description?: string): Promise<PlanVersion> {
  const res = await api.post<ApiResponse<PlanVersion>>(`/plans/${planId}/versions`, { description });
  return res.data.data;
}

export async function compareVersions(planId: string, versionA: number, versionB: number): Promise<VersionCompare> {
  const res = await api.get<ApiResponse<VersionCompare>>(`/plans/${planId}/versions/compare`, {
    params: { a: versionA, b: versionB },
  });
  return res.data.data;
}

export async function rollbackVersion(planId: string, versionId: string): Promise<void> {
  await api.post(`/plans/${planId}/versions/${versionId}/rollback`);
}
