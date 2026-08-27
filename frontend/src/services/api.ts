import axios from "axios";
import { getApiBaseUrl, getToken } from "@/utils/platform";

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

    return Promise.reject(error);
  }
);

export default api;
