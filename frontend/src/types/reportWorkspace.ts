import type { ReportVersionItem } from "@/types/riskAssessment";

export interface ReportChapter {
  key: string;
  title: string;
  content: string;
}

export interface ReportDocument {
  id: string;
  title: string;
  content: string;
  status: string;
  chapters: ReportChapter[];
  stylePreference?: Record<string, string> | null;
}

export interface ReportIssue {
  severity: "error" | "warning" | "info";
  section_key: string;
  kind: string;
  issue: string;
  suggestion: string;
}

export interface ReportSSECallback {
  onEvent: (event: any) => void;
  onError: (error: string) => void;
  onComplete: () => void;
}

export interface ReportAdapter {
  load(enterpriseId: string): Promise<ReportDocument>;
  saveChapter(enterpriseId: string, key: string, content: string): Promise<void>;
  generateChapter(enterpriseId: string, key: string, cb: ReportSSECallback): AbortController;
  regenerateChapter(enterpriseId: string, key: string, cb: ReportSSECallback): AbortController;
  generateAll(enterpriseId: string, cb: ReportSSECallback): AbortController;
  review(enterpriseId: string, sectionKeys: string[] | null): Promise<ReportIssue[]>;
  applyReview(enterpriseId: string, sectionKeys: string[]): Promise<
    Array<{ section_key: string; title: string; original: string; revised: string }>
  >;
  getStyle(enterpriseId: string): Promise<Record<string, string>>;
  saveStyle(enterpriseId: string, style: Record<string, string>): Promise<void>;
  merge(enterpriseId: string, chapters: ReportChapter[]): Promise<void>;
  listVersions(enterpriseId: string): Promise<ReportVersionItem[]>;
  exportUrl(enterpriseId: string): string;
}
