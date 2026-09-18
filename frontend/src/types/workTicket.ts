/**
 * 作业票（特殊作业票）类型与常量。
 *
 * 审批人表取自 GB 30871-2022 附录B 表B.1，与后端 seed_work_ticket_templates.py 的
 * APPROVAL_MATRIX 同源。前端留一份是为了兑现"级别一选、审批链自动定"——
 * 向导第 1 步选完级别就能立刻告诉用户要经过谁，不必为此多打一次接口。
 */

export type WorkTicketTypeCode = "DHZY" | "YXKJ";

export const TICKET_TYPE_LABEL: Record<WorkTicketTypeCode, string> = {
  DHZY: "动火作业",
  YXKJ: "受限空间作业",
};

/** 本计划只开放这两类；其余 6 类在列表页灰显并提示"未启用"。 */
export const ENABLED_TICKET_TYPES: WorkTicketTypeCode[] = ["DHZY", "YXKJ"];

/** 未启用的 6 类（计划 9 靠模板驱动复制），此处只用于灰显说明。 */
export const DISABLED_TICKET_TYPES = [
  "盲板抽堵作业",
  "高处作业",
  "吊装作业",
  "临时用电作业",
  "动土作业",
  "断路作业",
] as const;

export const FIRE_LEVELS = ["特级", "一级", "二级"] as const;

/** GB 30871-2022 附录B 表B.1：动火按级别定审批人，受限空间统一到所在基层单位。 */
export const APPROVAL_MATRIX: {
  code: WorkTicketTypeCode;
  level: string | null;
  approver: string;
}[] = [
  { code: "DHZY", level: "特级", approver: "主管领导" },
  { code: "DHZY", level: "一级", approver: "安全管理部门" },
  { code: "DHZY", level: "二级", approver: "所在基层单位" },
  { code: "YXKJ", level: null, approver: "所在基层单位" },
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

/** 节点 key 的可读名。种子只生成 `approve` 一个法定环节（审批人另见 APPROVAL_MATRIX）。 */
export function nodeLabel(nodeKey?: string | null, approver?: string | null): string {
  if (!nodeKey) return "—";
  if (nodeKey === "approve") return approver ? `审批（${approver}）` : "审批";
  return nodeKey;
}

export interface WorkTicketFieldDef {
  field_key: string;
  label: string;
  field_type?: string | null;
  group_name?: string | null;
  is_required?: boolean;
  options?: { choices?: string[] } | null;
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
}

export interface WorkTicketInstance {
  id: string;
  code: string;
  ticket_type: string;
  level?: string | null;
  status: string;
  current_node_key?: string | null;
  values: Record<string, unknown>;
  valid_from?: string | null;
  valid_to?: string | null;
  created_at?: string | null;
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

export interface WorkTicketDetail {
  ticket: WorkTicketInstance;
  gas_tests: GasTestRecord[];
  node_records: WorkTicketNodeRecord[];
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
