import api from "./api";
import type { AxiosResponse } from "axios";
import type { ApiResponse } from "@/types/common";
import { filenameFromContentDisposition } from "@/utils/download";
import { errorMessage } from "@/utils/apiError";
import type {
  AiPrefillResult,
  ApprovalNodePreview,
  BatchDetail,
  BatchSubmitAllResult,
  BatchTicketSpec,
  FieldMeta,
  GasTestPayload,
  LastTicketSummary,
  LocationTree,
  MeasureMeta,
  OpenTicketPayload,
  PrefillPayload,
  SubmitResult,
  WorkTicketBatch,
  WorkTicketDetail,
  WorkTicketInstance,
  WorkTicketTemplate,
} from "@/types/workTicket";

// api.ts 的 baseURL 已含 /api/v1，故此处只写业务路径
const BASE = "/work-ticket";

export const listTemplates = () =>
  api
    .get<ApiResponse<WorkTicketTemplate[]>>(`${BASE}/templates`)
    .then((r) => r.data.data);

/**
 * 开票前审批链预检：返回每个节点要求的岗位与当前企业匹配到的人数。
 * eligible_count = 0 表示该节点无人可签（票提交后会卡在审批中）。
 */
export const getApprovalPreview = (enterpriseId: string, templateId: string) =>
  api
    .get<ApiResponse<ApprovalNodePreview[]>>(`${BASE}/approval-preview`, {
      params: { enterprise_id: enterpriseId, template_id: templateId },
    })
    .then((r) => r.data.data);

/** 确定性预填：按来源优先级带出票面字段（进向导即调，不触发 AI）。 */
export const getPrefill = (params: {
  enterprise_id: string;
  template_id: string;
  level?: string | null;
  risk_object_id?: string | null;
  fire_method?: string | null;
  /** 作业情景 JSON 字符串（勾选=true；已声明核实时未勾选项=false）。 */
  scenario?: string | null;
}) =>
  api
    .get<ApiResponse<PrefillPayload>>(`${BASE}/prefill`, { params })
    .then((r) => r.data.data);

/** 上次同类票摘要（供"参考上次"入口）。 */
export const getLastTicket = (enterpriseId: string, templateId: string) =>
  api
    .get<ApiResponse<LastTicketSummary | null>>(`${BASE}/last-ticket`, {
      params: { enterprise_id: enterpriseId, template_id: templateId },
    })
    .then((r) => r.data.data);

/** 作业地点候选：楼层 → 区域 → 对象。 */
export const listLocations = (enterpriseId: string) =>
  api
    .get<ApiResponse<LocationTree>>(`${BASE}/locations`, {
      params: { enterprise_id: enterpriseId },
    })
    .then((r) => r.data.data);

/**
 * AI 预填：用户显式点击才调；后端未配置/停用/超时会返回 available:false，
 * 故这里跳过全局错误 toast，由调用方按 available 决定提示。
 */
export const aiPrefill = (payload: {
  enterprise_id: string;
  ticket_type: string;
  level?: string | null;
  work_content?: string | null;
}) =>
  api
    .post<ApiResponse<AiPrefillResult>>(`${BASE}/ai/prefill`, payload, {
      skipGlobalError: true,
    })
    .then((r) => r.data.data);

/** 草稿保存（仅 draft 状态）。 */
export const saveDraft = (
  ticketId: string,
  payload: {
    values: Record<string, unknown>;
    values_meta: Record<string, FieldMeta>;
    measures_meta: Record<string, MeasureMeta>;
  },
) =>
  api
    .patch<ApiResponse<WorkTicketInstance>>(`${BASE}/tickets/${ticketId}`, payload)
    .then((r) => r.data.data);

// ── 作业包（一次检修的批量开票） ──────────────────────────────────────────

export const createBatch = (payload: {
  enterprise_id: string;
  title: string;
  floor_id?: string | null;
  zone_id?: string | null;
  risk_object_id?: string | null;
  location_text?: string | null;
  work_period_start?: string | null;
  work_period_end?: string | null;
  shared_values?: Record<string, unknown>;
  content_base?: string | null;
  risk_basis?: string | null;
}) =>
  api
    .post<ApiResponse<WorkTicketBatch>>(`${BASE}/batches`, payload)
    .then((r) => r.data.data);

export const listBatches = (enterpriseId: string, status?: string) =>
  api
    .get<ApiResponse<WorkTicketBatch[]>>(`${BASE}/batches`, {
      params: { enterprise_id: enterpriseId, status },
    })
    .then((r) => r.data.data);

export const getBatchDetail = (batchId: string) =>
  api
    .get<ApiResponse<BatchDetail>>(`${BASE}/batches/${batchId}`)
    .then((r) => r.data.data);

export const updateBatch = (
  batchId: string,
  payload: Partial<{
    title: string;
    location_text: string | null;
    work_period_start: string | null;
    work_period_end: string | null;
    content_base: string | null;
    risk_basis: string | null;
    shared_values: Record<string, unknown>;
  }>,
) =>
  api
    .patch<ApiResponse<{ affected: number; skipped: number }>>(
      `${BASE}/batches/${batchId}`,
      payload,
    )
    .then((r) => r.data.data);

export const addBatchTickets = (batchId: string, tickets: BatchTicketSpec[]) =>
  api
    .post<ApiResponse<WorkTicketInstance[]>>(`${BASE}/batches/${batchId}/tickets`, {
      tickets,
    })
    .then((r) => r.data.data);

