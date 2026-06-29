import api from "./api";
import type { ApiResponse } from "@/types/common";
import type { ExportPreview, ExportTask, ExportValidation } from "@/types/plan";

export async function getExportPreview(planId: string): Promise<ExportPreview> {
  const res = await api.get<ApiResponse<ExportPreview>>(`/plans/${planId}/export/preview`);
  return res.data.data;
}

export async function exportDocx(planId: string): Promise<Blob | ExportTask> {
  const res = await api.post(`/plans/${planId}/export/docx`, {}, { responseType: "blob" });
  // 如果是 Blob，直接返回
  if (res.headers["content-type"]?.includes("application/vnd.openxmlformats")) {
    return res.data as Blob;
  }
  // 否则是 JSON 的异步任务
  const text = await (res.data as Blob).text();
  return JSON.parse(text).data as ExportTask;
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
