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
  inherent_risk_level?: string | null;
  level_color: string;
  responsible_unit: string;
  responsible_person: string;
  contact_phone: string;
  fallback_used: boolean;
  /** 存在未闭环隐患（规格 §11.1，告知卡 badge） */
  has_open_hazard: boolean;
  signs: SignItem[];
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
  has_open_hazard: boolean;
  snapshot: SnapshotInfo | null;
  stale: boolean;
  public_url: string;
}
