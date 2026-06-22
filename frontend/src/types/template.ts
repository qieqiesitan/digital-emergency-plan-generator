import type { PlanType } from "./plan";

export interface SectionTemplate {
  key: string;
  title: string;
  level: number;
  sort_order: number;
  ai_generatable: boolean;
  user_editable: boolean;
  required: boolean;
  auto_fill: boolean;
  auto_fill_source: string | null;
  gb_requirement: string;
  prompt_template: string | null;
  data_dependencies: string[];
  subsections: SectionTemplate[];
}

export interface PlanTemplate {
  id: string;
  plan_type: PlanType;
  name: string;
  version: string;
  structure: SectionTemplate[];
  is_active: boolean;
}
