/** 预案风格参数（Web 端 StylePanel 与高级模式共用） */
export interface StylePreference {
  formality: "formal" | "standard" | "practical";
  detail_level: "concise" | "balanced" | "comprehensive";
  table_preference: "minimal" | "moderate" | "heavy";
  diagram_preference: "none" | "mermaid";
  mode: "panel" | "advanced";
}

export const DEFAULT_STYLE: StylePreference = {
  formality: "standard",
  detail_level: "balanced",
  table_preference: "moderate",
  diagram_preference: "mermaid",
  mode: "panel",
};
