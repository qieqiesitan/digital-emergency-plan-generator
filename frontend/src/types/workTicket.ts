/**
 * 作业票（特殊作业票）类型与常量。
 *
 * 审批人表取自 GB 30871-2022 附录B 表B.1，与后端 seed_work_ticket_templates.py 的
 * APPROVAL_MATRIX 同源。前端留一份是为了兑现"级别一选、审批链自动定"——
 * 向导第 1 步选完级别就能立刻告诉用户要经过谁，不必为此多打一次接口。
 */

export type WorkTicketTypeCode =
  | "DHZY"
  | "YXKJ"
  | "MBCD"
  | "GCZY"
  | "QZDZ"
  | "LSYD"
  | "PTZY"
  | "DLZY";

export const TICKET_TYPE_LABEL: Record<WorkTicketTypeCode, string> = {
  DHZY: "动火作业",
  YXKJ: "受限空间作业",
  MBCD: "盲板抽堵作业",
  GCZY: "高处作业",
  QZDZ: "吊装作业",
  LSYD: "临时用电作业",
  PTZY: "动土作业",
  DLZY: "断路作业",
};

export const ALL_TICKET_TYPES: { code: WorkTicketTypeCode; label: string }[] = [
  { code: "DHZY", label: "动火作业" },
  { code: "YXKJ", label: "受限空间作业" },
  { code: "MBCD", label: "盲板抽堵作业" },
  { code: "GCZY", label: "高处作业" },
  { code: "QZDZ", label: "吊装作业" },
  { code: "LSYD", label: "临时用电作业" },
  { code: "PTZY", label: "动土作业" },
  { code: "DLZY", label: "断路作业" },
];

/** 仅动火与受限空间强制气体检测（GB 30871-2022 第 5、6 章）。 */
export const GAS_TEST_REQUIRED_TYPES: WorkTicketTypeCode[] = ["DHZY", "YXKJ"];

export const FIRE_LEVELS = ["特级", "一级", "二级"] as const;

/** GB 30871-2022 附录B 表B.1 的审批人（展示用；开票向导以模板流程节点为准）。 */
export const APPROVAL_MATRIX: {
  code: WorkTicketTypeCode;
  level: string | null;
  approver: string;
}[] = [
  { code: "DHZY", level: "特级", approver: "主管领导" },
  { code: "DHZY", level: "一级", approver: "安全管理部门" },
  { code: "DHZY", level: "二级", approver: "所在基层单位" },
  { code: "YXKJ", level: null, approver: "所在基层单位" },
  { code: "MBCD", level: null, approver: "所在基层单位" },
  { code: "GCZY", level: "Ⅰ级", approver: "所在基层单位" },
  { code: "GCZY", level: "Ⅱ级", approver: "所在单位专业部门" },
  { code: "GCZY", level: "Ⅲ级", approver: "所在单位专业部门" },
  { code: "GCZY", level: "Ⅳ级", approver: "主管厂长或总工程师" },
  { code: "QZDZ", level: "一级", approver: "主管厂长或总工程师" },
  { code: "QZDZ", level: "二级", approver: "所在单位专业部门" },
  { code: "QZDZ", level: "三级", approver: "所在单位专业部门" },
  { code: "LSYD", level: null, approver: "配送电单位" },
  { code: "PTZY", level: null, approver: "所在单位专业部门" },
  { code: "DLZY", level: null, approver: "所在单位专业部门" },
];

/** 返回该类型+级别对应的法定审批人；查不到返回 null（向导据此提示配置缺失）。 */
export function approverFor(
  ticketType: WorkTicketTypeCode,
  level?: string | null,
): string | null {
  const hit = APPROVAL_MATRIX.find(
    (r) => r.code === ticketType && r.level === (level ?? null),
  );
  return hit?.approver ?? null;
}

export const TICKET_STATUS_LABEL: Record<string, string> = {
  draft: "草稿",
  submitted: "已提交",
  approving: "审批中",
  approved: "已批准",
  rejected: "已退回",
  working: "作业中",
  finished: "已完工",
  closed: "已归档",
  cancelled: "已作废",
  expired: "已过期",
};

export const TICKET_STATUS_COLOR: Record<string, string> = {
  draft: "default",
  submitted: "default",
  approving: "processing",
  approved: "success",
  rejected: "error",
  working: "processing",
  finished: "success",
  closed: "default",
  cancelled: "default",
  expired: "warning",
};

/** 节点 key 的可读名。 */
export function nodeLabel(nodeKey?: string | null, approver?: string | null): string {
  if (!nodeKey) return "—";
  if (nodeKey === "countersign") return "涉及单位会签";
  if (nodeKey === "approve") return approver ? `审批（${approver}）` : "审批";
  return nodeKey;
}

export interface WorkTicketFlowNodeDef {
  node_key: string;
  name: string;
  sort_order: number;
  sign_policy: "any" | "all" | string;
  countersign_units?: string[] | null;
}

export interface WorkTicketFieldDef {
  field_key: string;
  label: string;
  field_type?: string | null;
  group_name?: string | null;
  is_required?: boolean;
  options?: { choices?: string[] } | null;
  /** 该字段允许 AI 预填（模板层数据，后端 templates 接口透出）。 */
  allow_ai_prefill?: boolean;
}

export interface WorkTicketMeasureDef {
  sort_order: number;
  measure_text: string;
  article_anchor: string;
}

