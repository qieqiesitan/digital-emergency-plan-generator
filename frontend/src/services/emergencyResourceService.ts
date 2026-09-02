import api from "./api";
import type { ApiResponse, PaginatedResponse } from "@/types/common";
import type { AxiosRequestConfig } from "axios";
import type { EmergencyResource, EmergencyResourceCreate, EmergencyResourceUpdate } from "@/types/emergencyResource";

export async function listResources(enterpriseId: string, params?: Record<string, unknown>): Promise<PaginatedResponse<EmergencyResource>> {
  const res = await api.get<PaginatedResponse<EmergencyResource>>(`/enterprises/${enterpriseId}/resources`, { params });
  return res.data;
}

export async function getResource(enterpriseId: string, id: string): Promise<EmergencyResource> {
  const res = await api.get<ApiResponse<EmergencyResource>>(`/enterprises/${enterpriseId}/resources/${id}`);
  return res.data.data;
}

export async function createResource(enterpriseId: string, data: EmergencyResourceCreate, config?: AxiosRequestConfig): Promise<EmergencyResource> {
  const res = await api.post<ApiResponse<EmergencyResource>>(`/enterprises/${enterpriseId}/resources`, data, config);
  return res.data.data;
}

export async function updateResource(enterpriseId: string, id: string, data: EmergencyResourceUpdate, config?: AxiosRequestConfig): Promise<EmergencyResource> {
  const res = await api.put<ApiResponse<EmergencyResource>>(`/enterprises/${enterpriseId}/resources/${id}`, data, config);
  return res.data.data;
}

export async function deleteResource(enterpriseId: string, id: string, config?: AxiosRequestConfig): Promise<void> {
  await api.delete(`/enterprises/${enterpriseId}/resources/${id}`, config);
}

// --- Extended: import & AI ---

export interface ResourceImportPreviewItem {
  row: number;
  data: EmergencyResourceCreate;
  errors: string[];
}

export interface ResourceImportPreviewResponse {
  items: ResourceImportPreviewItem[];
  valid_count: number;
  error_count: number;
}

export async function downloadResourceTemplate(enterpriseId: string): Promise<void> {
  const res = await api.get(`/enterprises/${enterpriseId}/resources/template`, { responseType: "blob" });
  const url = window.URL.createObjectURL(new Blob([res.data]));
  const a = document.createElement("a");
  a.href = url;
  a.download = "emergency_resources_template.xlsx";
  a.click();
  window.URL.revokeObjectURL(url);
}

export async function previewResourceImport(enterpriseId: string, file: File, config?: AxiosRequestConfig): Promise<ResourceImportPreviewResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await api.post<ApiResponse<ResourceImportPreviewResponse>>(`/enterprises/${enterpriseId}/resources/import`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 30000,
    ...config,
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

export async function getResourceAIQuestions(enterpriseId: string, config?: AxiosRequestConfig): Promise<AIQuestion[]> {
  const res = await api.post<ApiResponse<AIQuestionsResponse>>(`/enterprises/${enterpriseId}/resources/ai/questions`, undefined, config);
  return res.data.data.questions;
}

export interface AIGenerateResourceResponse {
  items: EmergencyResourceCreate[];
}

export async function generateResourcesAI(
  enterpriseId: string,
  answers: { question_id: string; question: string; answer: string }[],
  config?: AxiosRequestConfig,
): Promise<EmergencyResourceCreate[]> {
  const res = await api.post<ApiResponse<AIGenerateResourceResponse>>(
    `/enterprises/${enterpriseId}/resources/ai/generate`,
    { answers },
    { timeout: 180000, ...config },
  );
  return res.data.data.items;
}

export async function batchCreateResources(enterpriseId: string, items: EmergencyResourceCreate[], config?: AxiosRequestConfig): Promise<EmergencyResource[]> {
  const res = await api.post<ApiResponse<EmergencyResource[]>>(`/enterprises/${enterpriseId}/resources/batch`, { items }, config);
  return res.data.data;
}
