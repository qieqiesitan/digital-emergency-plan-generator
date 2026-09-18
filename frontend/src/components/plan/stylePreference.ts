import type { PlanStylePreference } from "@/types/plan";

/** 预案风格参数（Web 端 StylePanel 与高级模式共用；API 契约见 @/types/plan） */
export type StylePreference = PlanStylePreference;

export const DEFAULT_STYLE: StylePreference = {
  formality: "standard",
  detail_level: "balanced",
  table_preference: "moderate",
  diagram_preference: "mermaid",
  mode: "panel",
};
