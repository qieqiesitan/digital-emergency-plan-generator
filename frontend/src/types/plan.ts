export type PlanType = "comprehensive" | "special" | "onsite";
export type PlanStatus = "draft" | "generating" | "completed";

export interface PlanProject {
  id: string;
  enterprise_id: string;
  enterprise_name: string;
  plan_type: PlanType;
  title: string;
  accident_type: string | null;
  status: PlanStatus;
  current_version: number;
  sections_count: number;
  completed_sections: number;
  created_at: string;
  updated_at: string;
}

export interface PlanCreate {
  enterprise_id: string;
  plan_type: PlanType;
  title: string;
  accident_type?: string | null;
  style_preference?: Record<string, unknown> | null;
}

export interface PlanUpdate {
  title?: string;
}

export interface PlanSection {
  id: string;
  section_key: string;
  title: string;
  level: number;
  sort_order: number;
  content: string;
  ai_generated: boolean;
  updated_at: string;
}

export interface SectionUpdate {
  content: string;
}

export interface EnterprisePlanSummary {
  enterprise_id: string;
  enterprise_name: string;
  industry: string;
  total: number;
  comprehensive_count: number;
  special_count: number;
  onsite_count: number;
  last_updated: string | null;
}

// ponytail: merged from types/template.ts
export interface SectionTemplate {
  key: string;
  title: string;
  level: number;
  sort_order: number;
  ai_generatable: boolean;
  user_editable: boolean;
  required: boolean;
  auto_fill: boolean;
  auto_fill_source: string | null;
  gb_requirement: string;
  prompt_template: string | null;
  data_dependencies: string[];
  subsections: SectionTemplate[];
}

export interface PlanTemplate {
  id: string;
  plan_type: PlanType;
  name: string;
  version: string;
  structure: SectionTemplate[];
  is_active: boolean;
}

// ponytail: merged from types/version.ts
export interface PlanVersion {
  id: string;
  version_number: number;
  created_by: "auto" | "manual";
  description: string | null;
  is_current?: boolean;
  created_at: string;
}

export interface PlanVersionDetail extends PlanVersion {
  snapshot: Record<string, unknown>;
}

export interface SectionDiff {
  section_key: string;
  title: string;
  change_type: "added" | "removed" | "modified" | "unchanged";
  old_content: string | null;
  new_content: string | null;
}

export interface VersionCompare {
  version_a: number;
  version_b: number;
  diffs: SectionDiff[];
}

// ponytail: merged from types/export.ts
export interface ExportTask {
  task_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  progress: number;
  download_url: string | null;
  error_message: string | null;
}

export interface ExportPreview {
  plan_id: string;
  title: string;
  html: string;
}

export interface ExportValidation {
  valid: boolean;
  issues: Array<{ section_key: string; section_title: string; issue: string }>;
  warnings: string[];
}

// ponytail: merged from types/generation.ts
export interface GenerateRequest {
  section_key: string;
  custom_instruction?: string | null;
}

export interface GenerateBatchRequest {
  section_keys?: string[] | null;
}

export type SSEEventType = "chunk" | "done" | "error" | "progress" | "section_done" | "batch_done" | "token" | "chapter_start" | "chapter_end" | "complete";

export interface SSEEvent {
  type: SSEEventType;
  content?: string;
  message?: string;
  section_key?: string;
  current?: number;
  total?: number;
  completed?: number;
  failed?: number;
  chapter?: string;
  token?: string;
  chunk?: string;
  chapters?: Array<{ key: string; title: string; content: string }>;
}