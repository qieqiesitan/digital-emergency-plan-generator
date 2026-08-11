import api from "./api";
import type { ApiResponse } from "@/types/common";
import type { CardData, CardSummary, RightColumn, SnapshotInfo } from "@/types/riskNoticeCard";

const BASE = (enterpriseId: string) => `/enterprises/${enterpriseId}/risk-notice-cards`;

export interface CardListParams {
  level?: string;
  zone_id?: string;
  keyword?: string;
}

/** 摘要列表（支持 level/zone_id/keyword 筛选）。 */
export const fetchCardSummaries = (enterpriseId: string, params: CardListParams = {}) =>
  api.get<ApiResponse<CardSummary[]>>(`${BASE(enterpriseId)}`, { params }).then(r => r.data.data);

/** 单卡详情（快照优先）。 */
export const fetchCardDetail = (enterpriseId: string, objectId: string) =>
  api.get<ApiResponse<CardData>>(`${BASE(enterpriseId)}/${objectId}`).then(r => r.data.data);

/** 批量导出 Word，返回 file_key（下载走 /export/download/{file_key}）。 */
export const exportCards = (enterpriseId: string, objectIds: string[]) =>
  api
    .post<ApiResponse<{ file_key: string; warnings: string[] }>>(`${BASE(enterpriseId)}/export`, {
      object_ids: objectIds,
    })
    .then(r => r.data.data.file_key);

/** AI 优化（无副作用）：返回原版与优化版右栏对比。 */
export const aiOptimize = (enterpriseId: string, objectId: string) =>
  api
    .post<ApiResponse<{ original: RightColumn; optimized: RightColumn }>>(
      `${BASE(enterpriseId)}/${objectId}/ai-optimize`,
    )
    .then(r => r.data.data);

/** 保存 AI 快照，返回新版本号（source=ai）。 */
export const saveSnapshot = (enterpriseId: string, objectId: string, content: RightColumn) =>
  api
    .put<ApiResponse<SnapshotInfo>>(`${BASE(enterpriseId)}/${objectId}/snapshot`, { content })
    .then(r => r.data.data);

/** 重置公开 token，返回新的公开页 URL。 */
export const resetToken = (enterpriseId: string, objectId: string) =>
  api
    .post<ApiResponse<{ public_url: string }>>(`${BASE(enterpriseId)}/${objectId}/token/reset`)
    .then(r => r.data.data.public_url);

/** 公开只读卡片（无鉴权）。 */
export const fetchPublicCard = (token: string) =>
  api.get<ApiResponse<CardData>>(`/public/risk-notice-cards/${token}`).then(r => r.data.data);
