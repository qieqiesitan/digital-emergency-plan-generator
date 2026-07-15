import api from "./api";
import type {
  RegulationNode, RegulationListParams, RegulationListResponse,
  RegulationParseResult, RegulationCreateRequest, RegulationStats,
  RegulationGraphData, HistoryEvent, SourceFile,
  DuplicateCheckResponse, ImpactResponse, BatchAbolishResponse,
} from "@/types/regulation";

export async function fetchRegulations(params: RegulationListParams = {}): Promise<RegulationListResponse> {
  const res = await api.get("/regulations", { params });
  return res.data.data;
}

export async function fetchRegulation(id: string): Promise<RegulationNode> {
  const res = await api.get(`/regulations/${id}`);
  return res.data.data;
}

export async function parseRegulation(rawText?: string, file?: File): Promise<RegulationParseResult> {
  if (file) {
    const fd = new FormData();
    fd.append("file", file);
    if (rawText) fd.append("raw_text", rawText);
    const res = await api.post("/regulations/parse", fd);
    return res.data.data;
  }
  const res = await api.post("/regulations/parse", { content: rawText || "" });
  return res.data.data;
}

export async function createRegulation(data: RegulationCreateRequest, file?: File, force = false): Promise<{ id: string; message: string }> {
  const fd = new FormData();
  fd.append("data", JSON.stringify(data));
  if (file) fd.append("file", file);
  if (force) fd.append("force", "true");
  const res = await api.post("/regulations", fd);
  return res.data.data;
}
export async function updateRegulation(id: string, data: RegulationCreateRequest, file?: File): Promise<void> {
  const fd = new FormData();
  fd.append("data", JSON.stringify(data));
  if (file) fd.append("file", file);
  await api.put(`/regulations/${id}`, fd);
}

export async function deleteRegulation(id: string): Promise<void> {
  await api.delete(`/regulations/${id}`);
}

export async function abolishRegulation(id: string, replacedBy: string): Promise<void> {
  await api.post(`/regulations/${id}/abolish`, { replaced_by: replacedBy });
}

export async function fetchRegulationGraph(): Promise<RegulationGraphData> {
  const res = await api.get("/regulations/graph/data");
  return res.data.data;
}

export async function fetchStats(): Promise<RegulationStats> {
  const res = await api.get("/regulations/stats/data");
  return res.data.data;
}

export async function rebuildIndex(): Promise<{ total_articles: number; status: string; duration_seconds: number }> {
  const res = await api.post("/regulations/rebuild-index");
  return res.data.data;
}

export async function fetchRegulationHistory(id: string): Promise<{ items: HistoryEvent[]; total: number }> {
  const res = await api.get(`/regulations/${id}/history`);
  return res.data.data;
}

export async function fetchGlobalHistory(action?: string, limit = 50, offset = 0): Promise<{ items: HistoryEvent[]; total: number }> {
  const res = await api.get("/regulations/history/global", { params: { action, limit, offset } });
  return res.data.data;
}

export async function fetchSourceVersions(id: string): Promise<SourceFile[]> {
  const res = await api.get(`/regulations/${id}/source/versions`);
  return res.data.data;
}

export function getSourceDownloadUrl(id: string, filename?: string): string {
  const params = filename ? `?filename=${encodeURIComponent(filename)}` : "";
  return `/api/v1/regulations/${id}/source${params}`;
}

export async function updateTopics(id: string, topics: string[]): Promise<void> {
  await api.put(`/regulations/${id}/topics`, { topics });
}

export async function checkDuplicate(code: string, full_name: string, raw_text?: string): Promise<DuplicateCheckResponse> {
  const res = await api.post("/regulations/check-duplicate", { code, full_name, raw_text });
  return res.data.data;

}
export async function fetchImpact(id: string): Promise<ImpactResponse> {
  const res = await api.get(`/regulations/${id}/impact`);
  return res.data.data;
}

export async function batchAbolish(ids: string[]): Promise<BatchAbolishResponse> {
  const res = await api.post("/regulations/batch/abolish", { ids });
  return res.data.data;
}

