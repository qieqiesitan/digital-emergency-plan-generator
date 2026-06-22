interface YwtProps {
  token: string;
  username: string;
  nickname: string;
  sysCode: string;
  container?: HTMLElement;
  onGlobalStateChange?: (callback: (state: Record<string, unknown>) => void) => void;
  setGlobalState?: (state: Record<string, unknown>) => void;
}

declare global {
  interface Window {
    __POWERED_BY_QIANKUN__?: boolean;
    __YWT_PROPS__?: YwtProps;
  }
}

/** 获取中台注入的 props */
export function getYwtProps(): YwtProps {
  return window.__YWT_PROPS__ || ({} as YwtProps);
}

/** 获取 token，自动区分中台/独立模式 */
export function getToken(): string {
  if (isYwtMode()) {
    return getYwtProps().token || "";
  }
  return localStorage.getItem("access_token") || "";
}

/** 获取用户名 */
export function getUsername(): string {
  if (isYwtMode()) {
    return getYwtProps().username || "";
  }
  // 独立模式下从 localStorage 读取缓存的用户名
  return localStorage.getItem("username") || "";
}

/** 获取用户昵称 */
export function getNickname(): string {
  if (isYwtMode()) {
    return getYwtProps().nickname || getYwtProps().username || "";
  }
  return localStorage.getItem("nickname") || "";
}

/** 获取系统编码 */
export function getSysCode(): string {
  if (isYwtMode()) {
    return getYwtProps().sysCode || "";
  }
  return "";
}

/** 是否运行在中台 qiankun 模式下 */
export function isYwtMode(): boolean {
  return !!window.__POWERED_BY_QIANKUN__;
}

/** 获取 API baseURL */
export function getApiBaseUrl(): string {
  if (isYwtMode()) {
    return "http://localhost:8000";
  }
  return "/api/v1";
}
