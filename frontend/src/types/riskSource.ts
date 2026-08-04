export type RiskLevel = "重大" | "较大" | "一般" | "低";
export type Likelihood = "高" | "中" | "低";
export type Severity = "高" | "中" | "低";

export interface RiskSource {
  id: string;
  enterprise_id: string;
  categories: string[];
  name: string;
  location: string;
  location_x: number | null;
  location_y: number | null;
  description: string;
  likelihood: Likelihood;
  severity: Severity;
  risk_level: RiskLevel;
  control_measures: string;
  sort_order: number;
  created_at: string;
}

export interface RiskSourceCreate {
  categories: string[];
  name: string;
  location?: string;
  location_x?: number | null;
  location_y?: number | null;
  description?: string;
  likelihood?: Likelihood;
  severity?: Severity;
  risk_level?: RiskLevel;
  control_measures?: string;
}

export interface RiskSourceUpdate extends Partial<RiskSourceCreate> {}
