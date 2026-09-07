import { APP_BASE } from "@/utils/platform";

/**
 * 解析登录回跳目标：只允许站内相对路径。
 * 拒绝外部 URL、协议相对路径（//）、伪协议与路径穿越，防止开放重定向。
 * 部署子路径前缀（如 /emergency-plan-migration）会被剥离，因为路由以 basename 工作。
 */
export function resolveRedirectTarget(
  raw: string | null | undefined,
  appBase: string = APP_BASE,
): string | null {
  if (!raw) return null;
  const path = raw.trim();
  if (!path) return null;
  // 绝对 URL（http/https/ftp...）或协议相对路径一律拒绝
  if (/^(?:https?:)?\/\//i.test(path)) return null;
  // javascript: 等伪协议
  if (/^[a-z][a-z0-9+.-]*:/i.test(path)) return null;
  if (path.includes("\\") || path.includes("\n") || path.includes("\r")) return null;

  const base = appBase || "";
  const stripped = base && path.startsWith(`${base}/`) ? path.slice(base.length) : path;
  if (!stripped.startsWith("/")) return null;
  return stripped;
}

export function buildLoginPath(redirect: string | null | undefined): string {
  const safe = resolveRedirectTarget(redirect);
  return safe ? `/login?redirect=${encodeURIComponent(safe)}` : "/login";
}
