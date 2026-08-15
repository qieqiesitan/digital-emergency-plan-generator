import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  aiOptimize,
  exportCards,
  fetchCardDetail,
  fetchCardSummaries,
  fetchPublicCard,
  resetToken,
  saveSnapshot,
} from "./riskNoticeCardService";
import type { CardData, CardSummary, RightColumn, SnapshotInfo } from "@/types/riskNoticeCard";

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
      has_open_hazard: false,
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

  it("exportCards POST object_ids 并返回 { file_key, warnings }", async () => {
    apiMock.post.mockResolvedValue({
      data: { code: 0, message: "ok", data: { file_key: "cards.docx", warnings: ["o2 不存在"] } },
    });

    const result = await exportCards("e1", ["o1", "o2"]);

    expect(apiMock.post).toHaveBeenCalledWith("/enterprises/e1/risk-notice-cards/export", {
      object_ids: ["o1", "o2"],
    });
    expect(result).toEqual({ file_key: "cards.docx", warnings: ["o2 不存在"] });
  });

  it("fetchCardDetail 调用 GET 详情端点并解包返回单卡数据", async () => {
    const card: CardData = {
      object_id: "o1",
      enterprise_name: "示例企业",
      name: "储罐区",
      code: "OBJ-001",
      level: "重大",
      level_color: "#ff4d4f",
      responsible_unit: "安环部",
      responsible_person: "张三",
      contact_phone: "13800000000",
      fallback_used: false,
      has_open_hazard: false,
      signs: [{ category: "warning", name: "当心火灾", svg_name: "warning-fire.svg" }],
      snapshot: null,
      stale: false,
      public_url: "/r/tok1",
      generated_at: "2026-08-11T12:00:00Z",
      hazard_description: "易燃液体泄漏遇火源",
      accident_types: ["火灾"],
      control_measures: ["静电接地"],
      emergency_measures: ["切断火源"],
    };
    apiMock.get.mockResolvedValue({ data: { code: 0, message: "ok", data: card } });

    const result = await fetchCardDetail("e1", "o1");

    expect(apiMock.get).toHaveBeenCalledWith("/enterprises/e1/risk-notice-cards/o1");
    expect(result).toEqual(card);
  });

  it("aiOptimize POST ai-optimize 并返回原版与优化版对比", async () => {
    const original: RightColumn = {
      hazard_description: "易燃液体泄漏遇火源",
      accident_types: ["火灾"],
      control_measures: ["静电接地"],
      emergency_measures: ["切断火源"],
    };
    const optimized: RightColumn = {
      ...original,
      control_measures: ["静电接地", "安装可燃气体报警器"],
    };
    apiMock.post.mockResolvedValue({
      data: { code: 0, message: "ok", data: { original, optimized } },
    });

    const result = await aiOptimize("e1", "o1");

    expect(apiMock.post).toHaveBeenCalledWith("/enterprises/e1/risk-notice-cards/o1/ai-optimize");
    expect(result).toEqual({ original, optimized });
  });

  it("saveSnapshot PUT snapshot 携带 content body 并返回快照信息", async () => {
    const content: RightColumn = {
      hazard_description: "易燃液体泄漏遇火源",
      accident_types: ["火灾"],
      control_measures: ["静电接地"],
      emergency_measures: ["切断火源"],
    };
    const snapshot: SnapshotInfo = { version: 2, source: "ai" };
    apiMock.put.mockResolvedValue({ data: { code: 0, message: "ok", data: snapshot } });

    const result = await saveSnapshot("e1", "o1", content);

    expect(apiMock.put).toHaveBeenCalledWith("/enterprises/e1/risk-notice-cards/o1/snapshot", {
      content,
    });
    expect(result).toEqual(snapshot);
  });

  it("resetToken POST token/reset 并返回 public_url", async () => {
    apiMock.post.mockResolvedValue({
      data: { code: 0, message: "ok", data: { public_url: "/r/newtok" } },
    });

    const result = await resetToken("e1", "o1");

    expect(apiMock.post).toHaveBeenCalledWith("/enterprises/e1/risk-notice-cards/o1/token/reset");
    expect(result).toBe("/r/newtok");
  });

  it("fetchPublicCard 调用无鉴权公开端点并解包返回卡片数据", async () => {
    const card: CardData = {
      object_id: "o1",
      enterprise_name: "示例企业",
      name: "储罐区",
      code: "OBJ-001",
      level: "重大",
      level_color: "#ff4d4f",
      responsible_unit: "安环部",
      responsible_person: "张三",
      contact_phone: "13800000000",
      fallback_used: false,
      has_open_hazard: false,
      signs: [{ category: "warning", name: "当心火灾", svg_name: "warning-fire.svg" }],
      snapshot: null,
      stale: false,
      public_url: "/r/tok1",
      generated_at: "2026-08-11T12:00:00Z",
      hazard_description: "易燃液体泄漏遇火源",
      accident_types: ["火灾"],
      control_measures: ["静电接地"],
      emergency_measures: ["切断火源"],
    };
    apiMock.get.mockResolvedValue({ data: { code: 0, message: "ok", data: card } });

    const result = await fetchPublicCard("tok1");

    expect(apiMock.get).toHaveBeenCalledWith("/public/risk-notice-cards/tok1");
    expect(result).toEqual(card);
  });
});
