import type { ResourceInvestigationReport, ResourceInvestigationPreview } from "@/types/resourceInvestigation";
import type { SSEEvent } from "@/types/riskAssessment";
import type { ChapterDef } from '@/services/riskAssessmentService';
import api from "./api";

export async function getResourceInvestigation(enterpriseId: string): Promise<ResourceInvestigationReport> {
  const res = await api.get(`/enterprises/${enterpriseId}/resource-investigation`);
  return res.data.data;
}

export async function getResourceInvestigationSummary(enterpriseId: string): Promise<ResourceInvestigationReport["summary"]> {
  const res = await api.get(`/enterprises/${enterpriseId}/resource-investigation/summary`);
  return res.data.data;
}

export async function getResourceInvestigationPreview(enterpriseId: string): Promise<ResourceInvestigationPreview> {
  const res = await api.get(`/enterprises/${enterpriseId}/resource-investigation/preview`);
  return res.data.data;
}

export async function downloadResourceInvestigation(enterpriseId: string): Promise<void> {
  const token = localStorage.getItem("access_token");
  const url = `/api/v1/enterprises/${enterpriseId}/resource-investigation/export?token=${token}`;
  const resp = await fetch(url);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: "download failed" }));
    throw new Error(err.detail || err.message || "download failed");
  }
  const blob = await resp.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "resource_investigation_report.docx";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
}

export function generateResourceInvestigationStream(
  enterpriseId: string,
  customInstruction?: string,
  onEvent: (event: SSEEvent) => void,
  onError: (error: string) => void,
  onComplete: () => void
): AbortController {
  const controller = new AbortController();
  const token = localStorage.getItem("access_token");

  fetch(`/api/v1/enterprises/${enterpriseId}/resource-investigation/generate`, {
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


export async function mergeResourceInvestigation(
  enterpriseId: string,
  chapters: { key: string; title: string; content: string }[]
): Promise<{ report_id: string; title: string; status: string }> {
  const res = await api.post(
    `/enterprises/${enterpriseId}/resource-investigation/merge`,
    { custom_instruction: JSON.stringify(chapters) }
  );
  return res.data.data;
}

export async function getResourceInvestigationChapters(enterpriseId: string): Promise<ChapterDef[]> {
  const res = await api.get<ApiResponse<ChapterDef[]>>(`/enterprises/${enterpriseId}/resource-investigation/chapters`);
  return res.data.data;
}