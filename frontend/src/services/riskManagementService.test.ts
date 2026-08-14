import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  previewMethod,
  previewRiskMethod,
  previewRiskConversion,
  getAiDualLevelSuggestion,
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

  it("getAiDualLevelSuggestion 请求 AI 双等级建议 URL 并解包 data", async () => {
    apiMock.post.mockResolvedValue({
      data: {
        code: 0,
        message: "ok",
        data: {
          available: true,
          inherent: { risk_level: "重大", risk_score: "D=270" },
          current: { risk_level: "一般", risk_score: "D=21" },
          note: "报警器+联锁降低L",
        },
      },
    });

    const result = await getAiDualLevelSuggestion("e1", "ev1");

    expect(apiMock.post).toHaveBeenCalledWith(
      "/enterprises/e1/risk-management/events/ev1/ai-dual-level-suggestion",
    );
    expect(result).toEqual({
      available: true,
      inherent: { risk_level: "重大", risk_score: "D=270" },
      current: { risk_level: "一般", risk_score: "D=21" },
      note: "报警器+联锁降低L",
    });
  });

  it("getControlList 请求管控清单 URL 并透传筛选分页参数", async () => {
    const response = {
      data: { code: 0, message: "ok", data: { items: [], total: 0 } },
    };
    apiMock.get.mockResolvedValue(response);

    const result = await getControlList("e1", { floor_id: "f1", keyword: "仓库", page: 2, size: 50 });

    expect(apiMock.get).toHaveBeenCalledWith(
      "/enterprises/e1/risk-management/control-list",
      { params: { floor_id: "f1", keyword: "仓库", page: 2, size: 50 } },
    );
    // 服务内已解包 ApiResponse.data，直接返回业务数据
    expect(result).toEqual({ items: [], total: 0 });
  });

  it("exportControlList 以 blob responseType 请求导出 URL（无筛选时不带 params）", async () => {
    const response = { data: new Blob(["xlsx"]) };
    apiMock.get.mockResolvedValue(response);

    const result = await exportControlList("e1");

    expect(apiMock.get).toHaveBeenCalledWith(
      "/enterprises/e1/risk-management/control-list/export",
      { responseType: "blob" },
    );
    // 导出需响应体构造 blob 下载，保留 AxiosResponse
    expect(result).toBe(response);
  });

  it("exportControlList 透传当前筛选参数", async () => {
    const response = { data: new Blob(["xlsx"]) };
    apiMock.get.mockResolvedValue(response);

    const result = await exportControlList("e1", { floor_id: "f1", level: "重大", keyword: "仓库" });

    expect(apiMock.get).toHaveBeenCalledWith(
      "/enterprises/e1/risk-management/control-list/export",
      { params: { floor_id: "f1", level: "重大", keyword: "仓库" }, responseType: "blob" },
    );
    expect(result).toBe(response);
  });

  it("risk-publicity / token 重置 / 公开脱敏页 请求对应 URL", async () => {
    const publicity = {
      token: "t1",
      enterprise_name: "e1",
      items: [],
      zones: [],
      generated_at: "",
    };
    apiMock.get.mockResolvedValue({
      data: {
        code: 0,
        message: "ok",
        data: publicity,
      },
    });
    const publicityResult = await getRiskPublicity("e1");
    expect(apiMock.get).toHaveBeenCalledWith("/enterprises/e1/risk-management/risk-publicity");
    expect(publicityResult).toEqual(publicity);

    const tokenData = { token: "t2" };
    apiMock.post.mockResolvedValue({
      data: { code: 0, message: "ok", data: tokenData },
    });
    const resetResult = await resetRiskPublicityToken("e1");
    expect(apiMock.post).toHaveBeenCalledWith("/enterprises/e1/risk-management/risk-publicity/token");
    expect(resetResult).toEqual(tokenData);

    const publicData = { enterprise_name: "e1", items: [], generated_at: "" };
    apiMock.get.mockResolvedValue({
      data: { code: 0, message: "ok", data: publicData },
    });
    const publicResult = await fetchPublicRisk("tk-123");
    expect(apiMock.get).toHaveBeenCalledWith("/public/risk/tk-123");
    expect(publicResult).toEqual(publicData);
  });
});
