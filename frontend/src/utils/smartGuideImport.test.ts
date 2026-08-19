import { describe, expect, it } from "vitest";
import { buildExistingIndex, buildImportPlan } from "./smartGuideImport";
import type { HierarchyZone, SmartGuideZone } from "@/types/riskManagement";

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

describe("buildExistingIndex", () => {
  it("按 分区/对象/单元/事件/措施 构建去重索引", () => {
    const zones: HierarchyZone[] = [
      {
        id: "z1", name: "储罐区", description: null,
        objects: [
          {
            id: "o1", name: "1#储罐", category: null, is_risk_point: false,
            units: [
              {
                id: "u1", name: "阀门组", unit_type: "班组",
                events: [
                  {
                    id: "ev1", accident_type: "泄漏", description: null, risk_level: "较大",
                    risk_score: "R=12", method_type: "LS", chemical_id: null,
                    method_params: { l: 3, s: 4 }, measures: [],
                  },
                ],
              },
            ],
            events: [
              {
                id: "ev2", accident_type: "火灾", description: null, risk_level: "重大",
                risk_score: "R=16", method_type: "LS", chemical_id: null,
                method_params: { l: 4, s: 4 },
                measures: [{ id: "m1", measure_category: "engineering", measure_type: null, description: "报警器年检", status: "pending", check_items: [] }],
              },
            ],
          },
        ],
      },
    ];

    const index = buildExistingIndex(zones);

    expect(index.zones.get("储罐区")).toBe("z1");
    expect(index.objects.get("储罐区")?.get("1#储罐")).toBe("o1");
    expect(index.units.get("o1")?.get("阀门组")).toBe("u1");
    expect(index.events.get("u1")?.has("泄漏")).toBe(true);
    expect(index.events.get("o1")?.has("火灾")).toBe(true);
    expect(index.eventIds.get("u1")?.get("泄漏")).toBe("ev1");
    expect(index.eventIds.get("o1")?.get("火灾")).toBe("ev2");
    expect(index.measures.get("ev2")?.has("engineering|报警器年检")).toBe(true);
  });
});
