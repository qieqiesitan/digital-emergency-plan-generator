/**
 * 统一的接口错误提取。
 *
 * 为什么要有它：项目里这个逻辑散落在多处，实现还不一致——有的只认字符串 detail，
 * 而 FastAPI 的 pydantic 校验错误（422）的 detail 是**数组**，
 * 于是页面上只弹出「Request failed with status code 422」，用户根本不知道哪个字段错了
 * （2026-09-23 新建企业报 422 时就是这样）。
 */

interface ValidationItem {
  loc?: unknown[];
  msg?: string;
}

function formatItem(item: unknown): string {
  if (typeof item === "string") return item.trim();
  if (!item || typeof item !== "object") return "";
  const { loc, msg } = item as ValidationItem;
  const text = typeof msg === "string" ? msg.trim() : "";
  if (!text) return "";
  // loc 形如 ["body", "employee_count"]，去掉 body 前缀后作为字段名展示
  const fieldParts = Array.isArray(loc)
    ? loc.filter((part) => part !== "body" && typeof part === "string")
    : [];
  const field = fieldParts.join(".");
  return field ? `${field}：${text}` : text;
}

/** 把后端错误转成一句人话；实在没有就用 fallback。 */
export function errorMessage(err: unknown, fallback: string): string {
  const data = (
    err as { response?: { data?: { detail?: unknown; message?: unknown } } }
  )?.response?.data;
  const raw = data?.detail ?? data?.message;
  if (typeof raw === "string" && raw.trim()) return raw.trim();
  if (Array.isArray(raw)) {
    const parts = raw.map(formatItem).filter(Boolean);
    if (parts.length > 0) return parts.join("；");
  }
  const message = (err as { message?: string })?.message;
  return typeof message === "string" && message.trim() ? message : fallback;
}
