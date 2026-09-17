import api from "./api";
import type { ApiResponse } from "@/types/common";
import type {
  ConfirmResult,
  IngestItem,
  IngestJob,
  IngestSource,
  SkipResult,
} from "@/types/ingest";

const BASE = "/ingest";

export const listSources = () =>
  api.get<ApiResponse<IngestSource[]>>(`${BASE}/sources`).then((r) => r.data.data);

export const createSource = (payload: Partial<IngestSource>) =>
  api.post<ApiResponse<IngestSource>>(`${BASE}/sources`, payload).then((r) => r.data.data);

export const listJobs = (sourceId?: string) =>
  api
    .get<ApiResponse<IngestJob[]>>(`${BASE}/jobs`, {
      params: sourceId ? { source_id: sourceId } : undefined,
    })
    .then((r) => r.data.data);

export const listItems = (jobId: string, status?: string) =>
  api
    .get<ApiResponse<IngestItem[]>>(`${BASE}/items`, {
      params: { job_id: jobId, status },
    })
    .then((r) => r.data.data);

export const confirmItems = (itemIds: string[]) =>
  api
    .post<ApiResponse<ConfirmResult>>(`${BASE}/items/confirm`, { item_ids: itemIds })
    .then((r) => r.data.data);

export const skipItems = (itemIds: string[]) =>
  api
    .post<ApiResponse<SkipResult>>(`${BASE}/items/skip`, { item_ids: itemIds })
    .then((r) => r.data.data);
