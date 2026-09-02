import type { ApiResponse } from '@/types/common';
import type { RiskAssessmentReport, RiskAssessmentPreview, ReportVersionItem, SSEEvent } from "@/types/riskAssessment";
import api from "./api";
import type { AxiosRequestConfig } from "axios";

export async function getRiskAssessment(enterpriseId: string, config?: AxiosRequestConfig): Promise<RiskAssessmentReport> {
  const res = await api.get(`/enterprises/${enterpriseId}/risk-assessment`, config);
  return res.data.data;
}

export async function getRiskAssessmentSummary(enterpriseId: string): Promise<RiskAssessmentReport["summary"]> {
  const res = await api.get(`/enterprises/${enterpriseId}/risk-assessment/summary`);
  return res.data.data;
}

export async function getRiskAssessmentPreview(enterpriseId: string): Promise<RiskAssessmentPreview> {
  const res = await api.get(`/enterprises/${enterpriseId}/risk-assessment/preview`);
  return res.data.data;
}

export async function downloadRiskAssessment(enterpriseId: string): Promise<void> {
  const token = localStorage.getItem("access_token");
  const url = `/api/v1/enterprises/${enterpriseId}/risk-assessment/export?token=${token}`;
  const resp = await fetch(url);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: "download failed" }));
    throw new Error(err.detail || err.message || "download failed");
  }
  const blob = await resp.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "risk_assessment_report.docx";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
}

export async function saveRiskAssessmentContent(enterpriseId: string, content: string, config?: AxiosRequestConfig): Promise<{ content_length: number }> {
  // RiskAssessmentPreview 保存失败自带 message.error，跳过全局 toast 防双弹
  const res = await api.put(`/enterprises/${enterpriseId}/risk-assessment/content`, { content }, config);
  return res.data.data;
}

export async function createRiskAssessmentVersion(enterpriseId: string, config?: AxiosRequestConfig): Promise<ReportVersionItem> {
  // RiskAssessmentPreview 保存版本失败自带 message.error，跳过全局 toast 防双弹
  const res = await api.post(`/enterprises/${enterpriseId}/risk-assessment/versions`, {}, config);
  return res.data.data;
}

export async function listRiskAssessmentVersions(enterpriseId: string, config?: AxiosRequestConfig): Promise<ReportVersionItem[]> {
  // RiskAssessmentPreview 版本列表失败自带 message.error，跳过全局 toast 防双弹
  const res = await api.get(`/enterprises/${enterpriseId}/risk-assessment/versions`, config);
  return res.data.data;
}

export async function rollbackRiskAssessmentVersion(enterpriseId: string, versionId: string, config?: AxiosRequestConfig): Promise<{ message: string; current_version: number }> {
  // RiskAssessmentPreview 回滚失败自带 message.error，跳过全局 toast 防双弹
  const res = await api.post(`/enterprises/${enterpriseId}/risk-assessment/versions/${versionId}/rollback`, {}, config);
  return res.data;
}

export function generateRiskAssessmentStream(
  enterpriseId: string,
  onEvent: (event: SSEEvent) => void,
  onError: (error: string) => void,
  customInstruction: string | undefined, onComplete: () => void
): AbortController {
  const controller = new AbortController();
  const token = localStorage.getItem("access_token");

  fetch(`/api/v1/enterprises/${enterpriseId}/risk-assessment/generate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ custom_instruction: customInstruction || null }),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const err = await response.json().catch(() => ({ message: "生成请求失败" }));
        onError(err.message || err.detail || "生成请求失败");
        return;
      }
      const reader = response.body?.getReader();
      if (!reader) { onError("无法读取响应流"); return; }
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) { onComplete(); break; }
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const jsonStr = line.replace(/^(?:data: )+/, ""); const event: SSEEvent = JSON.parse(jsonStr);
              onEvent(event);
            } catch { /* skip */ }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        onError(err.message || "网络错误");
      }
    });

  return controller;
}


export async function mergeRiskAssessment(
  enterpriseId: string,
  chapters: { key: string; title: string; content: string }[],
  config?: AxiosRequestConfig
): Promise<{ report_id: string; title: string; status: string }> {
  // RiskAssessmentTab 合并失败自带 message.error，跳过全局 toast 防双弹
  const res = await api.post(
    `/enterprises/${enterpriseId}/risk-assessment/merge`,
    { custom_instruction: JSON.stringify(chapters) },
    config
  );
  return res.data.data;
}

export interface ChapterDef {
  key: string;
  title: string;
}

export async function getRiskAssessmentChapters(enterpriseId: string): Promise<ChapterDef[]> {
  const res = await api.get<ApiResponse<ChapterDef[]>>(`/enterprises/${enterpriseId}/risk-assessment/chapters`);
  return res.data.data;
}
