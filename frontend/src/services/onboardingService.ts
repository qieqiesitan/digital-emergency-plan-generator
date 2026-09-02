import api from "./api";
import type { AxiosRequestConfig } from "axios";
import type { CompletionResult, ImportResult } from "@/types/onboarding";

export function getEnterpriseCompletion(enterpriseId: string, config?: AxiosRequestConfig): Promise<CompletionResult> {
  return api.get(`/enterprises/${enterpriseId}/completion`, config).then(r => r.data.data);
}

export function importOnboardingFile(
  enterpriseId: string,
  module: string,
  file: File,
  config?: AxiosRequestConfig,
): Promise<ImportResult> {
  const form = new FormData();
  form.append("module", module);
  form.append("file", file);
  // ImportDrawer 导入失败自带 message.error，跳过全局 toast 防双弹
  return api.post(`/onboarding/import`, form, config).then(r => r.data.data);
}

export function importOnboardingBatch(
  enterpriseId: string,
  files: File[],
  config?: AxiosRequestConfig,
): Promise<ImportResult[]> {
  const form = new FormData();
  files.forEach(f => form.append("files", f));
  // ImportDrawer 导入失败自带 message.error，跳过全局 toast 防双弹
  return api.post(`/onboarding/import/batch`, form, config).then(r => r.data.data);
}
