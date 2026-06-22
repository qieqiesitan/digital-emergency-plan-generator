import api from "./api";
import type { ApiResponse, PaginatedResponse } from "@/types/common";
import type { RiskSource, RiskSourceCreate, RiskSourceUpdate } from "@/types/riskSource";

export async function listRiskSources(enterpriseId: string, params?: Record<string, unknown>): Promise<PaginatedResponse<RiskSource>> {
  const res = await api.get<PaginatedResponse<RiskSource>>(`/enterprises/${enterpriseId}/risk-sources`, { params });
  return res.data;
}

export async function getRiskSource(enterpriseId: string, id: string): Promise<RiskSource> {
  const res = await api.get<ApiResponse<RiskSource>>(`/enterprises/${enterpriseId}/risk-sources/${id}`);
  return res.data.data;
}

export async function createRiskSource(enterpriseId: string, data: RiskSourceCreate): Promise<RiskSource> {
  const res = await api.post<ApiResponse<RiskSource>>(`/enterprises/${enterpriseId}/risk-sources`, data);
  return res.data.data;
}

export async function updateRiskSource(enterpriseId: string, id: string, data: RiskSourceUpdate): Promise<RiskSource> {
  const res = await api.put<ApiResponse<RiskSource>>(`/enterprises/${enterpriseId}/risk-sources/${id}`, data);
  return res.data.data;
}

export async function deleteRiskSource(enterpriseId: string, id: string): Promise<void> {
  await api.delete(`/enterprises/${enterpriseId}/risk-sources/${id}`);
}

// --- Extended: import & AI ---

export interface ImportPreviewItem {
  row: number;
  data: RiskSourceCreate;
  errors: string[];
}

export interface ImportPreviewResponse {
  items: ImportPreviewItem[];
  valid_count: number;
  error_count: number;
}

export async function downloadRiskSourceTemplate(enterpriseId: string): Promise<void> {
  const res = await api.get(`/enterprises/${enterpriseId}/risk-sources/template`, { responseType: "blob" });
  const url = window.URL.createObjectURL(new Blob([res.data]));
  const a = document.createElement("a");
  a.href = url;
  a.download = "risk_sources_template.xlsx";
  a.click();
  window.URL.revokeObjectURL(url);
}

export async function previewRiskSourceImport(enterpriseId: string, file: File): Promise<ImportPreviewResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await api.post<ApiResponse<ImportPreviewResponse>>(`/enterprises/${enterpriseId}/risk-sources/import`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 30000,
  });
  return res.data.data;
}

export interface AIQuestion {
  id: string;
  question: string;
}

export interface AIQuestionsResponse {
  questions: AIQuestion[];
}

export async function getRiskSourceAIQuestions(enterpriseId: string): Promise<AIQuestion[]> {
  const res = await api.post<ApiResponse<AIQuestionsResponse>>(`/enterprises/${enterpriseId}/risk-sources/ai/questions`);
  return res.data.data.questions;
}

export interface AIGenerateRiskResponse {
  items: RiskSourceCreate[];
}

export async function generateRiskSourcesAI(
  enterpriseId: string,
  answers: { question_id: string; question: string; answer: string }[],
): Promise<RiskSourceCreate[]> {
  const res = await api.post<ApiResponse<AIGenerateRiskResponse>>(
    `/enterprises/${enterpriseId}/risk-sources/ai/generate`,
    { answers },
    { timeout: 120000 },
  );
  return res.data.data.items;
}

export async function batchCreateRiskSources(enterpriseId: string, items: RiskSourceCreate[]): Promise<RiskSource[]> {
  const res = await api.post<ApiResponse<RiskSource[]>>(`/enterprises/${enterpriseId}/risk-sources/batch`, { items });
  return res.data.data;
}
