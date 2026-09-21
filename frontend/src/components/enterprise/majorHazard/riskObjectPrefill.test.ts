import { describe, expect, it } from "vitest";
import type { LinkableRiskObject } from "@/types/majorHazard";
import { buildUnitPrefill, isPrefillMarkVisible } from "./riskObjectPrefill";

const SOURCE: LinkableRiskObject = {
  id: "o1",
  name: "罐区A风险点",
  location: "厂区北侧罐区东侧",
  responsible_unit: "生产运行部",
  responsible_person: "张峰",
  contact_phone: "13800000000",
};

describe("buildUnitPrefill（风险点 → 单元表单）", () => {
  it("空白项全部带出", () => {
    const { patch, fields } = buildUnitPrefill(SOURCE, {});
    expect(patch).toEqual({
      address: "厂区北侧罐区东侧",
      department: "生产运行部",
      responsible_person: "张峰",
      responsible_phone: "13800000000",
    });
    expect(fields).toEqual([
      "address",
      "department",
      "responsible_person",
      "responsible_phone",
    ]);
  });

  it("已填字段不被覆盖", () => {
    const { patch, fields } = buildUnitPrefill(SOURCE, { department: "人工填的部门" });
    expect(patch.department).toBeUndefined();
    expect(patch.address).toBe("厂区北侧罐区东侧");
    expect(fields).not.toContain("department");
  });

  it("纯空格视为空白", () => {
    const { patch } = buildUnitPrefill(SOURCE, { address: "   " });
    expect(patch.address).toBe("厂区北侧罐区东侧");
  });

  it("来源字段为空则不产出该项", () => {
    const { patch, fields } = buildUnitPrefill(
      { id: "o2", name: "空风险点", location: "" },
      {},
    );
    expect(patch).toEqual({});
    expect(fields).toEqual([]);
  });

  it("不产出名称、楼层与多边形", () => {
    const { patch } = buildUnitPrefill(SOURCE, {});
    expect("name" in patch).toBe(false);
    expect("floor_id" in patch).toBe(false);
    expect("polygon" in patch).toBe(false);
  });
});

describe("isPrefillMarkVisible（来源标记）", () => {
  it("值仍是带出时的原值 → 显示", () => {
    expect(isPrefillMarkVisible({ address: "厂区北侧" }, "address", "厂区北侧")).toBe(true);
  });

  it("用户改过 → 不显示", () => {
    expect(isPrefillMarkVisible({ address: "厂区北侧" }, "address", "厂区北侧（改）")).toBe(false);
  });

  it("该字段没被带出过 → 不显示", () => {
    expect(isPrefillMarkVisible({ address: "厂区北侧" }, "department", "生产运行部")).toBe(false);
  });
});
