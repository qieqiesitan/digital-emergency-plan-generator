export interface RiskAssessmentSummary {
  risk_source_count: number;
  risk_level_distribution: Record<string, number>;
  top_risks: Array<{
    name: string;
    category: string;
    risk_level: string;
    likelihood: string;
    severity: string;
    location: string;
    key_control_measures: string;
  }>;
  risk_by_category: Record<string, number>;
  key_findings: string[];
  overall_assessment: string;
}

export interface RiskAssessmentReport {
  id: string;
  enterprise_id: string;
  title: string;
  content: string;
  summary: RiskAssessmentSummary;
  status: "draft" | "generating" | "completed";
  generated_by: "ai" | "manual";
  generated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface RiskAssessmentPreview {
  report_id: string;
  title: string;
  html: string;
}

export interface SSEEvent {
  type: "progress" | "chunk" | "section_done" | "batch_done" | "error";
  message?: string;
  stage?: string;
  content?: string;
  section_key?: string;
  report_id?: string;
  title?: string;
  current?: number;
  total?: number;
  completed?: number;
  failed?: number;
}
