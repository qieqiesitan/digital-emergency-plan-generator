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
  generatedAt?: string | null;
  chapters: ReportChapter[];
  stylePreference?: Record<string, string> | null;
  /** 全量生成产出的四色分布图（risk 类型 summary.images 透传） */
  fourColorImages?: Array<{ floor_id: string; floor_name: string; url: string }>;
}

export interface ReportIssue {
  severity: "error" | "warning" | "info";
  section_key: string;
  kind: string;
  issue: string;
  suggestion: string;
}

/** 报告生成 SSE 事件（后端按 type 下发不同字段，未知字段保持前向兼容） */
export interface ReportStreamEvent {
  type: string;
  message?: string;
  content?: string;
  section_key?: string;
  current?: number;
  total?: number;
  chapters?: Array<{ key: string; title: string }>;
  failed_sections?: Array<{ section_key: string; title: string }>;
}

export interface ReportSSECallback {
  onEvent: (event: ReportStreamEvent) => void;
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
  /** 导出 Word：blob 下载（不新开窗口），文件名取后端 Content-Disposition */
  download(enterpriseId: string): Promise<void>;
}
