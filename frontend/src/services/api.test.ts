import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { AxiosError, type AxiosRequestConfig, type AxiosResponse } from "axios";

vi.mock("antd", () => ({
  message: {
    error: vi.fn(),
    warning: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
  },
}));

import api from "./api";
import { message } from "antd";
import * as authService from "./authService";
import { fetchStats } from "./regulationService";

const errorSpy = vi.mocked(message.error);

function fakeResponse(config: unknown, status: number, data: unknown): AxiosResponse {
  return { data, status, statusText: String(status), headers: {}, config: config as AxiosResponse["config"] };
}

function httpError(config: AxiosRequestConfig, status: number, data: unknown): AxiosError {
  const code = status >= 500 ? AxiosError.ERR_BAD_RESPONSE : AxiosError.ERR_BAD_REQUEST;
  return new AxiosError(
    `Request failed with status code ${status}`,
    code,
    config as never,
    null,
    fakeResponse(config as never, status, data) as never,
  );
}

function networkError(config: AxiosRequestConfig): AxiosError {
  return new AxiosError("Network Error", AxiosError.ERR_NETWORK, config as never);
}

describe("api 全局错误 toast（F4）", () => {
  let failWith: { status: number; data: unknown } | null = null;
  let seenConfigs: Array<AxiosRequestConfig & { skipGlobalError?: boolean }>;
  const storage = new Map<string, string>();

  beforeEach(() => {
    vi.clearAllMocks();
    storage.clear();
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => (storage.has(key) ? storage.get(key)! : null),
      setItem: (key: string, value: string) => storage.set(key, value),
      removeItem: (key: string) => storage.delete(key),
      clear: () => storage.clear(),
    });
    failWith = null;
    seenConfigs = [];
    api.defaults.adapter = async (config) => {
      seenConfigs.push(config);
      if (failWith) throw httpError(config, failWith.status, failWith.data);
      return { data: { code: 0, data: {} }, status: 200, statusText: "OK", headers: {}, config };
    };
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    delete api.defaults.adapter;
  });

  it("500 + data.detail → 弹一次全局 toast 且用后端 detail 文案", async () => {
    failWith = { status: 500, data: { detail: "法规库索引未初始化" } };
    await expect(api.get("/regulations/stats")).rejects.toThrow();
    expect(errorSpy).toHaveBeenCalledTimes(1);
    expect(errorSpy).toHaveBeenCalledWith("法规库索引未初始化");
  });

  it("404 + data.message → 取 message 文案（detail 缺省时兜底）", async () => {
    failWith = { status: 404, data: { message: "预案不存在" } };
    await expect(api.get("/plans/not-exist")).rejects.toThrow();
    expect(errorSpy).toHaveBeenCalledWith("预案不存在");
  });

  it("4xx 无 detail/message/error → 通用 HTTP 状态兜底文案", async () => {
    failWith = { status: 400, data: {} };
    await expect(api.get("/x")).rejects.toThrow();
    expect(errorSpy).toHaveBeenCalledWith("请求失败（HTTP 400）");
  });

  it("请求带 X-Skip-Global-Error: 1 头 → 不弹全局 toast", async () => {
    failWith = { status: 500, data: { detail: "boom" } };
    await expect(
      api.get("/x", { headers: { "X-Skip-Global-Error": "1" } }),
    ).rejects.toThrow();
    expect(errorSpy).not.toHaveBeenCalled();
  });

  it("请求 config.skipGlobalError: true → 不弹全局 toast", async () => {
    failWith = { status: 500, data: { detail: "boom" } };
    await expect(api.get("/x", { skipGlobalError: true })).rejects.toThrow();
    expect(errorSpy).not.toHaveBeenCalled();
  });

  it("401（无 refresh token 走既有分支）→ 不弹全局 toast", async () => {
    failWith = { status: 401, data: { detail: "凭据过期" } };
    await expect(api.get("/users/me")).rejects.toThrow();
    expect(errorSpy).not.toHaveBeenCalled();
  });

  it("网络错误（无 response）→ 不弹全局 toast（仅 HTTP 4xx/5xx 统一提示）", async () => {
    api.defaults.adapter = async (config) => {
      seenConfigs.push(config);
      throw networkError(config);
    };
    await expect(api.get("/x")).rejects.toThrow();
    expect(errorSpy).not.toHaveBeenCalled();
  });

  it("认证/个人资料等自行提示的服务请求带 skipGlobalError", async () => {
    await authService.login({ email: "a@b.c", password: "pw" });
    await authService.register({ email: "a@b.c", password: "pw", password_confirm: "pw", name: "n" });
    await authService.logout("refresh-token");
    await authService.updateProfile({ name: "n" });
    await authService.changePassword({ old_password: "o", new_password: "n", new_password_confirm: "n" });
    expect(seenConfigs).toHaveLength(5);
    for (const cfg of seenConfigs) {
      expect(cfg.skipGlobalError).toBe(true);
    }
  });

  it("RegulationManagePage 自带失败态 → fetchStats 请求 skipGlobalError", async () => {
    await fetchStats();
    expect(seenConfigs.at(-1)?.skipGlobalError).toBe(true);
  });
});
