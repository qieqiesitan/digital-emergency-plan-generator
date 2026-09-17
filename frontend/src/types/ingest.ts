export interface IngestSource {
  id: string;
  source_type: "file" | "sheet" | "api_push" | "api_pull" | "manual";
  name: string;
  config: Record<string, unknown>;
  secret_ref?: string | null;
  target_entity?: string | null;
  is_active: boolean;
  created_at?: string | null;
}

export interface IngestJob {
  id: string;
  source_id?: string | null;
  trigger: string;
  status: "running" | "succeeded" | "failed" | "partial";
  total: number;
  imported: number;
  skipped: number;
  failed: number;
  pending_review: number;
  error_summary?: string | null;
  created_at?: string | null;
}

export interface IngestItem {
  id: string;
  job_id: string;
  target_entity: string;
  status: "pending" | "imported" | "skipped" | "failed" | "needs_review";
  confidence: "high" | "medium" | "low";
  source_locator?: string | null;
  raw_payload: Record<string, unknown>;
  error?: string | null;
  review_note?: string | null;
  /** 后端给的建议默认勾选状态：仅 high/medium 且 pending 时为 true */
  default_checked: boolean;
}

export interface ConfirmResult {
  confirmed: number;
  failed: Array<{ item_id: string; reason: string }>;
}

export interface SkipResult {
  skipped: number;
}
