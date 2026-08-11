/** 获取 token */
export function getToken(): string {
  return localStorage.getItem("access_token") || "";
}

/** 获取用户名 */
export function getUsername(): string {
  return localStorage.getItem("username") || "";
}

/** 获取用户昵称 */
export function getNickname(): string {
  return localStorage.getItem("nickname") || "";
}

/** 获取系统编码 */
export function getSysCode(): string {
  return "";
}

/** 获取 API baseURL */
export function getApiBaseUrl(): string {
  return "/api/v1";
}

/** 应用部署子路径前缀（生产为 /emergency-plan-migration，开发为 ""） */
export const APP_BASE = import.meta.env.BASE_URL.replace(/\/+$/, "");

/** 从 pathname 中剥离应用子路径前缀，如 /emergency-plan-migration/m/login -> /m/login */
export function stripAppBase(pathname: string, appBase: string = APP_BASE): string {
  if (!appBase) return pathname;
  if (pathname === appBase || pathname.startsWith(`${appBase}/`)) {
    return pathname.slice(appBase.length);
  }
  return pathname;
}
