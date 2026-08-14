import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  previewMethod,
  previewRiskMethod,
  previewRiskConversion,
  getControlList,
  exportControlList,
  getRiskPublicity,
  resetRiskPublicityToken,
  fetchPublicRisk,
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

  it("getControlList 请求管控清单 URL 并透传筛选分页参数", async () => {
    apiMock.get.mockResolvedValue({
      data: { code: 0, message: "ok", data: { items: [], total: 0 } },
    });

    await getControlList("e1", { floor_id: "f1", keyword: "仓库", page: 2, size: 50 });

    expect(apiMock.get).toHaveBeenCalledWith(
      "/enterprises/e1/risk-management/control-list",
      { params: { floor_id: "f1", keyword: "仓库", page: 2, size: 50 } },
    );
  });

  it("exportControlList 以 blob responseType 请求导出 URL", async () => {
    apiMock.get.mockResolvedValue({ data: new Blob(["xlsx"]) });

    await exportControlList("e1");

    expect(apiMock.get).toHaveBeenCalledWith(
      "/enterprises/e1/risk-management/control-list/export",
      { responseType: "blob" },
    );
  });

  it("risk-publicity / token 重置 / 公开脱敏页 请求对应 URL", async () => {
    apiMock.get.mockResolvedValue({
      data: {
        code: 0,
        message: "ok",
        data: { token: "t1", enterprise_name: "e1", items: [], zones: [], generated_at: "" },
      },
    });
    await getRiskPublicity("e1");
    expect(apiMock.get).toHaveBeenCalledWith("/enterprises/e1/risk-management/risk-publicity");

    apiMock.post.mockResolvedValue({
      data: { code: 0, message: "ok", data: { token: "t2" } },
    });
    await resetRiskPublicityToken("e1");
    expect(apiMock.post).toHaveBeenCalledWith("/enterprises/e1/risk-management/risk-publicity/token");

    apiMock.get.mockResolvedValue({
      data: { code: 0, message: "ok", data: { enterprise_name: "e1", items: [], generated_at: "" } },
    });
    await fetchPublicRisk("tk-123");
    expect(apiMock.get).toHaveBeenCalledWith("/public/risk/tk-123");
  });
});
