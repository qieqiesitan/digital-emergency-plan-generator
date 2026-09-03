export interface ResourceGap {
  category: string;
  needed: string;
  reason: string;
  severity: string;
}

export interface ResourceInvestigationSummary {
  internal_resource_count: number;
  external_resource_count: number;
  internal_by_category: Record<string, number>;
  external_by_category: Record<string, number>;
  resource_gaps: ResourceGap[];
  key_findings: string[];
  overall_assessment: string;
}

export interface ResourceInvestigationReport {
  id: string;
  enterprise_id: string;
  title: string;
  content: string;
  summary: Partial<ResourceInvestigationSummary> & {
    chapters?: Array<{ key: string; title: string; content: string }>;
  };
  status: "draft" | "generating" | "completed";
  generated_by: "ai" | "manual";
  generated_at: string | null;
  current_version?: number;
  created_at: string;
  updated_at: string;
  style_preference?: Record<string, string> | null;
}

export interface ResourceInvestigationPreview {
  report_id: string;
  title: string;
  html: string;
}