export interface WorkTicketTemplate {
  id: string;
  code: WorkTicketTypeCode | string;
  name: string;
  level?: string | null;
  is_graded?: boolean;
  fields: WorkTicketFieldDef[];
  measures: WorkTicketMeasureDef[];
  flow_nodes?: WorkTicketFlowNodeDef[];
  /**
   * 该票种要展示的作业情景项（人工勾选）。由后端从 YAML 条件表带出，
   * 因此切换票种时情景区会跟着变；空数组表示该票种无需额外情景。
   */
  scenario_fields?: { key: string; label: string }[];
}

export interface WorkTicketInstance {
  id: string;
  code: string;
  ticket_type: string;
  level?: string | null;
  status: string;
  current_node_key?: string | null;
  values: Record<string, unknown>;
  values_meta?: Record<string, FieldMeta>;
  measures_meta?: Record<string, MeasureMeta>;
  valid_from?: string | null;
  valid_to?: string | null;
  created_at?: string | null;
}

/** 字段来源：决定开票页上的来源徽标与"哪些值需要人工确认"。 */
export type FieldSource =
  | "manual"
  | "history"
  | "member"
  | "risk_object"
  | "template_link"
  | "system_default"
  | "batch"
  | "ai";

export interface FieldMeta {
  source: FieldSource;
  source_ref?: Record<string, unknown>;
  prefilled_at?: string | null;
  confirmed_at?: string | null;
  confirmed_by?: string | null;
  edited?: boolean;
}

export type MeasureState = "pending" | "confirmed" | "not_applicable";

export interface MeasureMeta {
  state: MeasureState;
  reason_code?: string;
  reason_text?: string;
  acted_by?: string | null;
  acted_at?: string | null;
}

export interface MeasureSuggestion {
  sort_order: number;
  suggest: "applicable" | "not_applicable" | "unknown";
  reason: string | null;
}

export interface PrefillMember {
  id: string;
  name: string;
  position?: string | null;
  certificates?: { type?: string; no?: string; valid_to?: string }[];
}

export interface PrefillPayload {
  values: Record<string, unknown>;
  values_meta: Record<string, FieldMeta>;
  last_ticket_id?: string | null;
  members: PrefillMember[];
  /** 措施"是否涉及"建议：只影响分组排序，落地仍需人工点击。 */
  measures_suggestions?: MeasureSuggestion[];
}

export interface AiPrefillResult {
  available: boolean;
  risk_identification?: { text: string; basis: string[] } | null;
  jsa?: { text: string; hazards: { hazard: string; control: string }[] } | null;
  measures_suggestions?: MeasureSuggestion[];
  note?: string;
}

export interface LastTicketSummary {
  id: string;
  code: string;
  created_at?: string | null;
  work_content?: string | null;
  risk_identification?: string | null;
}

export interface LocationTree {
  floors: { id: string; name: string }[];
  zones: { id: string; name: string; floor_id?: string | null }[];
  objects: {
    id: string;
    name: string;
    location?: string | null;
    zone_id?: string | null;
    floor_id?: string | null;
  }[];
}

/** 作业包：一次检修（同地点 + 同一时段）下的多张作业票。 */
export interface WorkTicketBatch {
  id: string;
  enterprise_id: string;
  title: string;
  status: "draft" | "active" | "closed" | "cancelled" | string;
  floor_id?: string | null;
  zone_id?: string | null;
  risk_object_id?: string | null;
  location_text?: string | null;
  work_period_start?: string | null;
  work_period_end?: string | null;
  shared_values: Record<string, unknown>;
  content_base?: string | null;
  risk_basis?: string | null;
  created_at?: string | null;
}

export interface BatchTicketSpec {
  ticket_type: string;
  level?: string | null;
  template_id: string;
}

export interface BatchDetail {
  batch: WorkTicketBatch;
  tickets: WorkTicketInstance[];
  package_gas_tests: (GasTestRecord & { origin?: string })[];
}

export interface BatchSubmitAllResult {
  results: { ticket_id: string; code: string; ok: boolean; errors: string[] }[];
  succeeded: number;
}

/** 开票前审批链预检：每个节点要求什么岗位、当前企业能匹配到几个人。 */
export interface ApprovalNodePreview {
  node_key: string;
  name: string;
  role_code?: string | null;
  countersign_units?: string[];
  condition_expr?: string | null;
  is_statutory?: boolean;
  /** 0 表示当前企业没有任何人能签这个节点 → 票会卡在审批中 */
  eligible_count: number;
  eligible_names: string[];
}

export interface GasTestPayload {
  sampled_at: string;
  location?: string | null;
  gas_type?: string | null;
  result?: string | null;
  tester?: string | null;
  conclusion?: string | null;
}

export interface GasTestRecord extends GasTestPayload {
  id: string;
  instance_id?: string;
}

export interface WorkTicketNodeRecord {
  id: string;
  node_key: string;
  action: string;
  acted_by?: string | null;
  opinion?: string | null;
  created_at?: string | null;
}

/** 全量流转留痕（开票/提交/审批/开始作业/完工/归档/作废/过期）。 */
export interface WorkTicketAuditLog {
  id: string;
  action: string;
  from_status?: string | null;
  to_status?: string | null;
  detail?: Record<string, unknown>;
  acted_by?: string | null;
  created_at?: string | null;
}

export interface WorkTicketDetail {
  ticket: WorkTicketInstance;
  gas_tests: GasTestRecord[];
  node_records: WorkTicketNodeRecord[];
  audit_logs: WorkTicketAuditLog[];
}

export interface OpenTicketPayload {
  enterprise_id: string;
  enterprise_code: string;
  ticket_type: string;
  template_id: string;
  level?: string | null;
  values: Record<string, unknown>;
}

export interface SubmitResult {
  instance_id: string;
  status: string;
  node?: string | null;
  pending_signs?: number;
}
