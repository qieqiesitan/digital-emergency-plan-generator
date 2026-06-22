import api from "./api";
import type { ApiResponse } from "@/types/common";

export interface PromptTemplate {
  id: number;
  template_code: string;
  template_name: string;
  systemPrompt: string;
  userPromptTemplate: string;
  category: string;
  status: string;
}

export interface PromptCreate {
  template_code: string;
  template_name: string;
  systemPrompt: string;
  userPromptTemplate: string;
  category: string;
}

export interface PromptUpdate {
  template_name?: string;
  systemPrompt?: string;
  userPromptTemplate?: string;
  category?: string;
  status?: string;
}

export interface PromptTestRequest {
  variables: Record<string, string>;
}

export interface PromptTestResult {
  result: string;
  tokens_used?: number;
}

export async function fetchPrompts(category?: string): Promise<PromptTemplate[]> {
  const params = category ? { category } : {};
  const res = await api.get<ApiResponse<PromptTemplate[]>>("/prompts", { params });
  return res.data.data;
}

export async function fetchPrompt(id: number): Promise<PromptTemplate> {
  const res = await api.get<ApiResponse<PromptTemplate>>(`/prompts/${id}`);
  return res.data.data;
}

export async function createPrompt(data: PromptCreate): Promise<PromptTemplate> {
  const res = await api.post<ApiResponse<PromptTemplate>>("/prompts", data);
  return res.data.data;
}

export async function updatePrompt(id: number, data: PromptUpdate): Promise<PromptTemplate> {
  const res = await api.put<ApiResponse<PromptTemplate>>(`/prompts/${id}`, data);
  return res.data.data;
}

export async function testPrompt(id: number, variables: Record<string, string>): Promise<PromptTestResult> {
  const res = await api.post<ApiResponse<PromptTestResult>>(`/prompts/${id}/test`, { variables });
  return res.data.data;
}
