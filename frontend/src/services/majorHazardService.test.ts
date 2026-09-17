import { beforeEach, describe, expect, it, vi } from "vitest";
import api from "./api";
import {
  computeCalculation,
  linkRiskObject,
  listCalculations,
  listCriticalQuantities,
  listLedgerChemicals,
  listLinkableRiskObjects,
  listUnits,
  previewCalculation,
  replaceUnitChemicals,
  setUnitPolygon,
  suggestDesignMaxFromLedger,
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

  // --- 跨模块关联（计划 7） ---

  it("setUnitPolygon 楼层与落点成对提交", async () => {
    mocked.put.mockResolvedValue({ data: { data: { unit_id: "u1", floor_id: "f1" } } });
    const polygon = {
      version: 1 as const,
      points: [
        { x: 10, y: 10 },
        { x: 40, y: 10 },
        { x: 40, y: 40 },
      ],
    };
    await setUnitPolygon("u1", { floor_id: "f1", polygon });
    expect(mocked.put).toHaveBeenCalledWith("/major-hazard/units/u1/polygon", {
      floor_id: "f1",
      polygon,
    });
  });

  it("setUnitPolygon 清空时两个字段都为 null", async () => {
    mocked.put.mockResolvedValue({ data: { data: { unit_id: "u1", floor_id: null } } });
    await setUnitPolygon("u1", { floor_id: null, polygon: null });
    expect(mocked.put).toHaveBeenCalledWith("/major-hazard/units/u1/polygon", {
      floor_id: null,
      polygon: null,
    });
  });

  it("listLinkableRiskObjects 带 enterprise_id", async () => {
    mocked.get.mockResolvedValue({ data: { data: [{ id: "o1", name: "罐区A风险点" }] } });
    const out = await listLinkableRiskObjects("e1");
    expect(mocked.get).toHaveBeenCalledWith("/major-hazard/linkable/risk-objects", {
      params: { enterprise_id: "e1" },
    });
    expect(out[0].id).toBe("o1");
  });

  it("linkRiskObject 传 null 表示解除关联", async () => {
    mocked.put.mockResolvedValue({ data: { data: { unit_id: "u1", risk_object_id: null } } });
    await linkRiskObject("u1", null);
    expect(mocked.put).toHaveBeenCalledWith("/major-hazard/units/u1/risk-object", {
      risk_object_id: null,
    });
  });

  it("listLedgerChemicals 取本企业台账", async () => {
    mocked.get.mockResolvedValue({ data: { data: [{ id: "c1", name: "甲醇" }] } });
    const out = await listLedgerChemicals("e1");
    expect(mocked.get).toHaveBeenCalledWith("/major-hazard/ledger/chemicals", {
      params: { enterprise_id: "e1" },
    });
    expect(out[0].name).toBe("甲醇");
  });

  it("suggestDesignMaxFromLedger 只取建议值且标注需确认", async () => {
    mocked.get.mockResolvedValue({
      data: {
        data: {
          chemical_id: "c1",
          chemical_name: "甲醇",
          suggested_q: 40,
          source: "structured",
          hint: "设计最大量口径…",
          requires_confirmation: true,
        },
      },
    });
    const out = await suggestDesignMaxFromLedger("c1", "e1");
    expect(mocked.get).toHaveBeenCalledWith(
      "/major-hazard/ledger/chemicals/c1/suggest-design-max",
      { params: { enterprise_id: "e1" } },
    );
    expect(out.suggested_q).toBe(40);
    expect(out.requires_confirmation).toBe(true);
  });
});
