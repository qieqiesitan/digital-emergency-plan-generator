import type { ReportChapter } from "@/types/reportWorkspace";

/** 失败章节列表纯 reducer：按 key 去重追加 */
export function addFailedChapter(
  list: ReportChapter[],
  key: string,
  title?: string,
): ReportChapter[] {
  if (!key || list.some((f) => f.key === key)) return list;
  return [...list, { key, title: title || key, content: "" }];
}
