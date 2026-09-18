import api from "./api";
import type { ApiResponse } from "@/types/common";
import type { ExportPreview, ExportTask, ExportValidation } from "@/types/plan";

export async function getExportPreview(planId: string): Promise<ExportPreview> {
  const res = await api.get<ApiResponse<ExportPreview>>(`/plans/${planId}/export/preview`);
  return res.data.data;
}

export async function exportDocx(planId: string): Promise<Blob | ExportTask> {
  // 导出页自行解析错误并 message.error；blob 响应体错误由调用方处理，跳过全局 toast
  const res = await api.post(`/plans/${planId}/export/docx`, {}, { responseType: "blob", timeout: 120000, skipGlobalError: true });
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
    throw new Error("Server error: " + text.slice(0, 200), { cause: e });
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
  // 下载走 window.open（无法带 Authorization 头）：使用后端 /download 端点支持的
  // ?token= 查询参数鉴权（W0 安全修复后该端点必须登录，且只能下载本人企业的导出物）
  const token = typeof localStorage !== "undefined" ? localStorage.getItem("access_token") || "" : "";
  const suffix = token ? `?token=${encodeURIComponent(token)}` : "";
  return `/api/v1/export/download/${fileKey}${suffix}`;
}
