import api from "./api";
import type { ApiResponse, PaginatedResponse, PaginationParams } from "@/types/common";
import type { Enterprise, EnterpriseCreate, EnterpriseUpdate, OrgGroup, SurroundingInfo } from "@/types/enterprise";

export interface EnterpriseQueryParams extends PaginationParams {
  search?: string;
  industry?: string;
}

export async function listEnterprises(params?: EnterpriseQueryParams): Promise<PaginatedResponse<Enterprise>> {
  const res = await api.get<PaginatedResponse<Enterprise>>("/enterprises", { params });
  return res.data;
}

export async function getEnterprise(id: string): Promise<Enterprise> {
  const res = await api.get<ApiResponse<Enterprise>>(`/enterprises/${id}`);
  return res.data.data;
}

export async function createEnterprise(data: EnterpriseCreate): Promise<Enterprise> {
  const res = await api.post<ApiResponse<Enterprise>>("/enterprises", data);
  return res.data.data;
}

export async function updateEnterprise(id: string, data: EnterpriseUpdate): Promise<Enterprise> {
  const res = await api.put<ApiResponse<Enterprise>>(`/enterprises/${id}`, data);
  return res.data.data;
}

export async function deleteEnterprise(id: string): Promise<void> {
  await api.delete(`/enterprises/${id}`);
}

export async function getOrgStructure(id: string): Promise<OrgGroup[]> {
  const res = await api.get<ApiResponse<OrgGroup[]>>(`/enterprises/${id}/org-structure`);
  return res.data.data;
}

export async function updateOrgStructure(id: string, data: OrgGroup[]): Promise<OrgGroup[]> {
  const res = await api.put<ApiResponse<OrgGroup[]>>(`/enterprises/${id}/org-structure`, data);
  return res.data.data;
}

export async function getSurrounding(id: string): Promise<SurroundingInfo> {
  const res = await api.get<ApiResponse<SurroundingInfo>>(`/enterprises/${id}/surrounding`);
  return res.data.data;
}

export async function updateSurrounding(id: string, data: SurroundingInfo): Promise<SurroundingInfo> {
  const res = await api.put<ApiResponse<SurroundingInfo>>(`/enterprises/${id}/surrounding`, data);
  return res.data.data;
}

// --- AI Surrounding ---

export interface AIQuestion {
  id: string;
  question: string;
}

export interface AIQuestionsResponse {
  questions: AIQuestion[];
}

export async function getSurroundingAIQuestions(enterpriseId: string): Promise<AIQuestion[]> {
  const res = await api.post<ApiResponse<AIQuestionsResponse>>(`/enterprises/${enterpriseId}/surrounding/ai/questions`);
  return res.data.data.questions;
}

export interface AIGenerateSurroundingResponse {
  surrounding: SurroundingInfo;
}

export async function generateSurroundingAI(
  enterpriseId: string,
  answers: { question_id: string; question: string; answer: string }[],
): Promise<SurroundingInfo> {
  const res = await api.post<ApiResponse<AIGenerateSurroundingResponse>>(
    `/enterprises/${enterpriseId}/surrounding/ai/generate`,
    { answers },
    { timeout: 120000 },
  );
  return res.data.data.surrounding;
}
