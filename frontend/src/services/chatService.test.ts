import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { sendChatMessage } from "./chatService";

describe("sendChatMessage 非 2xx 错误路径（I7：AI 未配置 400）", () => {
  const storage = new Map<string, string>();

  beforeEach(() => {
    storage.clear();
    storage.set("access_token", "test-token");
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => (storage.has(key) ? storage.get(key)! : null),
      setItem: (key: string, value: string) => { storage.set(key, value); },
      removeItem: (key: string) => { storage.delete(key); },
      clear: () => storage.clear(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("HTTP 400（detail=系统未配置 AI 模型）→ onError 收到完整 detail，可被前端分类为未配置引导", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ detail: "系统未配置 AI 模型，请联系管理员" }), {
          status: 400,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    const onError = vi.fn();
    const onComplete = vi.fn();
    sendChatMessage("你好", [], null, () => {}, onError, onComplete);

    await vi.waitFor(() => expect(onError).toHaveBeenCalled());
    expect(onError).toHaveBeenCalledWith("系统未配置 AI 模型，请联系管理员");
    // 错误路径不得触发 onComplete（Chat 的 "（无回复）" 兜底只在 onComplete 走）
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("HTTP 500（detail=模型服务异常）→ onError 收到 detail，用于通用错误展示", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ detail: "模型服务异常" }), {
          status: 500,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    const onError = vi.fn();
    sendChatMessage("你好", [], "conv-1", () => {}, onError, () => {});

    await vi.waitFor(() => expect(onError).toHaveBeenCalled());
    expect(onError).toHaveBeenCalledWith("模型服务异常");
  });
});
