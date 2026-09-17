// 重大危险源类型定义。
//
// 注意：后端 Decimal 字段（临界量、q、β、s、R、α）经 FastAPI 序列化后是【字符串】
// （保精度，临界量有 0.3 / 0.75 这类值）。展示前统一用 utils/majorHazardFormat 的
// toNumber / formatQty 转换，不要直接参与算术。

export interface MajorHazardUnit {
  id: string;
  enterprise_id: string;
  name: string;
  unit_type: "production" | "storage";
  address?: string | null;
  department?: string | null;
  responsible_person?: string | null;
  responsible_phone?: string | null;
  risk_object_id?: string | null;
  is_active: boolean;
  created_at?: string | null;
}

export interface MajorHazardUnitPayload {
  name: string;
  unit_type: "production" | "storage";
  boundary_desc?: string | null;
  floor_id?: string | null;
  polygon?: Record<string, unknown> | null;
  address?: string | null;
  longitude?: number | null;
  latitude?: number | null;
  department?: string | null;
  responsible_person?: string | null;
  responsible_phone?: string | null;
  risk_object_id?: string | null;
  is_active?: boolean;
}

export interface MajorHazardUnitChemical {
  id: string;
  unit_id: string;
  chemical_id?: string | null;
  chemical_name: string;
  physical_state?: string | null;
  storage_location?: string | null;
  q_design_max: string;
  q_actual?: string | null;
  critical_quantity_t: string;
  beta: string;
  beta_source: "table3" | "table4" | "manual";
}

/** 提交品种清单时的载荷（id / unit_id 由后端管理）。 */
export type MajorHazardUnitChemicalPayload = Omit<
  MajorHazardUnitChemical,
  "id" | "unit_id"
>;

export interface MajorHazardCalculation {
  id: string;
  seq: number;
  s_value: string;
  r_value: string;
  alpha: string;
  exposed_population: number;
  is_major_hazard: boolean;
  level?: string | null;
  formula_version: string;
  calculated_at?: string | null;
}

export interface PreviewChemicalItem {
  name: string;
  q: number;
  Q: number;
  beta: number;
  q_over_Q: number;
  beta_times_q_over_Q: number;
}

/** 预览与固化共用同一形状（预览不含 seq；固化才有）。 */
export interface MajorHazardPreviewResult {
  seq?: number;
  s_value: string | number;
  r_value: string | number;
  alpha: string | number;
  exposed_population: number;
  is_major_hazard: boolean;
  level?: string | null;
  formula_version: string;
  chemicals: PreviewChemicalItem[];
}

export interface CriticalQuantity {
  chemical_name: string;
  alias?: string | null;
  cas_no?: string | null;
  critical_t?: string | null;
  critical_note?: string | null;
  table_no: string;
  source_page?: number | null;
}

export interface MajorHazardRecord {
  id: string;
  unit_id: string;
  enterprise_id: string;
  hazard_code?: string | null;
  filing_status: string;
  filing_no?: string | null;
  filing_date?: string | null;
  chief_name?: string | null;
  chief_post?: string | null;
  chief_phone?: string | null;
  tech_name?: string | null;
  tech_post?: string | null;
  tech_phone?: string | null;
  oper_name?: string | null;
  oper_post?: string | null;
  oper_phone?: string | null;
  attachments: Record<string, unknown>;
  completeness: Record<string, unknown>;
}

export interface EvidenceItem {
  id: string;
  regulation_id?: string | null;
  article_anchor: string;
  relation: string;
  note?: string | null;
}
