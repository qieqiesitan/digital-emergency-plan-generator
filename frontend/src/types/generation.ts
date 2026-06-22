export interface GenerateRequest {
  section_key: string;
  custom_instruction?: string | null;
}

export interface GenerateBatchRequest {
  section_keys?: string[] | null;
}

export type SSEEventType = "chunk" | "done" | "error" | "progress" | "section_done" | "batch_done";

export interface SSEEvent {
  type: SSEEventType;
  content?: string;
  message?: string;
  section_key?: string;
  current?: number;
  total?: number;
  completed?: number;
  failed?: number;
}
