import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  previewMethod,
  previewRiskMethod,
  previewRiskConversion,
} from "./riskManagementService";

const { apiMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

vi.mock("@/services/api", () => ({ default: apiMock }));

describe("riskManagementService dual-level", () => {
  beforeEach(() => vi.clearAllMocks());

  it("previewRiskMethod 透传 scenario 到预览端点", async () => {
    apiMock.post.mockResolvedValue({
      data: {
        code: 0,
        message: "ok",
        data: { risk_level: "重大", risk_score: "R=20", action: "立即整改", scenario: "inherent" },
      },
    });

    const result = await previewRiskMethod("e1", {
      method_id: "m1",
      params: { L: 4, S: 5 },
      scenario: "inherent",
    });

    expect(apiMock.post).toHaveBeenCalledWith(
      "/enterprises/e1/risk-management/methods/preview",
      { method_id: "m1", params: { L: 4, S: 5 }, scenario: "inherent" },
    );
    expect(result.scenario).toBe("inherent");
  });

  it("previewRiskMethod 不传 scenario 时保持向后兼容（payload 不含 scenario）", async () => {
    apiMock.post.mockResolvedValue({
      data: { code: 0, message: "ok", data: { risk_level: "一般", risk_score: "R=9", action: "" } },
    });

    await previewRiskMethod("e1", { method_id: "m1", params: { L: 3, S: 3 } });

    expect(apiMock.post).toHaveBeenCalledWith(
      "/enterprises/e1/risk-management/methods/preview",
      { method_id: "m1", params: { L: 3, S: 3 } },
    );
  });

  it("previewMethod 旧签名仍可用并调用同一端点", async () => {
    apiMock.post.mockResolvedValue({
      data: { code: 0, message: "ok", data: { risk_level: "较大", risk_score: "R=15", action: "" } },
    });

    const result = await previewMethod("e1", "m1", { L: 3, S: 5 });

    expect(apiMock.post).toHaveBeenCalledWith(
      "/enterprises/e1/risk-management/methods/preview",
      { method_id: "m1", params: { L: 3, S: 5 } },
    );
    expect(result.risk_level).toBe("较大");
  });

  it("previewRiskConversion 请求折算参考 URL 并解包 data", async () => {
    apiMock.get.mockResolvedValue({
      data: {
        code: 0,
        message: "ok",
        data: { factor: 0.5, reference_score: 10, reference_level: "一般" },
      },
    });

    const result = await previewRiskConversion("e1", "ev1");

    expect(apiMock.get).toHaveBeenCalledWith(
      "/enterprises/e1/risk-management/events/ev1/conversion-reference",
    );
    expect(result).toEqual({ factor: 0.5, reference_score: 10, reference_level: "一般" });
  });
});
