import api from "./api";
import type { ApiResponse, PaginatedResponse } from "@/types/common";
import type { AxiosRequestConfig } from "axios";
import type { HazardousChemical, HazardousChemicalCreate, HazardousChemicalUpdate } from "@/types/hazardousChemical";

export async function listChemicals(
  enterpriseId: string,
  params?: Record<string, unknown>,
  config?: AxiosRequestConfig
): Promise<PaginatedResponse<HazardousChemical>> {
  const res = await api.get<PaginatedResponse<HazardousChemical>>(
    `/enterprises/${enterpriseId}/chemicals`,
    { params, ...config }
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
  data: HazardousChemicalCreate,
  config?: AxiosRequestConfig
): Promise<HazardousChemical> {
  const res = await api.post<ApiResponse<HazardousChemical>>(
    `/enterprises/${enterpriseId}/chemicals`,
    data,
    config
  );
  return res.data.data;
}

export async function updateChemical(
  enterpriseId: string,
  id: string,
  data: HazardousChemicalUpdate,
  config?: AxiosRequestConfig
): Promise<HazardousChemical> {
  const res = await api.put<ApiResponse<HazardousChemical>>(
    `/enterprises/${enterpriseId}/chemicals/${id}`,
    data,
    config
  );
  return res.data.data;
}

export async function deleteChemical(enterpriseId: string, id: string, config?: AxiosRequestConfig): Promise<void> {
  await api.delete(`/enterprises/${enterpriseId}/chemicals/${id}`, config);
}


// ── AI 智能生成 ──
export interface AIQuestion {
  id: string;
  question: string;
}

export interface AIQuestionsResponse {
  questions: AIQuestion[];
}

export async function getChemicalAIQuestions(enterpriseId: string, config?: AxiosRequestConfig): Promise<AIQuestion[]> {
  const res = await api.post<ApiResponse<AIQuestionsResponse>>(
    `/enterprises/${enterpriseId}/chemicals/ai/questions`,
    undefined,
    config
  );
  return res.data.data.questions;
}

export interface AIGenerateChemicalsResponse {
  items: HazardousChemicalCreate[];
}

export async function generateChemicalsAI(
  enterpriseId: string,
  answers: { question_id: string; question: string; answer: string }[],
  config?: AxiosRequestConfig
): Promise<HazardousChemicalCreate[]> {
  const res = await api.post<ApiResponse<AIGenerateChemicalsResponse>>(
    `/enterprises/${enterpriseId}/chemicals/ai/generate`,
    { answers },
    { timeout: 180000, ...config }
  );
  return res.data.data.items;
}

export async function batchCreateChemicals(
  enterpriseId: string,
  items: HazardousChemicalCreate[],
  config?: AxiosRequestConfig
): Promise<HazardousChemical[]> {
  const res = await api.post<ApiResponse<HazardousChemical[]>>(
    `/enterprises/${enterpriseId}/chemicals/batch`,
    { items },
    config
  );
  return res.data.data;
}
