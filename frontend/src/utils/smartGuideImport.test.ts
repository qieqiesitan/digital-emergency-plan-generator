import { describe, expect, it } from "vitest";
import { buildImportPlan } from "./smartGuideImport";
import type { SmartGuideZone } from "@/types/riskManagement";

const hierarchy: SmartGuideZone[] = [
  { name: "储罐区", objects: [] },
  { name: "新车间", objects: [] },
  { name: "储罐区", objects: [] },
];

describe("buildImportPlan", () => {
  it("过滤与现有分区重名的分区并计数", () => {
    const { filteredHierarchy, skippedZones } = buildImportPlan(hierarchy, {}, new Set(["储罐区"]));
    expect(filteredHierarchy.map(z => z.name)).toEqual(["新车间"]);
    expect(skippedZones).toEqual(["储罐区", "储罐区"]);
  });

  it("nameOverrides 改名后的名称参与去重", () => {
    const { filteredHierarchy, skippedZones } = buildImportPlan(
      hierarchy,
      { "z-1": "储罐区" },
      new Set(["储罐区"]),
    );
    // 原始"储罐区"、"新车间"改名后、以及重名"储罐区"全部命中现有集合
    expect(filteredHierarchy).toEqual([]);
    expect(skippedZones).toEqual(["储罐区", "储罐区", "储罐区"]);
  });
});
