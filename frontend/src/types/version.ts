export interface PlanVersion {
  id: string;
  version_number: number;
  created_by: "auto" | "manual";
  description: string | null;
  created_at: string;
}

export interface PlanVersionDetail extends PlanVersion {
  snapshot: Record<string, unknown>;
}

export interface SectionDiff {
  section_key: string;
  title: string;
  change_type: "added" | "removed" | "modified" | "unchanged";
  old_content: string | null;
  new_content: string | null;
}

export interface VersionCompare {
  version_a: number;
  version_b: number;
  diffs: SectionDiff[];
}