export const removeBatchTicket = (batchId: string, ticketId: string) =>
  api
    .delete<ApiResponse<{ removed: string; affected: number }>>(
      `${BASE}/batches/${batchId}/tickets/${ticketId}`,
    )
    .then((r) => r.data.data);

export const addPackageGasTest = (batchId: string, payload: GasTestPayload) =>
  api
    .post(`${BASE}/batches/${batchId}/gas-tests`, payload)
    .then((r) => r.data.data);

export const submitBatchAll = (batchId: string) =>
  api
    .post<ApiResponse<BatchSubmitAllResult>>(`${BASE}/batches/${batchId}/submit-all`, {}, {
      skipGlobalError: true,
    })
    .then((r) => r.data.data);

export const transitionBatch = (batchId: string, action: "close" | "cancel") =>
  api
    .post<ApiResponse<WorkTicketBatch>>(`${BASE}/batches/${batchId}/transition`, { action }, {
      skipGlobalError: true,
    })
    .then((r) => r.data.data);

export const listTickets = (
  enterpriseId: string,
  filters?: { ticket_type?: string; status?: string; assigned_to_me?: boolean },
) =>
  api
    .get<ApiResponse<WorkTicketInstance[]>>(`${BASE}/tickets`, {
      params: {
        enterprise_id: enterpriseId,
        ticket_type: filters?.ticket_type,
        status: filters?.status,
        // 绑定为审批成员时后端会强制按人收窄；企业主可用它过滤"轮到我签"的票
        assigned_to_me: filters?.assigned_to_me || undefined,
      },
    })
    .then((r) => r.data.data);

export const getTicketDetail = (ticketId: string) =>
  api
    .get<ApiResponse<WorkTicketDetail>>(`${BASE}/tickets/${ticketId}`)
    .then((r) => r.data.data);

export const openTicket = (payload: OpenTicketPayload) =>
  api
    .post<ApiResponse<WorkTicketInstance>>(`${BASE}/tickets`, payload, {
      skipGlobalError: true,
    })
    .then((r) => r.data.data);

export const addGasTest = (ticketId: string, payload: GasTestPayload) =>
  api.post(`${BASE}/tickets/${ticketId}/gas-tests`, payload).then((r) => r.data.data);

/**
 * 提交审批。校验失败时后端返回 422 + 问题清单，页面要逐条展示，
 * 故跳过全局错误 toast，由调用方读 detail。
 */
export const submitTicket = (ticketId: string) =>
  api
    .post<ApiResponse<SubmitResult>>(
      `${BASE}/tickets/${ticketId}/submit`,
      undefined,
      { skipGlobalError: true },
    )
    .then((r) => r.data.data);

export const actOnNode = (
  ticketId: string,
  payload: { action: "approve" | "reject"; opinion?: string },
) =>
  api
    .post<ApiResponse<SubmitResult>>(
      `${BASE}/tickets/${ticketId}/node-action`,
      payload,
      { skipGlobalError: true },
    )
    .then((r) => r.data.data);

/**
 * 生命周期推进（企业主）：开始作业 / 完工 / 归档 / 作废。
 * 与审批节点动作（actOnNode）语义不同：这里推进的是作业过程状态。
 */
export const transitionTicket = (
  ticketId: string,
  payload: { action: "start" | "finish" | "close" | "cancel"; opinion?: string },
) =>
  api
    .post<ApiResponse<{ instance_id: string; action: string; from_status: string; status: string }>>(
      `${BASE}/tickets/${ticketId}/transition`,
      payload,
      { skipGlobalError: true },
    )
    .then((r) => r.data.data);

/** 从 axios 错误里取后端可读文案（提交/审批失败时用）。 */
export function errorDetail(err: unknown, fallback: string): string {
  // 委托给统一实现：它同时认字符串 detail 与 pydantic 校验数组（422 的常见形态）
  return errorMessage(err, fallback);
}

/**
 * responseType=blob 时后端返回的错误体也是 Blob，先把里面的 detail 读出来，
 * 读不到再退回通用话术，避免把 "[object Blob]" 抛给用户。
 */
async function blobErrorDetail(err: unknown, fallback: string): Promise<string> {
  const data = (err as { response?: { data?: unknown } })?.response?.data;
  if (typeof Blob !== "undefined" && data instanceof Blob) {
    try {
      const parsed = JSON.parse(await data.text());
      return parsed?.detail || parsed?.message || fallback;
    } catch {
      return fallback;
    }
  }
  return errorDetail(err, fallback);
}

/**
 * 打印票面（下载 DOCX）。每调用一次后端就固化一个新版本的打印快照，
 * 所以这里不做任何缓存或去重。
 */
export async function downloadTicketDocx(
  ticketId: string,
  fallbackName = "安全作业票",
): Promise<void> {
  let resp: AxiosResponse<Blob>;
  try {
    resp = await api.get<Blob>(`${BASE}/tickets/${ticketId}/print.docx`, {
      responseType: "blob",
      skipGlobalError: true,
    });
  } catch (err) {
    throw new Error(await blobErrorDetail(err, "票面生成失败"), { cause: err });
  }
  const name = filenameFromContentDisposition(
    String(resp.headers?.["content-disposition"] ?? ""),
    `${fallbackName}.docx`,
  );
  const url = URL.createObjectURL(resp.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
