import type { ApiResponse } from '@/types/common';
import type { RiskAssessmentReport, RiskAssessmentPreview, ReportVersionItem, SSEEvent } from "@/types/riskAssessment";
import type { ReportIssue } from "@/types/reportWorkspace";
import api from "./api";
import { dedupeInflight } from "./inflight";
import type { AxiosRequestConfig } from "axios";
import { filenameFromContentDisposition } from "@/utils/download";

/**
 * 读取企业当前的风险评估报告；**尚未生成时返回 null**（后端 200 + data=null 表达空态，
 * 见 backend/app/routers/risk_assessment.py）。调用方按空态渲染，而不是当异常处理。
 */
export async function getRiskAssessment(
  enterpriseId: string,
  config?: AxiosRequestConfig,
): Promise<RiskAssessmentReport | null> {
  // 并发同名请求合并：开发期 StrictMode 双挂载会把首屏这个请求发两次（控制台两份重复报错）。
  // 注意这里**不**默认 skipGlobalError：真正的故障（500/无权）仍要走全局提示；「报告还没生成」
  // 已经不是错误了（后端返回 200 + null），需要自行提示失败态的调用方再显式传 skipGlobalError。
  return dedupeInflight(`risk-assessment:${enterpriseId}`, async () => {
    const res = await api.get(`/enterprises/${enterpriseId}/risk-assessment`, {
      ...config,
    });
    return (res.data.data as RiskAssessmentReport | null) ?? null;
  });
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
  const name = filenameFromContentDisposition(
    resp.headers.get("content-disposition") || "",
    "risk_assessment_report.docx",
  );
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = name;
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
  customInstruction: string | undefined,
  onEvent: (event: SSEEvent) => void,
  onError: (error: string) => void,
  onComplete: () => void,
): AbortController {
  return ssePost(
    `/api/v1/enterprises/${enterpriseId}/risk-assessment/generate`,
    { custom_instruction: customInstruction || null },
    { onEvent, onError, onComplete },
  );
}

interface SSEPostCallbacks {
  onEvent: (event: SSEEvent) => void;
  onError: (error: string) => void;
  onComplete: () => void;
}

function ssePost(
  path: string,
  body: Record<string, unknown>,
  cb: SSEPostCallbacks,
): AbortController {
  const controller = new AbortController();
  const token = localStorage.getItem("access_token");

  fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const err = await response.json().catch(() => ({ message: "生成请求失败" }));
        cb.onError(err.message || err.detail || "生成请求失败");
        return;
      }
      const reader = response.body?.getReader();
      if (!reader) { cb.onError("无法读取响应流"); return; }
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) { cb.onComplete(); break; }
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const jsonStr = line.replace(/^(?:data: )+/, "");
              const event: SSEEvent = JSON.parse(jsonStr);
              cb.onEvent(event);
            } catch { /* skip */ }
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        cb.onError(err.message || "网络错误");
      }
    });

  return controller;
}

export function generateRiskAssessmentSectionStream(
  enterpriseId: string,
  chapterKey: string,
  cb: {
    onEvent: (event: SSEEvent) => void;
    onError: (error: string) => void;
    onComplete: () => void;
  },
): AbortController {
  return ssePost(
    `/api/v1/enterprises/${enterpriseId}/risk-assessment/generate/section`,
    { chapter_key: chapterKey },
    cb,
  );
}

export async function saveRiskAssessmentSection(
  enterpriseId: string,
  chapterKey: string,
  content: string,
): Promise<void> {
  await api.put(`/enterprises/${enterpriseId}/risk-assessment/sections/${chapterKey}`, { content });
}

export async function reviewRiskAssessment(
  enterpriseId: string,
  sectionKeys: string[] | null = null,
): Promise<ReportIssue[]> {
  const res = await api.post(`/enterprises/${enterpriseId}/risk-assessment/review`, { section_keys: sectionKeys });
  return res.data.data.issues;
}

export async function applyRiskAssessmentReview(
  enterpriseId: string,
  sectionKeys: string[],
): Promise<Array<{ section_key: string; title: string; original: string; revised: string }>> {
  const res = await api.post(`/enterprises/${enterpriseId}/risk-assessment/review/apply`, { section_keys: sectionKeys });
  return res.data.data.applied;
}

export async function getRiskAssessmentStyle(
  enterpriseId: string,
): Promise<Record<string, string>> {
  const res = await api.get(`/enterprises/${enterpriseId}/risk-assessment/style`);
  return res.data.data.style_preference || {};
}

export async function saveRiskAssessmentStyle(
  enterpriseId: string,
  style: Record<string, string>,
): Promise<void> {
  await api.put(`/enterprises/${enterpriseId}/risk-assessment/style`, { style_preference: style });
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
