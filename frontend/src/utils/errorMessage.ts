/**
 * 从未知异常中提取可展示的错误文案。
 *
 * 兼容三类来源（本项目后端/axios/原生 Error 混用）：
 * 1. axios 响应体 `response.data.detail` / `response.data.message`
 * 2. Error.message
 * 3. 字符串抛出物
 */
export function errorMessage(err: unknown, fallback = "操作失败"): string {
  if (typeof err === "string") return err.trim() || fallback;

  if (err && typeof err === "object") {
    const e = err as {
      message?: unknown;
      response?: { data?: { detail?: unknown; message?: unknown } };
    };
    const candidates = [
      e.response?.data?.detail,
      e.response?.data?.message,
      e.message,
    ];
    for (const candidate of candidates) {
      if (typeof candidate === "string" && candidate.trim()) return candidate;
    }
  }

  if (err === undefined || err === null) return fallback;
  const text = String(err);
  return text.trim() && text !== "[object Object]" ? text : fallback;
}
