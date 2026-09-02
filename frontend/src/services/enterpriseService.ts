import api from "./api";
import type { AxiosRequestConfig } from "axios";
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

export async function createEnterprise(data: EnterpriseCreate, config?: AxiosRequestConfig): Promise<Enterprise> {
  const res = await api.post<ApiResponse<Enterprise>>("/enterprises", data, config);
  return res.data.data;
}

export async function updateEnterprise(id: string, data: EnterpriseUpdate, config?: AxiosRequestConfig): Promise<Enterprise> {
  const res = await api.put<ApiResponse<Enterprise>>(`/enterprises/${id}`, data, config);
  return res.data.data;
}

export async function deleteEnterprise(id: string, config?: AxiosRequestConfig): Promise<void> {
  await api.delete(`/enterprises/${id}`, config);
}

export async function getOrgStructure(id: string): Promise<OrgGroup[]> {
  const res = await api.get<ApiResponse<OrgGroup[]>>(`/enterprises/${id}/org-structure`);
  return res.data.data;
}

export async function updateOrgStructure(id: string, data: OrgGroup[], config?: AxiosRequestConfig): Promise<OrgGroup[]> {
  const res = await api.put<ApiResponse<OrgGroup[]>>(`/enterprises/${id}/org-structure`, data, config);
  return res.data.data;
}

export async function getSurrounding(id: string): Promise<SurroundingInfo> {
  const res = await api.get<ApiResponse<SurroundingInfo>>(`/enterprises/${id}/surrounding`);
  return res.data.data;
}

export async function updateSurrounding(id: string, data: SurroundingInfo, config?: AxiosRequestConfig): Promise<SurroundingInfo> {
  const res = await api.put<ApiResponse<SurroundingInfo>>(`/enterprises/${id}/surrounding`, data, config);
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

export async function getSurroundingAIQuestions(enterpriseId: string, config?: AxiosRequestConfig): Promise<AIQuestion[]> {
  const res = await api.post<ApiResponse<AIQuestionsResponse>>(`/enterprises/${enterpriseId}/surrounding/ai/questions`, undefined, config);
  return res.data.data.questions;
}

export interface AIGenerateSurroundingResponse {
  surrounding: SurroundingInfo;
}

export async function generateSurroundingAI(
  enterpriseId: string,
  answers: { question_id: string; question: string; answer: string }[],
  config?: AxiosRequestConfig,
): Promise<SurroundingInfo> {
  const res = await api.post<ApiResponse<AIGenerateSurroundingResponse>>(
    `/enterprises/${enterpriseId}/surrounding/ai/generate`,
    { answers },
    { timeout: 180000, ...config },
  );
  return res.data.data.surrounding;
}

// ponytail: merged from uploadService.ts
import axios from "axios";

export async function uploadFile(file: File): Promise<string> {
  const token = localStorage.getItem("access_token");
  const formData = new FormData();
  formData.append("file", file);
  const res = await axios.post<{ code: number; data: { url: string } }>(
    "/api/v1/upload", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
  return res.data.data.url;
}
// ── AI Autofill ──

export interface AutofillResult {
  name?: string;
  fields: Record<string, string | number | null>;
  error?: string;
}

export async function autofillEnterprise(companyName: string, config?: AxiosRequestConfig): Promise<AutofillResult> {
  const res = await api.post<ApiResponse<AutofillResult>>("/enterprises/autofill", { name: companyName }, config);
  return res.data.data;
}

// ── Amap POI search ──

export interface AmapPoiTypeItem {
  code: string;
  label: string;
  target_type: "nearby" | "sensitive";
}

export interface AmapSearchParams {
  radius?: number;
  types?: string;  // comma-separated codes
}

export interface AmapSearchResult {
  surrounding: SurroundingInfo;
  searched_address: string;
  has_gis: boolean;
  available_types: AmapPoiTypeItem[];
}

export async function searchAmapSurrounding(
  enterpriseId: string,
  params?: AmapSearchParams,
  config?: AxiosRequestConfig,
): Promise<AmapSearchResult> {
  const res = await api.post<ApiResponse<AmapSearchResult>>(
    `/enterprises/${enterpriseId}/surrounding/amap-search`,
    params || {},
    { timeout: 30000, ...config },
  );
  return res.data.data;
}

