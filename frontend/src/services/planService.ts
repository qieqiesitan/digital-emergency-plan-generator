import api from "./api";
import type { ApiResponse, PaginatedResponse, PaginationParams } from "@/types/common";
import type { PlanProject, PlanCreate, PlanUpdate, EnterprisePlanSummary } from "@/types/plan";

export interface PlanQueryParams extends PaginationParams {
  enterprise_id: string;
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