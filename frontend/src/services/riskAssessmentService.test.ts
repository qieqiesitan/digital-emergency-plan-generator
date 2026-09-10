import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { generateRiskAssessmentStream } from "./riskAssessmentService";

describe("generateRiskAssessmentStream 参数顺序（回归：e9a34d1 重排导致桌面/移动端卡「准备开始」）", () => {
  const storage = new Map<string, string>();

  beforeEach(() => {
    storage.clear();
    storage.set("access_token", "test-token");
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => (storage.has(key) ? storage.get(key)! : null),
      setItem: (key: string, value: string) => {
        storage.set(key, value);
      },
      removeItem: (key: string) => {
        storage.delete(key);
      },
      clear: () => storage.clear(),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // 与全部 4 个调用方（桌面/移动 RiskAssessmentTab/Screen）一致的调用顺序：
  // (enterpriseId, customInstruction, onEvent, onError, onComplete)
  it("按调用方顺序传参时，SSE progress 事件送达 onEvent 且结束时触发 onComplete", async () => {
    const sseBody =
      'data: {"type":"progress","message":"开始逐章生成风险评估报告（共5章）...","current":0,"total":5}\n\n' +
      'data: {"type":"progress","message":"正在生成「一、危险有害因素辨识分析」（1/5）","current":1,"total":5,"section_key":"ch1_hazard_id"}\n\n';
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        body: {
          getReader: () => {
            let i = 0;
            const chunks = [new TextEncoder().encode(sseBody)];
            return {
              read: async () =>
                i < chunks.length
                  ? { done: false, value: chunks[i++] }
                  : { done: true, value: undefined },
            };
          },
        },
      })),
    );

    const onEvent = vi.fn();
    const onError = vi.fn();
    const onComplete = vi.fn();
    generateRiskAssessmentStream(
      "enterprise-1",
      undefined,
      onEvent,
      onError,
      onComplete,
    );

    await vi.waitFor(() => expect(onEvent).toHaveBeenCalled());
    expect(onEvent.mock.calls[0][0]).toMatchObject({
      type: "progress",
      current: 0,
      total: 5,
    });
    expect(onEvent.mock.calls[1][0]).toMatchObject({
      type: "progress",
      section_key: "ch1_hazard_id",
    });
    expect(onComplete).toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
  });

  it("HTTP 400 → onError 收到后端 message（不得把错误误投给 onEvent）", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(JSON.stringify({ message: "生成请求失败" }), {
          status: 400,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    const onEvent = vi.fn();
    const onError = vi.fn();
    const onComplete = vi.fn();
    generateRiskAssessmentStream(
      "enterprise-1",
      undefined,
      onEvent,
      onError,
      onComplete,
    );

    await vi.waitFor(() => expect(onError).toHaveBeenCalled());
    expect(onError).toHaveBeenCalledWith("生成请求失败");
    expect(onEvent).not.toHaveBeenCalled();
    expect(onComplete).not.toHaveBeenCalled();
  });
});
