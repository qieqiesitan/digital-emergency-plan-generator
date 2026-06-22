import axios from "axios";
import { getApiBaseUrl, getToken, isYwtMode } from "@/utils/platform";

const api = axios.create({
  baseURL: getApiBaseUrl(),
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

// 动态 baseURL：中台模式直连后端，独立模式走 Vite proxy
api.interceptors.request.use((config) => {
  config.baseURL = getApiBaseUrl();
  return config;
});

// 请求拦截器：自动注入 Token（自动区分中台/独立模式）
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：401 刷新（中台模式下由主应用处理，不做 refresh）
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: unknown) => void;
  reject: (reason: unknown) => void;
}> = [];

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // 中台模式：401 交给主应用处理，直接 reject
    if (isYwtMode()) {
      if (error.response?.status === 401) {
        window.dispatchEvent(new CustomEvent("auth:logout"));
      }
      return Promise.reject(error);
    }

    // 独立模式：401 自动刷新
    if (error.response?.status === 401 && !originalRequest._retry) {
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

      try {
        const refreshToken = localStorage.getItem("refresh_token");
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
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.dispatchEvent(new CustomEvent("auth:logout"));
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default api;
