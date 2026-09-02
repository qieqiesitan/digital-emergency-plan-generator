import axios, { type AxiosRequestConfig } from "axios";
import { message } from "antd";
import { getApiBaseUrl, getToken } from "@/utils/platform";

// F4：允许单个请求关闭「全局错误 toast」——页面自己处理错误提示时（登录/注册表单内联错误、
// 导出下载流、已有 onError 兜底的调用方）在请求配置里置 skipGlobalError，或带
// X-Skip-Global-Error: 1 请求头。拦截器内不做重复去重，以 skip 为准。
declare module "axios" {
  export interface AxiosRequestConfig {
    skipGlobalError?: boolean;
  }
}

const api = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 180000,
});

// 动态 baseURL
api.interceptors.request.use((config) => {
  config.baseURL = getApiBaseUrl();
  return config;
});

// 请求拦截器：自动注入 Token
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：401 自动刷新
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: unknown) => void;
  reject: (reason: unknown) => void;
}> = [];

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // 401 自动刷新
    if (error.response?.status === 401 && !originalRequest._retry) {
      // 认证类接口（登录/注册）的 401 属于「凭据错误」，不触发刷新，直接透传原始 error，
      // 让页面能读取后端返回的友好 detail（如「邮箱或密码错误」）而不是技术性错误。
      const url: string = originalRequest?.url || "";
      const isAuthEndpoint = /\/auth\/(login|register)/.test(url);
      if (isAuthEndpoint) {
        return Promise.reject(error);
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return api(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      let refreshToken: string | null = null;
      try {
        refreshToken = localStorage.getItem("refresh_token");
        if (!refreshToken) throw new Error("No refresh token");

        const { data } = await axios.post("/api/v1/auth/refresh", {
          refresh_token: refreshToken,
        });
        const newToken = data.data.access_token;
        localStorage.setItem("access_token", newToken);
        localStorage.setItem("refresh_token", data.data.refresh_token);

        failedQueue.forEach(({ resolve }) => resolve(newToken));
        failedQueue = [];

        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return api(originalRequest);
      } catch (refreshError) {
        failedQueue.forEach(({ reject }) => reject(refreshError));
        failedQueue = [];
        // 仅当存在 refresh_token 且刷新确实失败（无效/过期）时按登录过期处理；
        // 无 refresh_token 的 401（如登录页密码错误）直接 reject，由页面自身错误提示。
        if (refreshToken) {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          window.dispatchEvent(new CustomEvent("auth:logout"));
        }
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    // 统一全局错误提示（F4）：非 401 的 4xx/5xx 未显式 skip 时，优先取后端
    // detail/message/error 文案，用 antd message.error 统一提示，避免静默失败/只显示空内容。
    if (error.response && error.response.status !== 401 && !shouldSkipGlobalError(originalRequest)) {
      showGlobalError(error);
    }

    return Promise.reject(error);
  }
);

/** 请求是否显式要求跳过全局错误 toast（config.skipGlobalError 或 X-Skip-Global-Error 头） */
function shouldSkipGlobalError(config?: AxiosRequestConfig): boolean {
  if (!config) return false;
  if (config.skipGlobalError) return true;
  const rawHeaders = config.headers;
  if (!rawHeaders) return false;
  let value: unknown;
  if (typeof (rawHeaders as { get?: (name: string) => unknown }).get === "function") {
    value = (rawHeaders as { get: (name: string) => unknown }).get("X-Skip-Global-Error");
  } else {
    value = (rawHeaders as Record<string, unknown>)["X-Skip-Global-Error"];
  }
  return value === true || value === "1" || value === "true";
}

/** 提取后端可读错误文案：data.detail / data.message / data.error 优先 */
function extractErrorText(data: unknown): string | null {
  if (data && typeof data === "object") {
    const body = data as Record<string, unknown>;
    for (const key of ["detail", "message", "error"]) {
      const value = body[key];
      if (typeof value === "string" && value.trim()) return value.trim();
    }
  }
  return null;
}

/** 弹出统一全局错误 toast（拦截器唯一出口，避免各页面各自静默/重复实现） */
function showGlobalError(error: unknown): void {
  const status = (error as { response?: { status?: number } })?.response?.status;
  const data = (error as { response?: { data?: unknown } })?.response?.data;
  const text = extractErrorText(data);
  message.error(text || (status ? `请求失败（HTTP ${status}）` : "请求失败，请稍后重试"));
}

export default api;
