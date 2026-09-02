import api from "./api";
import type { AxiosRequestConfig } from "axios";
import type { ApiResponse } from "@/types/common";
import type {
  AiSignReviewResponse,
  CardData,
  CardSummary,
  RightColumn,
  SnapshotInfo,
} from "@/types/riskNoticeCard";

const BASE = (enterpriseId: string) => `/enterprises/${enterpriseId}/risk-notice-cards`;

export interface CardListParams {
  level?: string;
  zone_id?: string;
  keyword?: string;
}

/** 摘要列表（支持 level/zone_id/keyword 筛选）。 */
export const fetchCardSummaries = (enterpriseId: string, params: CardListParams = {}) =>
  // RiskNoticeCardPage isError 已自带 toast + 空态文案，跳过全局 toast 防双弹
  api.get<ApiResponse<CardSummary[]>>(`${BASE(enterpriseId)}`, { params, skipGlobalError: true }).then(r => r.data.data);

/** 单卡详情（快照优先）。 */
export const fetchCardDetail = (enterpriseId: string, objectId: string) =>
  api.get<ApiResponse<CardData>>(`${BASE(enterpriseId)}/${objectId}`).then(r => r.data.data);

/** 批量导出 Word，返回 { file_key, warnings }（下载走 /export/download/{file_key}）。 */
export const exportCards = (enterpriseId: string, objectIds: string[], config?: AxiosRequestConfig) => {
  const body = { object_ids: objectIds };
  const req = config
    ? api.post<ApiResponse<{ file_key: string; warnings: string[] }>>(`${BASE(enterpriseId)}/export`, body, config)
    : api.post<ApiResponse<{ file_key: string; warnings: string[] }>>(`${BASE(enterpriseId)}/export`, body);
  return req.then(r => r.data.data);
};

/** AI 优化（无副作用）：返回原版与优化版右栏对比。 */
export const aiOptimize = (enterpriseId: string, objectId: string, config?: AxiosRequestConfig) => {
  const req = config
    ? api.post<ApiResponse<{ original: RightColumn; optimized: RightColumn }>>(
        `${BASE(enterpriseId)}/${objectId}/ai-optimize`,
        {},
        config,
      )
    : api.post<ApiResponse<{ original: RightColumn; optimized: RightColumn }>>(
        `${BASE(enterpriseId)}/${objectId}/ai-optimize`,
      );
  return req.then(r => r.data.data);
};

/** AI 标志审查（无副作用）：返回当前标志与 AI 增删建议。 */
export const aiReviewSigns = (enterpriseId: string, objectId: string, config?: AxiosRequestConfig) => {
  const req = config
    ? api.post<ApiResponse<AiSignReviewResponse>>(
        `${BASE(enterpriseId)}/${objectId}/ai-review-signs`,
        {},
        config,
      )
    : api.post<ApiResponse<AiSignReviewResponse>>(`${BASE(enterpriseId)}/${objectId}/ai-review-signs`);
  return req.then(r => r.data.data);
};

/** 保存 AI 快照，返回新版本号（source=ai）。 */
export const saveSnapshot = (enterpriseId: string, objectId: string, content: RightColumn, config?: AxiosRequestConfig) => {
  const req = config
    ? api.put<ApiResponse<SnapshotInfo>>(`${BASE(enterpriseId)}/${objectId}/snapshot`, { content }, config)
    : api.put<ApiResponse<SnapshotInfo>>(`${BASE(enterpriseId)}/${objectId}/snapshot`, { content });
  return req.then(r => r.data.data);
};

/** 重置公开 token，返回新的公开页 URL。 */
export const resetToken = (enterpriseId: string, objectId: string) =>
  api
    .post<ApiResponse<{ public_url: string }>>(`${BASE(enterpriseId)}/${objectId}/token/reset`)
    .then(r => r.data.data.public_url);

/** 公开只读卡片（无鉴权）。 */
export const fetchPublicCard = (token: string) =>
  api.get<ApiResponse<CardData>>(`/public/risk-notice-cards/${token}`).then(r => r.data.data);
