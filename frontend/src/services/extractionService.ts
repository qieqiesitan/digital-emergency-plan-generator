import api from "./api";
import type { ApiResponse } from "@/types/common";

const BASE = "/extraction";

export const parseFile = (file: File) => {
  const fd = new FormData();
  fd.append("file", file);
  return api
    .post<ApiResponse<{ filename: string; chars: number; text: string }>>(
      `${BASE}/parse-file`,
      fd,
    )
    .then((r) => r.data.data);
};

export const suggestMapping = (headers: string[], targetEntity: string) =>
  api
    .post<ApiResponse<{ mapping: Record<string, string>; source: "ai" | "exact" }>>(
      `${BASE}/suggest-mapping`,
      { headers, target_entity: targetEntity },
    )
    .then((r) => r.data.data);

export const runExtraction = (payload: {
  job_id: string;
  source_id: string;
  target_entity: string;
  text: string;
  filename: string;
}) =>
  api
    .post<ApiResponse<{ queued: number; skipped: number; invalid: number }>>(
      `${BASE}/run`,
      payload,
    )
    .then((r) => r.data.data);
