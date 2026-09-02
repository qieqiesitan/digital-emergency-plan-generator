import { getApiBaseUrl } from "@/utils/platform";

/**
 * SSE 请求公共层（体检 B13）：统一 baseURL + Authorization 头 + 401 刷新重试，
 * 并统一 ReadableStream 行读取。事件解析仍由各调用方 onData 完成。
 */

export interface SseStreamOutcome {
  status: "stream" | "error" | "cancelled";
  message?: string;
}

export interface SseFetchOptions {
  /** 请求路径（不含 getApiBaseUrl 前缀），如 "/plans/xxx/generate/section" */
  path: string;
  method?: string;
  /** JSON 请求体；POST 时自动注入 Content-Type + Authorization（Bearer access_token） */
  body?: unknown;
  signal?: AbortSignal;
  /** 请求失败兜底文案（response 无 detail/message 或网络错误时使用） */
  errorMessage: string;
  /** 逐行读取：onData 收到去掉 "data: " 前缀的原始数据，由调用方自行 JSON.parse + 事件分发 */
  onData: (data: string) => void;
  /** 流完成（非取消、非错误）后回调 */
  onComplete: () => void;
  /** 错误回调：HTTP 非 2xx / 网络错误 / 流中途异常（message 已取 detail/errorMessage） */
  onError: (message: string) => void;
}

function readErrorDetail(body: string): string | null {
  try {
    const parsed = JSON.parse(body) as {
      detail?: unknown;
      message?: unknown;
      error?: unknown;
    };
    if (typeof parsed.detail === "string" && parsed.detail) return parsed.detail;
    if (typeof parsed.message === "string" && parsed.message) return parsed.message;
    if (typeof parsed.error === "string" && parsed.error) return parsed.error;
  } catch {
    // 非 JSON 错误体：原样截断使用
  }
  const trimmed = body.trim();
  return trimmed && trimmed.length < 300 ? trimmed : null;
}

async function responseErrorMessage(response: Response): Promise<string | null> {
  try {
    const text = await response.clone().text();
    return readErrorDetail(text);
  } catch {
    return null;
  }
}

function buildHeaders(jsonBody: boolean): Record<string, string> {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${localStorage.getItem("access_token") || ""}`,
  };
  if (jsonBody) {
    headers["Content-Type"] = "application/json";
  }
  return headers;
}

function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

/** 401 时刷新 token（沿用 api.ts 拦截器行为：成功换新 token，失败清登录态并广播 auth:logout） */
async function tryRefreshToken(): Promise<boolean> {
  const refreshToken = localStorage.getItem("refresh_token");
  if (!refreshToken) {
    return false;
  }
  try {
    const res = await fetch(`${getApiBaseUrl()}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) {
      dispatchLogout();
      return false;
    }
    const json = (await res.json()) as {
      data?: { access_token?: string; refresh_token?: string };
    };
    const access = json.data?.access_token;
    const nextRefresh = json.data?.refresh_token;
    if (!access) {
      dispatchLogout();
      return false;
    }
    localStorage.setItem("access_token", access);
    if (nextRefresh) localStorage.setItem("refresh_token", nextRefresh);
    return true;
  } catch {
    dispatchLogout();
    return false;
  }
}

function dispatchLogout(): void {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  window.dispatchEvent(new CustomEvent("auth:logout"));
}

async function reportError(
  response: Response | null,
  options: SseFetchOptions,
  networkMessage?: string,
): Promise<SseStreamOutcome> {
  let message: string | null = null;
  if (response) message = await responseErrorMessage(response);
  const finalMessage = message || networkMessage || options.errorMessage;
  options.onError(finalMessage);
  return { status: "error", message: finalMessage };
}

function parseError(err: unknown, fallback: string): string {
  if (err instanceof Error && err.message && err.message !== "Failed to fetch") {
    return err.message;
  }
  return fallback;
}

/** 读取 SSE 响应流，逐 data: 行回调 onData；done 后回调 onComplete */
async function consumeStream(
  response: Response,
  options: SseFetchOptions,
): Promise<SseStreamOutcome> {
  const reader = response.body?.getReader();
  if (!reader) return reportError(null, options);

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (line.startsWith("data: ")) {
          options.onData(line.slice(6));
        }
      }
    }
    options.onComplete();
    return { status: "stream" };
  } catch (err) {
    if (isAbortError(err)) return { status: "cancelled" };
    return reportError(null, options, parseError(err, options.errorMessage));
  }
}

/**
 * 发起 SSE 请求（自动注入 token，401 刷新后重试一次）。永不 reject：
 * - stream：响应 2xx 且流正常读完（onComplete 已触发）
 * - error：HTTP 非 2xx / 网络错误 / 流异常（onError 已触发）
 * - cancelled：主动 abort（onError/onComplete 均不触发）
 */
export async function sseFetch(options: SseFetchOptions): Promise<SseStreamOutcome> {
  const url = `${getApiBaseUrl()}${options.path}`;
  const jsonBody = options.body !== undefined;
  const method = (options.method || (jsonBody ? "POST" : "GET")).toUpperCase();

  let response: Response | null = null;
  try {
    response = await fetch(url, {
      method,
      headers: buildHeaders(jsonBody),
      body: jsonBody ? JSON.stringify(options.body) : undefined,
      signal: options.signal,
    });
  } catch (err) {
    if (isAbortError(err)) return { status: "cancelled" };
    return reportError(null, options, parseError(err, options.errorMessage));
  }

  if (response.status === 401) {
    const refreshed = await tryRefreshToken();
    if (!refreshed) {
      return reportError(response, options, "登录已过期，请重新登录");
    }
    try {
      response = await fetch(url, {
        method,
        headers: buildHeaders(jsonBody),
        body: jsonBody ? JSON.stringify(options.body) : undefined,
        signal: options.signal,
      });
    } catch (err) {
      if (isAbortError(err)) return { status: "cancelled" };
      return reportError(null, options, parseError(err, options.errorMessage));
    }
  }

  if (!response.ok) {
    return reportError(response, options);
  }

  return consumeStream(response, options);
}

export interface ApiJsonFetchOptions {
  /** 请求路径（不含 getApiBaseUrl 前缀） */
  path: string;
  method?: string;
  /** JSON 请求体；存在时自动注入 Content-Type */
  body?: unknown;
  errorMessage: string;
}

/** 非流式 JSON 请求（自动注入 token，401 刷新后重试一次）；失败 reject 带可读 message */
export async function apiJsonFetch<T = unknown>(options: ApiJsonFetchOptions): Promise<T> {
  const url = `${getApiBaseUrl()}${options.path}`;
  const jsonBody = options.body !== undefined;
  const method = (options.method || (jsonBody ? "POST" : "GET")).toUpperCase();

  let response: Response | null = null;
  try {
    response = await fetch(url, {
      method,
      headers: buildHeaders(jsonBody),
      body: jsonBody ? JSON.stringify(options.body) : undefined,
    });
  } catch (err) {
    throw new Error(parseError(err, options.errorMessage));
  }

  if (response.status === 401) {
    const refreshed = await tryRefreshToken();
    if (!refreshed) {
      throw new Error("登录已过期，请重新登录");
    }
    try {
      response = await fetch(url, {
        method,
        headers: buildHeaders(jsonBody),
        body: jsonBody ? JSON.stringify(options.body) : undefined,
      });
    } catch (err) {
      throw new Error(parseError(err, options.errorMessage));
    }
  }

  if (!response.ok) {
    const detail = await responseErrorMessage(response);
    throw new Error(detail || options.errorMessage);
  }
  return response.json() as Promise<T>;
}
