/**
 * 版本对比的纯展示逻辑（无 React，可单测）。
 *
 * 后端 `GET /plans/{id}/versions/compare?a=&b=` 返回逐章节的
 * `{section_key, title, change_type: added|removed|modified|unchanged, old_content, new_content}`。
 * 这里负责分组的**顺序与文案**：新增 → 删除 → 修改 → 未变（未变默认折叠，避免噪音）。
 */
import type { SectionDiff } from "@/types/plan";

export type DiffKind = SectionDiff["change_type"];

export interface DiffGroup {
  kind: DiffKind;
  label: string;
  items: SectionDiff[];
}

const ORDER: DiffKind[] = ["added", "removed", "modified", "unchanged"];
const LABEL: Record<DiffKind, string> = {
  added: "新增章节",
  removed: "删除章节",
  modified: "内容有修改",
  unchanged: "未变化",
};

/** 按"新增→删除→修改→未变"分组；空组不返回。 */
export function groupDiffs(diffs: readonly SectionDiff[] | null | undefined): DiffGroup[] {
  const buckets: Record<DiffKind, SectionDiff[]> = {
    added: [], removed: [], modified: [], unchanged: [],
  };
  for (const d of diffs ?? []) {
    const kind = (d?.change_type ?? "unchanged") as DiffKind;
    (buckets[kind] ?? buckets.unchanged).push(d);
  }
  return ORDER.filter((k) => buckets[k].length > 0).map((k) => ({
    kind: k,
    label: LABEL[k],
    items: buckets[k],
  }));
}

export interface DiffSummary {
  added: number;
  removed: number;
  modified: number;
  unchanged: number;
  /** 真正有变化的章节数（不含未变） */
  changed: number;
}

export function summarizeDiffs(diffs: readonly SectionDiff[] | null | undefined): DiffSummary {
  const s: DiffSummary = { added: 0, removed: 0, modified: 0, unchanged: 0, changed: 0 };
  for (const d of diffs ?? []) {
    const kind = (d?.change_type ?? "unchanged") as DiffKind;
    if (kind in s) s[kind] += 1;
  }
  s.changed = s.added + s.removed + s.modified;
  return s;
}

/** 纯文本长度（用于给"未变/修改"一个体量参考；HTML 标签不计入）。 */
export function plainTextLength(html: string | null | undefined): number {
  return (html || "").replace(/<[^>]*>/g, "").replace(/\s+/g, "").length;
}
