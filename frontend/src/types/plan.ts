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
  total: number;
  comprehensive_count: number;
  special_count: number;
  onsite_count: number;
  last_updated: string | null;
}