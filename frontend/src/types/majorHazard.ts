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
  floor_id?: string | null;
  polygon?: MajorHazardUnitPolygon | null;
  is_active: boolean;
  created_at?: string | null;
}

/** 单元平面图落点的顶点。坐标为百分比（0-100），与四色图工作台约定一致。 */
export interface MajorHazardUnitPolygonPoint {
  x: number;
  y: number;
}

/**
 * 单元在平面图上的落点。
 *
 * 只存一个多边形（单元边界就是一条闭合界线），不套用四色图的
 * RiskZoneFloorPlanPolygon——那个结构带 level_mode/risk_level 等风险分级语义，
 * 对重大危险源单元没有意义。两者共用的是坐标约定与几何算法。
 */
export interface MajorHazardUnitPolygon {
  version: 1;
  points: MajorHazardUnitPolygonPoint[];
}

/** 可关联的风险点（`GET /major-hazard/linkable/risk-objects`）。 */
export interface LinkableRiskObject {
  id: string;
  name: string;
  zone_id?: string | null;
  floor_id?: string | null;
}

/** 危化品台账条目（`GET /major-hazard/ledger/chemicals`）。 */
export interface LedgerChemical {
  id: string;
  name: string;
  cas_no?: string | null;
  max_storage?: string | null;
  storage_amount?: number | null;
  storage_unit?: string | null;
}

/**
 * 设计最大量的**建议初值**。
 *
 * `requires_confirmation` 恒为 true：建议值来自台账存量口径，
 * 与 GB 18218 4.2.2 的设计最大量口径不同，必须由人工确认后才落库。
 */
export interface DesignMaxSuggestion {
  chemical_id: string;
  chemical_name: string;
  suggested_q: number | null;
  ledger_text?: string | null;
  source: "structured" | "text";
  hint: string;
  requires_confirmation: boolean;
}

export interface MajorHazardUnitPayload {
  name: string;
  unit_type: "production" | "storage";
  boundary_desc?: string | null;
  floor_id?: string | null;
  polygon?: MajorHazardUnitPolygon | null;
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

/** 表4 的一条危险性类别（用于 β 查不到时让用户选）。 */
export interface HazardSymbolOption {
  symbol: string;
  category?: string | null;
  beta?: number | null;
}

/**
 * 按品种名查出的标准值。
 *
 * `needs_hazard_symbol=true` 表示表3（按名称）没查到 β，
 * 需要用户从 `hazard_symbol_options`（表4）里选一个危险性类别再查。
 */
export interface ChemicalDefinition {
  chemical_name: string;
  alias?: string | null;
  cas_no?: string | null;
  table_no?: string | null;
  critical_quantity_t?: number | null;
  critical_note?: string | null;
  beta?: number | null;
  beta_source?: "table3" | "table4" | null;
  needs_hazard_symbol: boolean;
  hazard_symbol_options: HazardSymbolOption[];
}
