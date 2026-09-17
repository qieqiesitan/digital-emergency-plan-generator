import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "./api";
import {
  computeCalculation,
  listCalculations,
  listCriticalQuantities,
  listUnits,
  previewCalculation,
  replaceUnitChemicals,
} from "./majorHazardService";

vi.mock("./api", () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

const mocked = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
};

describe("majorHazardService", () => {
  beforeEach(() => vi.clearAllMocks());

  it("listUnits 走 /major-hazard/units 并带 enterprise_id", async () => {
    mocked.get.mockResolvedValue({ data: { data: [{ id: "u1", name: "罐区A" }] } });
    const out = await listUnits("e1");
    expect(mocked.get).toHaveBeenCalledWith("/major-hazard/units", {
      params: { enterprise_id: "e1" },
    });
    expect(out[0].name).toBe("罐区A");
  });

  it("previewCalculation 调 preview 端点", async () => {
    mocked.post.mockResolvedValue({
      data: { data: { s_value: "1.5", r_value: "7.5", chemicals: [] } },
    });
    const out = await previewCalculation("u1", 60);
    expect(mocked.post).toHaveBeenCalledWith("/major-hazard/units/u1/preview", {
      exposed_population: 60,
    });
    expect(out.r_value).toBe("7.5");
  });

  it("computeCalculation 调 compute 端点（固化）", async () => {
    mocked.post.mockResolvedValue({ data: { data: { seq: 1, chemicals: [] } } });
    await computeCalculation("u1", 60);
    expect(mocked.post).toHaveBeenCalledWith("/major-hazard/units/u1/compute", {
      exposed_population: 60,
    });
  });

  it("listCalculations 取快照列表", async () => {
    mocked.get.mockResolvedValue({ data: { data: [{ seq: 2 }, { seq: 1 }] } });
    const out = await listCalculations("u1");
    expect(mocked.get).toHaveBeenCalledWith("/major-hazard/units/u1/calculations");
    expect(out).toHaveLength(2);
  });

  it("listCriticalQuantities 带 keyword 与 limit", async () => {
    mocked.get.mockResolvedValue({ data: { data: [] } });
    await listCriticalQuantities("氯");
    expect(mocked.get).toHaveBeenCalledWith(
      "/major-hazard/definitions/critical-quantities",
      { params: { keyword: "氯", limit: 30 } },
    );
  });

  it("replaceUnitChemicals 整体替换品种清单", async () => {
    mocked.put.mockResolvedValue({ data: { data: { unit_id: "u1", count: 2 } } });
    const out = await replaceUnitChemicals("u1", [
      {
        chemical_name: "氯",
        q_design_max: "5",
        critical_quantity_t: "5",
        beta: "4",
        beta_source: "table3",
      },
    ]);
    expect(mocked.put).toHaveBeenCalledWith("/major-hazard/units/u1/chemicals", [
      expect.objectContaining({ chemical_name: "氯" }),
    ]);
    expect(out.count).toBe(2);
  });
});
