export interface ExportTask {
  task_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  progress: number;
  download_url: string | null;
  error_message: string | null;
}

export interface ExportPreview {
  plan_id: string;
  title: string;
  html: string;
}

export interface ExportValidation {
  valid: boolean;
  issues: Array<{ section_key: string; section_title: string; issue: string }>;
  warnings: string[];
}
