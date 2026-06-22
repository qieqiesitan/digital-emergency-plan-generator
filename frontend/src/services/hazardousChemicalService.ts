import api from "./api";
import type { ApiResponse, PaginatedResponse } from "@/types/common";
import type { HazardousChemical, HazardousChemicalCreate, HazardousChemicalUpdate } from "@/types/hazardousChemical";

export async function listChemicals(
  enterpriseId: string,
  params?: Record<string, unknown>
): Promise<PaginatedResponse<HazardousChemical>> {
  const res = await api.get<PaginatedResponse<HazardousChemical>>(
    `/enterprises/${enterpriseId}/chemicals`,
    { params }
  );
  return res.data;
}

export async function getChemical(enterpriseId: string, id: string): Promise<HazardousChemical> {
  const res = await api.get<ApiResponse<HazardousChemical>>(
    `/enterprises/${enterpriseId}/chemicals/${id}`
  );
  return res.data.data;
}

export async function createChemical(
  enterpriseId: string,
  data: HazardousChemicalCreate
): Promise<HazardousChemical> {
  const res = await api.post<ApiResponse<HazardousChemical>>(
    `/enterprises/${enterpriseId}/chemicals`,
    data
  );
  return res.data.data;
}

export async function updateChemical(
  enterpriseId: string,
  id: string,
  data: HazardousChemicalUpdate
): Promise<HazardousChemical> {
  const res = await api.put<ApiResponse<HazardousChemical>>(
    `/enterprises/${enterpriseId}/chemicals/${id}`,
    data
  );
  return res.data.data;
}

export async function deleteChemical(enterpriseId: string, id: string): Promise<void> {
  await api.delete(`/enterprises/${enterpriseId}/chemicals/${id}`);
}


// ── AI 智能生成 ──
export interface AIQuestion {
  id: string;
  question: string;
}

export interface AIQuestionsResponse {
  questions: AIQuestion[];
}

export async function getChemicalAIQuestions(enterpriseId: string): Promise<AIQuestion[]> {
  const res = await api.post<ApiResponse<AIQuestionsResponse>>(
    `/enterprises/${enterpriseId}/chemicals/ai/questions`
  );
  return res.data.data.questions;
}

export interface AIGenerateChemicalsResponse {
  items: HazardousChemicalCreate[];
}

export async function generateChemicalsAI(
  enterpriseId: string,
  answers: { question_id: string; question: string; answer: string }[]
): Promise<HazardousChemicalCreate[]> {
  const res = await api.post<ApiResponse<AIGenerateChemicalsResponse>>(
    `/enterprises/${enterpriseId}/chemicals/ai/generate`,
    { answers },
    { timeout: 120000 }
  );
  return res.data.data.items;
}

export async function batchCreateChemicals(
  enterpriseId: string,
  items: HazardousChemicalCreate[]
): Promise<HazardousChemical[]> {
  const res = await api.post<ApiResponse<HazardousChemical[]>>(
    `/enterprises/${enterpriseId}/chemicals/batch`,
    { items }
  );
  return res.data.data;
}