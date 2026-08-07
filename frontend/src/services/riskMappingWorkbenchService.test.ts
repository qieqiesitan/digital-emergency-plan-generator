import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  analyzeFourColorMap,
  cancelFourColorImport,
  commitFourColorImport,
} from "./riskMappingWorkbenchService";
import type { FourColorAnalyzeResult } from "@/types/riskMappingWorkbench";

const { apiMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

vi.mock("@/services/api", () => ({ default: apiMock }));

describe("riskMappingWorkbenchService four-color", () => {
  beforeEach(() => vi.clearAllMocks());

  it("analyzeFourColorMap 上传文件并解包 data", async () => {
    const data: FourColorAnalyzeResult = {
      preview_url: "/uploads/x.png",
      canvas_width: 600,
      canvas_height: 450,
      zones: [{
        client_id: "d1",
        name: "原料库",
        risk_level: "重大",
        color: "#ff4d4f",
        suspected: true,
        suggested_name: "原料库",
        ai_hint: "疑似Logo",
        polygons: [{ id: "p1", label: null, points: [{ x: 10, y: 10 }, { x: 30, y: 10 }, { x: 30, y: 40 }] }],
      }],
      excluded: [{
        color: "红",
        reason: "legend",
        polygons: [{ id: "p2", label: null, points: [{ x: 80, y: 5 }, { x: 90, y: 5 }, { x: 90, y: 10 }] }],
      }],
      texts: [{ points: [{ x: 10, y: 10 }, { x: 30, y: 10 }, { x: 30, y: 12 }, { x: 10, y: 12 }], text: "原料库", confidence: 0.9 }],
      warnings: [],
    };
    apiMock.post.mockResolvedValue({ data: { code: 0, message: "ok", data } });
    const file = new File(["x"], "a.png", { type: "image/png" });
    const result = await analyzeFourColorMap("e1", "f1", file);
    expect(apiMock.post).toHaveBeenCalledWith(
      "/enterprises/e1/risk-management/floors/f1/four-color/analyze",
      expect.any(FormData),
    );
    expect(result.canvas_width).toBe(600);
    expect(result.zones[0].risk_level).toBe("重大");
    expect(result.excluded[0].reason).toBe("legend");
    expect(result.zones[0].suggested_name).toBe("原料库");
    expect(result.zones[0].ai_hint).toBe("疑似Logo");
    expect(result.texts[0].text).toBe("原料库");
  });

  it("commitFourColorImport 提交 payload 并解包 data", async () => {
    apiMock.post.mockResolvedValue({
      data: { code: 0, message: "ok", data: { floor: { id: "f1" }, zones: [] } },
    });
    const result = await commitFourColorImport("e1", "f1", {
      file_token: "abc",
      zones: [{ name: "分区1", risk_level: "低", polygons: [{ points: [{ x: 1, y: 2 }, { x: 3, y: 4 }, { x: 5, y: 6 }] }] }],
      replace_existing: true,
    });
    expect(apiMock.post).toHaveBeenCalledWith(
      "/enterprises/e1/risk-management/floors/f1/four-color/commit",
      expect.objectContaining({ file_token: "abc", replace_existing: true }),
    );
    expect(result.floor.id).toBe("f1");
  });

  it("cancelFourColorImport 调用 DELETE", async () => {
    apiMock.delete.mockResolvedValue({ data: { code: 0, message: "ok", data: null } });
    await cancelFourColorImport("e1", "f1", "tok123");
    expect(apiMock.delete).toHaveBeenCalledWith(
      "/enterprises/e1/risk-management/floors/f1/four-color/tok123",
    );
  });
});
