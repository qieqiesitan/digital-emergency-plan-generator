// 隐患排查治理前端类型（与 backend/app/routers/hazard_management.py 端点响应一致）

export type HazardSourceType =
  | "inspection"
  | "report"
  | "regulatory"
  | "accident"
  | "manual";
export type HazardLevel = "major" | "general";
export type HazardStatus =
  | "registered"
  | "grading"
  | "pending_approval"
  | "rectifying"
  | "reviewing"
  | "second_review"
  | "closed";
export type HazardLevelSource = "ai" | "manual";

export interface HazardRecord {
  id: string;
  enterprise_id: string;
  code: string;
  source_type: HazardSourceType;
  source_task_id: string | null;
  source_item_id: string | null;
  object_id: string | null;
  measure_id: string | null;
  title: string;
  description: string;
  photo_urls: string[] | null;
  location: string | null;
  hazard_type: string | null;
  level: HazardLevel | null;
  level_source: HazardLevelSource | null;
  grading_basis: string | null;
  rectification_plan: Record<string, unknown> | null;
  deadline: string | null;
  rectification_user_id: string | null;
  reviewer_user_id: string | null;
  closed_at: string | null;
  status: HazardStatus;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

/** 台账行：记录全部业务字段 + 状态/来源/等级中文标签（GET /records）。 */
export interface HazardRecordListItem extends HazardRecord {
  status_label: string;
  source_type_label: string;
  level_label: string;
}

/** 台账统计（企业全量口径，与驾驶舱一致）：total/open/major/overdue。 */
export interface HazardRecordsStats {
  total: number;
  open: number;
  major: number;
  overdue: number;
}

export interface HazardRecordsResponse {
  items: HazardRecordListItem[];
  stats: HazardRecordsStats | null;
}

export interface HazardRecordCreate {
  source_type: HazardSourceType;
  hazard_type?: string | null;
  object_id?: string | null;
  measure_id?: string | null;
  title: string;
  description: string;
  photo_urls?: string[];
  location?: string | null;
  source_task_id?: string | null;
  source_item_id?: string | null;
}

export interface HazardRectification {
  id: string;
  record_id: string;
  user_id: string | null;
  content: string;
  evidence: string[];
  submitted_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface HazardReview {
  id: string;
  record_id: string;
  review_type: string;
  user_id: string | null;
  result: "pass" | "fail";
  comment: string | null;
  evidence: string[];
  created_at: string;
  updated_at: string;
}

export interface HazardApproval {
  id: string;
  record_id: string;
  user_id: string | null;
  action: "approve" | "reject";
  comment: string | null;
  created_at: string;
  updated_at: string;
}

export interface HazardAuditLog {
  id: string;
  enterprise_id: string;
  record_id: string | null;
  user_id: string | null;
  action: string;
  detail: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/** 隐患单详情：全部业务字段 + 名称 + 时间线（GET /records/{rid}）。 */
export interface HazardRecordDetail extends HazardRecord {
  status_label: string;
  source_type_label: string;
  level_label: string;
  object_name: string | null;
  measure_name: string | null;
  rectifications: HazardRectification[];
  reviews: HazardReview[];
  approvals: HazardApproval[];
  audit_logs: HazardAuditLog[];
}

export interface HazardInspectionPlan {
  id: string;
  enterprise_id: string;
  name: string;
  category: string;
  frequency: string;
  weekdays: number[] | null;
  zone_ids: string[];
  template_id: string | null;
  responsible_user_id: string | null;
  ai_suggestion: Record<string, unknown> | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface HazardInspectionPlanCreate {
  name: string;
  category: string;
  frequency: string;
  weekdays?: number[] | null;
  zone_ids: string[];
  template_id?: string | null;
  responsible_user_id?: string | null;
  ai_suggestion?: Record<string, unknown> | null;
  enabled?: boolean;
}

export type HazardInspectionPlanUpdate = Partial<HazardInspectionPlanCreate>;

export type HazardTaskStatus = "pending" | "processing" | "done" | "overdue";

export interface HazardInspectionItem {
  id: string;
  task_id: string;
  object_id: string | null;
  measure_id: string | null;
  content: string;
  expected_note: string | null;
  result: "pending" | "normal" | "abnormal" | "na";
  remark: string | null;
  photo_urls: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface HazardInspectionTask {
  id: string;
  plan_id: string;
  enterprise_id: string;
  title: string | null;
  status: HazardTaskStatus;
  responsible_user_id: string | null;
  due_at: string;
  completed_at: string | null;
  overdue_notified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface HazardInspectionTaskDetail extends HazardInspectionTask {
  items: HazardInspectionItem[];
}

export interface HazardTaskItemSubmit {
  item_id: string;
  result: string;
  remark?: string | null;
  photo_urls?: string[] | null;
}

export interface HazardTaskSubmitPayload {
  items: HazardTaskItemSubmit[];
}

export interface HazardChecklistTemplateItem {
  content: string;
  expected_note?: string | null;
}

export interface HazardChecklistTemplate {
  id: string;
  enterprise_id: string | null;
  name: string;
  category: string;
  items: HazardChecklistTemplateItem[];
  is_system: boolean;
  source: "system" | "enterprise";
  created_at: string;
  updated_at: string;
}

export interface HazardChecklistTemplateCreate {
  name: string;
  category: string;
  items: HazardChecklistTemplateItem[];
}

export type HazardChecklistTemplateUpdate = Partial<HazardChecklistTemplateCreate>;

export interface HazardNotification {
  id: string;
  enterprise_id: string;
  user_id: string;
  record_id: string | null;
  type: string;
  message: string | null;
  read_at: string | null;
  created_at: string;
  updated_at: string;
}

// ── 驾驶舱（GET /dashboard，任务 11 §12） ──

export interface HazardDashboardMetrics {
  open_hazards: number;
  open_risk_points: number;
  rectification_rate: number | null;
  on_time_closed: number;
  due_this_month: number;
  avg_rectification_days: number | null;
  major_count: number;
  major_approved: number;
  overdue_count: number;
  overdue_records: number;
  overdue_tasks: number;
  monthly_new: number;
  monthly_new_mom: number | null;
  scan_pending: number;
}

export interface HazardDashboardPayload {
  metrics: HazardDashboardMetrics;
  charts: {
    type_distribution: { hazard_type: string; count: number }[];
    monthly_trend: { month: string; count: number }[];
    major_records: {
      code: string;
      title: string;
      deadline: string | null;
      status: string;
    }[];
    enterprise_comparison: {
      enterprise_id: string;
      name: string;
      open_count: number;
    }[];
  };
  unread: {
    total: number;
    mine: number;
    by_type: Record<string, number>;
  };
}

// ── 公示（§11.2/§14） ──

export interface HazardPublicityItem {
  code: string;
  title: string;
  level: string;
  status: string;
  rectification: string;
  source_type: string;
}

export interface HazardPublicityTokenResult {
  token: string;
  link: string;
}

// ── 公开页（免登录，§8 扫码上报 / §11.2 公示公开页） ──

export interface PublicHazardReportPayload {
  title?: string;
  description: string;
  photo_urls?: string[];
  location?: string;
  nonce: string;
}

export interface PublicHazardReportResult {
  message: string;
}

export interface PublicHazardPublicityPayload {
  enterprise_name: string;
  items: HazardPublicityItem[];
  generated_at: string;
  masked: boolean;
}

// ── AI 辅助（§16 失败降级 available:false） ──

export interface HazardRecordAssistResult {
  available: boolean;
  title: string;
  hazard_type: string;
  suggested_level: string;
  reason: string;
  note?: string;
}

export interface HazardAiGradeResult {
  available: boolean;
  suggested_level?: "major" | "general";
  basis?: string;
  confidence?: number;
  note?: string;
}

export interface HazardGovernancePlanResult {
  available: boolean;
  plan?: {
    goal: string;
    measures: string;
    budget: string;
    emergency_measures: string;
    acceptance_criteria: string;
  };
  note?: string;
}

export interface HazardPlanBuilderResult {
  available: boolean;
  plans: Array<{
    name: string;
    category: string;
    frequency: string;
    weekdays?: number[];
    responsible_user_name?: string;
    zone_names?: string[];
  }>;
  note?: string;
}

export interface HazardScheduleSuggestionResult {
  available: boolean;
  suggested_frequency?: string;
  suggested_responsible_user_id?: string | null;
  reason?: string;
  note?: string;
}

export interface HazardChecklistSuggestionResult {
  available: boolean;
  items: Array<{ content: string; expected_note?: string }>;
  note?: string;
}

export interface HazardSetupWizardResult {
  available: boolean;
  org_suggestion?: Record<string, unknown> | null;
  plans_suggestion?: HazardPlanBuilderResult | null;
  checklist_suggestion?: HazardChecklistSuggestionResult | null;
  note?: string;
}

export interface HazardChecklistTemplateAIResult {
  available: boolean;
  items: HazardChecklistTemplateItem[];
  note?: string;
}
