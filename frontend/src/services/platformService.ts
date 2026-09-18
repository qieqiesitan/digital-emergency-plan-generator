import api from "./api";
import type { ApiResponse } from "@/types/common";

// api.ts 的 baseURL 已含 /api/v1，故此处只写业务路径
const BASE = "/platform";

/** AI 能力注册表条目（code 与 llm_call_logs.capability 对齐）。 */
export interface AiCapability {
  id: string;
  code: string;
  module: string;
  name: string;
  description?: string | null;
  prompt_ref?: string | null;
  model_override?: string | null;
  is_enabled: boolean;
  allow_manual: boolean;
}

export interface CapabilityUpdatePayload {
  is_enabled?: boolean;
  allow_manual?: boolean;
  /** 传空字符串表示清空覆盖，交由后端默认模型 */
  model_override?: string | null;
  prompt_ref?: string | null;
}

/** 单个能力的调用统计。 */
export interface CapabilityUsage {
  capability: string;
  calls: number;
  failures: number;
  failure_rate: number;
  truncated: number;
  tokens: number;
  avg_duration_ms: number | null;
}

export interface AiUsage {
  total_calls: number;
  total_tokens: number;
  /** 流被截断的调用数：success 可能仍为 True，但结果是半截的 */
  total_truncated: number;
  by_capability: CapabilityUsage[];
  since?: string;
  days?: number;
}

/** 跨企业总览（平台级视角，非单企业驾驶舱）。 */
export interface PlatformOverview {
  enterprises: number;
  risk_points: number;
  hazards: number;
  major_hazard_units: number;
  major_hazard_level_1_2: number;
  work_tickets: number;
}

export const listCapabilities = () =>
  api.get<ApiResponse<AiCapability[]>>(`${BASE}/capabilities`).then((r) => r.data.data);

export const updateCapability = (code: string, payload: CapabilityUpdatePayload) =>
  api
    .put<ApiResponse<AiCapability>>(`${BASE}/capabilities/${code}`, payload)
    .then((r) => r.data.data);

export const getAiUsage = (days = 30) =>
  api
    .get<ApiResponse<AiUsage>>(`${BASE}/ai-usage`, { params: { days } })
    .then((r) => r.data.data);

export const getPlatformOverview = () =>
  api.get<ApiResponse<PlatformOverview>>(`${BASE}/overview`).then((r) => r.data.data);
