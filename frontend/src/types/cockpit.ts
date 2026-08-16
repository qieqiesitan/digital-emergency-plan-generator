export interface RiskCounts {
  major: number;
  larger: number;
  general: number;
  low: number;
  total: number;
}

export interface TopRisk {
  name: string;
  level: string;
  score: number | null;
  responsible_unit: string | null;
}

export interface ZoneRisk {
  zone_name: string;
  counts: RiskCounts;
  total: number;
}

export interface CockpitTodo {
  priority: "high" | "medium" | "low";
  title: string;
  note: string;
}

export interface CompletionModule {
  key: string;
  label: string;
  done: boolean;
}

export interface CockpitCompletion {
  percent: number;
  modules: CompletionModule[];
}

export interface ActivityItem {
  actor: string;
  action: string;
  time: string;
}

export interface HazardCounts {
  open: number;
  due: number;
  overdue: number;
}

export interface CockpitSummary {
  risk_counts: RiskCounts;
  zone_risks: ZoneRisk[];
  top_risks: TopRisk[];
  risk_index: number;
  hazard_counts: HazardCounts;
  todos: CockpitTodo[];
  completion: CockpitCompletion;
  recent_activities: ActivityItem[];
}

export const RISK_LEVEL_COLORS: Record<string, string> = {
  major: "#ff4d4f",
  larger: "#ff9f43",
  general: "#ffd666",
  low: "#40a9ff",
};

export const RISK_LEVEL_LABELS: Record<string, string> = {
  major: "重大",
  larger: "较大",
  general: "一般",
  low: "低",
};
