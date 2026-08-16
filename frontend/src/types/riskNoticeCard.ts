/** 风险告知卡（Risk Notice Card）类型定义。
 *
 * 结构与后端 backend/app/schemas/risk_notice_card.py 一一对应：
 * SignItem / RightColumn / CardData / CardSummary。
 */

export type SignCategory = "warning" | "prohibition" | "instruction" | "notice";

export interface SignItem {
  category: SignCategory;
  name: string;
  svg_name: string;
}

/** AI 标志审查建议（remove/add 为 svg_name 集合，reasons 为逐项理由）。 */
export interface SignSuggestion {
  remove: string[];
  add: string[];
  reasons: { sign_name: string; reason: string }[];
}

/** AI 标志审查结果（original_signs 为审查时当前标志）。 */
export interface AiSignReviewResponse {
  original_signs: SignItem[];
  suggestion: SignSuggestion;
}

/** 右栏四块内容（AI 优化仅针对 hazard_description/control_measures/emergency_measures）。 */
export interface RightColumn {
  hazard_description: string;
  accident_types: string[];
  control_measures: string[];
  emergency_measures: string[];
}

/** 快照信息（version 每次保存 +1，source 区分 ai/rule）。 */
export interface SnapshotInfo {
  version: number;
  source: string;
}

/** 单卡完整数据（快照优先）。 */
export interface CardData extends RightColumn {
  object_id: string;
  enterprise_name: string;
  name: string;
  code: string;
  level: string;
  level_color: string;
  responsible_unit: string;
  responsible_person: string;
  contact_phone: string;
  fallback_used: boolean;
  signs: SignItem[];
  /** 标志来源（后端回填，旧响应可能缺失）。 */
  signs_source?: "rule" | "ai" | "manual";
  snapshot: SnapshotInfo | null;
  stale: boolean;
  public_url: string;
  generated_at: string;
}

/** 列表摘要（列表端点返回）。 */
export interface CardSummary {
  object_id: string;
  name: string;
  zone_name: string;
  level: string;
  level_color: string;
  accident_types: string[];
  signs: SignItem[];
  responsible_unit: string;
  snapshot: SnapshotInfo | null;
  stale: boolean;
  public_url: string;
}
