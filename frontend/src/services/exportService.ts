import api from "./api";
import type { ApiResponse } from "@/types/common";
import type { ExportPreview, ExportTask, ExportValidation } from "@/types/plan";

export async function getExportPreview(planId: string): Promise<ExportPreview> {
  const res = await api.get<ApiResponse<ExportPreview>>(`/plans/${planId}/export/preview`);
  return res.data.data;
}

export async function exportDocx(planId: string): Promise<Blob | ExportTask> {
  const res = await api.post(`/plans/${planId}/export/docx`, {}, { responseType: "blob", timeout: 120000 });
  const ct = String(res.headers["content-type"] || "");
  if (ct.includes("application/vnd.openxmlformats") || ct.includes("application/octet-stream")) {
    return res.data as Blob;
  }
  // Backend returned error JSON inside blob
  const text = await (res.data as Blob).text();
  try {
    const parsed = JSON.parse(text);
    throw new Error(parsed.detail || parsed.message || ("Server error: " + text.slice(0, 200)));
  } catch (e: unknown) {
    if (e instanceof Error && !e.message.startsWith("Server error:")) throw e;
    throw new Error("Server error: " + text.slice(0, 200));
  }
}

export async function validateExport(planId: string): Promise<ExportValidation> {
  const res = await api.post<ApiResponse<ExportValidation>>(`/plans/${planId}/export/validate`);
  return res.data.data;
}

export async function getExportTaskStatus(taskId: string): Promise<ExportTask> {
  const res = await api.get<ApiResponse<ExportTask>>(`/export/tasks/${taskId}`);
  return res.data.data;
}

export function getDownloadUrl(fileKey: string): string {
  return `/api/v1/export/download/${fileKey}`;
}
