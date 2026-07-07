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
