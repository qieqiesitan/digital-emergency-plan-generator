/**
 * DataHub 待确认队列的展示辅助纯函数。
 *
 * 队列要让审核人一眼看出"这条数据是什么、从哪来"，所以载荷必须被压成
 * 一行可读文本，而不是丢一坨 JSON 给人自己找。
 */

export function describePayload(
  payload: Record<string, unknown> | null | undefined,
  maxLen = 120,
): string {
  if (!payload) return "—";
  const parts: string[] = [];
  for (const [key, value] of Object.entries(payload)) {
    if (value === null || value === undefined || value === "") continue;
    if (typeof value === "object") {
      parts.push(`${key}: ${JSON.stringify(value)}`);
    } else {
      parts.push(`${key}: ${String(value)}`);
    }
  }
  if (!parts.length) return "—";
  const text = parts.join(" ｜ ");
  return text.length > maxLen ? `${text.slice(0, maxLen)}…` : text;
}

export const SOURCE_TYPE_LABELS: Record<string, string> = {
  file: "文件抽取",
  sheet: "表格导入",
  api_push: "系统推送",
  api_pull: "定时拉取",
  manual: "人工录入",
};

export const CONFIDENCE_LABELS: Record<string, string> = {
  high: "高",
  medium: "中",
  low: "低",
};
