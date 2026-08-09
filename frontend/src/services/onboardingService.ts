import api from "./api";
import type { CompletionResult } from "@/types/onboarding";

export function getEnterpriseCompletion(enterpriseId: string): Promise<CompletionResult> {
  return api.get(`/enterprises/${enterpriseId}/completion`).then(r => r.data.data);
}

export function importOnboardingFile(enterpriseId: string, module: string, file: File): Promise<{ module: string; candidates: unknown[]; source: string }> {
  const form = new FormData();
  form.append("module", module);
  form.append("file", file);
  return api.post(`/onboarding/import`, form).then(r => r.data.data);
}

export function importOnboardingBatch(enterpriseId: string, files: File[]): Promise<{ module: string; candidates: unknown[]; source: string }[]> {
  const form = new FormData();
  files.forEach(f => form.append("files", f));
  return api.post(`/onboarding/import/batch`, form).then(r => r.data.data);
}
