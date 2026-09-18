import api from "./api";
import type { AxiosResponse } from "axios";
import type { ApiResponse } from "@/types/common";
import { filenameFromContentDisposition } from "@/utils/download";
import type {
  GasTestPayload,
  OpenTicketPayload,
  SubmitResult,
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

export const listTickets = (
  enterpriseId: string,
  filters?: { ticket_type?: string; status?: string },
) =>
  api
    .get<ApiResponse<WorkTicketInstance[]>>(`${BASE}/tickets`, {
      params: {
        enterprise_id: enterpriseId,
        ticket_type: filters?.ticket_type,
        status: filters?.status,
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

/** 从 axios 错误里取后端可读文案（提交/审批失败时用）。 */
export function errorDetail(err: unknown, fallback: string): string {
  const data = (err as { response?: { data?: { detail?: unknown; message?: unknown } } })
    ?.response?.data;
  const detail = data?.detail ?? data?.message;
  if (typeof detail === "string" && detail.trim()) return detail;
  const message = (err as { message?: string })?.message;
  return message || fallback;
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
