/**
 * 预案相关 URL 的统一定义与透传规则：
 * 企业语境（enterprise_id）统一由这里携带，避免各页面手拼字符串时漏掉。
 */

export interface PlanContext {
  enterpriseId?: string | null;
}

export interface PlanEditorOptions extends PlanContext {
  autoGenerate?: "1" | "sample";
}

function buildUrl(
  planId: string,
  action: "edit" | "versions" | "preview",
  opts?: PlanEditorOptions,
): string {
  const params = new URLSearchParams();
  if (opts?.enterpriseId) params.set("enterprise_id", opts.enterpriseId);
  if (action === "edit" && opts?.autoGenerate) params.set("auto_generate", opts.autoGenerate);
  const query = params.toString();
  return `/plans/${planId}/${action}${query ? `?${query}` : ""}`;
}

export function planEditorUrl(planId: string, opts?: PlanEditorOptions): string {
  return buildUrl(planId, "edit", opts);
}

export function planVersionsUrl(planId: string, ctx?: PlanContext): string {
  return buildUrl(planId, "versions", ctx);
}

export function planPreviewUrl(planId: string, ctx?: PlanContext): string {
  return buildUrl(planId, "preview", ctx);
}

/**
 * 预案编辑器清理 URL：只删除 auto_generate（防重复触发），
 * 保留 enterprise_id 等其余参数，避免返回时丢失企业语境。
 */
export function sanitizeEditorSearchParams(search: string): string {
  const params = new URLSearchParams(search);
  params.delete("auto_generate");
  const query = params.toString();
  return query ? `?${query}` : "";
}
