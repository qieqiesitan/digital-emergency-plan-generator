import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  exportCards,
  fetchCardSummaries,
  fetchPublicCard,
} from "./riskNoticeCardService";
import type { CardSummary } from "@/types/riskNoticeCard";

const { apiMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
}));

vi.mock("@/services/api", () => ({ default: apiMock }));

describe("riskNoticeCardService", () => {
  beforeEach(() => vi.clearAllMocks());

  it("fetchCardSummaries 调用 GET 列表端点并携带筛选参数", async () => {
    const summary: CardSummary = {
      object_id: "o1",
      name: "储罐区",
      zone_name: "生产区",
      level: "重大",
      level_color: "#ff4d4f",
      accident_types: ["火灾"],
      signs: [{ category: "warning", name: "当心火灾", svg_name: "warning-fire.svg" }],
      responsible_unit: "安环部",
      snapshot: null,
      stale: false,
      public_url: "/r/tok1",
    };
    apiMock.get.mockResolvedValue({ data: { code: 0, message: "ok", data: [summary] } });

    const result = await fetchCardSummaries("e1", { level: "重大", keyword: "储罐" });

    expect(apiMock.get).toHaveBeenCalledWith("/enterprises/e1/risk-notice-cards", {
      params: { level: "重大", keyword: "储罐" },
    });
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("储罐区");
  });

  it("exportCards POST object_ids 并返回 file_key", async () => {
    apiMock.post.mockResolvedValue({
      data: { code: 0, message: "ok", data: { file_key: "cards.docx", warnings: [] } },
    });

    const result = await exportCards("e1", ["o1", "o2"]);

    expect(apiMock.post).toHaveBeenCalledWith("/enterprises/e1/risk-notice-cards/export", {
      object_ids: ["o1", "o2"],
    });
    expect(result).toBe("cards.docx");
  });

  it("fetchPublicCard 调用无鉴权公开端点", async () => {
    apiMock.get.mockResolvedValue({ data: { code: 0, message: "ok", data: { object_id: "o1" } } });

    await fetchPublicCard("tok1");

    expect(apiMock.get).toHaveBeenCalledWith("/public/risk-notice-cards/tok1");
  });
});
