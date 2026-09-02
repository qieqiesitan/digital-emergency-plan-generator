import api from "./api";
import type {
  RegulationNode, RegulationListParams, RegulationListResponse,
  RegulationParseResult, RegulationCreateRequest, RegulationStats,
  RegulationGraphData, HistoryEvent, SourceFile,
  DuplicateCheckResponse, ImpactResponse, BatchAbolishResponse,
} from "@/types/regulation";

import { getApiBaseUrl } from "@/utils/platform";

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
    // RegulationForm 解析失败自带 message.error，跳过全局 toast 防双弹
    const res = await api.post("/regulations/parse", fd, { skipGlobalError: true });
    return res.data.data;
  }
  // RegulationForm 解析失败自带 message.error，跳过全局 toast 防双弹
  const res = await api.post("/regulations/parse", { content: rawText || "" }, { skipGlobalError: true });
  return res.data.data;
}

export async function createRegulation(data: RegulationCreateRequest, file?: File, force = false): Promise<{ id: string; message: string }> {
  const fd = new FormData();
  fd.append("data", JSON.stringify(data));
  if (file) fd.append("file", file);
  if (force) fd.append("force", "true");
  // RegulationForm 入库失败自带 message.error，跳过全局 toast 防双弹
  const res = await api.post("/regulations", fd, { skipGlobalError: true });
  return res.data.data;
}
export async function updateRegulation(id: string, data: RegulationCreateRequest, file?: File): Promise<void> {
  const fd = new FormData();
  fd.append("data", JSON.stringify(data));
  if (file) fd.append("file", file);
  // RegulationForm 更新失败自带 message.error，跳过全局 toast 防双弹
  await api.put(`/regulations/${id}`, fd, { skipGlobalError: true });
}

export async function deleteRegulation(id: string): Promise<void> {
  // RegulationList 删除失败自带 message.error，跳过全局 toast 防双弹
  await api.delete(`/regulations/${id}`, { skipGlobalError: true });
}

export async function abolishRegulation(id: string, replacedBy: string): Promise<void> {
  // AbolishDialog 废止 mutation 自带 message.error，跳过全局 toast 防双弹
  await api.post(`/regulations/${id}/abolish`, { replaced_by: replacedBy }, { skipGlobalError: true });
}

export async function fetchRegulationGraph(): Promise<RegulationGraphData> {
  const res = await api.get("/regulations/graph-data");
  return res.data.data;
}

export async function fetchStats(): Promise<RegulationStats> {
  // RegulationManagePage 自带失败态 Alert+重试（且 30s 自动轮询），跳过全局 toast 防刷屏
  const res = await api.get("/regulations/stats/data", { skipGlobalError: true });
  return res.data.data;
}

export async function rebuildIndex(): Promise<{ total_articles: number; status: string; duration_seconds: number }> {
  // RegulationManagePage 重建索引失败自带 message.error，跳过全局 toast 防双弹
  const res = await api.post("/regulations/rebuild-index", {}, { skipGlobalError: true });
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
  return `${getApiBaseUrl()}/regulations/${id}/source${params}`;
}

export async function fetchSourceFile(id: string, filename?: string): Promise<Blob> {
  const params = filename ? `?filename=${encodeURIComponent(filename)}` : "";
  // RegulationDetail 源文件加载失败自带 message.error；blob 下载失败无统一文案，跳过全局 toast
  const res = await api.get(`/regulations/${id}/source${params}`, { responseType: "blob", skipGlobalError: true });
  return res.data as Blob;
}

export async function updateTopics(id: string, topics: string[]): Promise<void> {
  // RegulationDetail 标签增删静默失败（catch 空处理），跳过全局 toast
  await api.put(`/regulations/${id}/topics`, { topics }, { skipGlobalError: true });
}

export async function checkDuplicate(code: string, full_name: string, raw_text?: string): Promise<DuplicateCheckResponse> {
  // RegulationForm 重复检查失败静默降级为未发现，跳过全局 toast（避免解析成功却弹错）
  const res = await api.post("/regulations/check-duplicate", { code, full_name, raw_text }, { skipGlobalError: true });
  return res.data.data;

}
export async function fetchImpact(id: string): Promise<ImpactResponse> {
  // AbolishDialog 影响查询失败静默降级，跳过全局 toast（页面有加载态与提示区）
  const res = await api.get(`/regulations/${id}/impact`, { skipGlobalError: true });
  return res.data.data;
}

export async function batchAbolish(ids: string[]): Promise<BatchAbolishResponse> {
  // RegulationList 批量废止 mutation 自带 message.error，跳过全局 toast 防双弹
  const res = await api.post("/regulations/batch/abolish", { ids }, { skipGlobalError: true });
  return res.data.data;
}

