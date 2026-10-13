import { describe, expect, it } from "vitest";
import { buildExistingIndex, buildImportPlan, buildMergeBadges, planZoneTargets } from "./smartGuideImport";
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

    expect(index.zones.get("储罐区")).toEqual(["z1"]);
    expect(index.objects.get("z1")?.get("1#储罐")).toBe("o1");
    expect(index.units.get("o1")?.get("阀门组")).toBe("u1");
    expect(index.events.get("u1")?.has("泄漏")).toBe(true);
    expect(index.events.get("o1")?.has("火灾")).toBe(true);
    expect(index.eventIds.get("u1")?.get("泄漏")).toBe("ev1");
    expect(index.eventIds.get("o1")?.get("火灾")).toBe("ev2");
    expect(index.measures.get("ev2")?.has("engineering|报警器年检")).toBe(true);
  });
});

const existingForBadges: HierarchyZone[] = [
  {
    id: "z1", name: "储罐区", description: null,
    objects: [
      {
        id: "o1", name: "1号储罐", category: null, is_risk_point: false,
        units: [
          {
            id: "u1", name: "罐体", unit_type: null,
            events: [
              {
                id: "ev1", accident_type: "泄漏", description: null, risk_level: null,
                risk_score: null, method_type: "LS", chemical_id: null,
                method_params: {}, measures: [],
              },
            ],
          },
        ],
        events: [
          {
            id: "ev2", accident_type: "火灾", description: null, risk_level: null,
            risk_score: null, method_type: "LS", chemical_id: null,
            method_params: {}, measures: [],
          },
        ],
      },
    ],
  },
];

describe("buildMergeBadges", () => {
  it("已有节点标 merge、新节点标 new（含补单元/补事件/新增对象）", () => {
    const index = buildExistingIndex(existingForBadges);
    const hierarchy: SmartGuideZone[] = [
      {
        name: "储罐区",
        objects: [
          {
            name: "1号储罐",
            units: [
              { name: "罐体", events: [{ accident_type: "泄漏" }, { accident_type: "中毒" }] },
              { name: "阀门组", events: [] },
            ],
          },
          { name: "2号储罐", units: [{ name: "罐体", events: [] }] },
        ],
      },
    ];
    const badges = buildMergeBadges(index, hierarchy, {});
    expect(badges.get("z-0")).toEqual({ kind: "merge", count: 1 });
    expect(badges.get("z-0-o-0")?.kind).toBe("merge");
    expect(badges.get("z-0-o-0-u-0")?.kind).toBe("merge");
    expect(badges.get("z-0-o-0-u-0-ev-0")?.kind).toBe("merge");
    expect(badges.get("z-0-o-0-u-0-ev-1")?.kind).toBe("new");
    expect(badges.get("z-0-o-0-u-1")?.kind).toBe("new");
    expect(badges.get("z-0-o-1")?.kind).toBe("new");
    expect(badges.get("z-0-o-1-u-0")?.kind).toBe("new");
  });

  it("对象级事件按父对象判定；改名 override 参与匹配", () => {
    const index = buildExistingIndex(existingForBadges);
    const hierarchy: SmartGuideZone[] = [
      { name: "罐区", objects: [{ name: "1号罐", events: [{ accident_type: "火灾" }] }] },
    ];
    // 不改名：分区名对不上 → 整条路径全新
    const withoutOverride = buildMergeBadges(index, hierarchy, {});
    expect(withoutOverride.get("z-0")?.kind).toBe("new");
    expect(withoutOverride.get("z-0-o-0")?.kind).toBe("new");
    expect(withoutOverride.get("z-0-o-0-ev-0")?.kind).toBe("new");

    // 用户把分区/对象改名为现有名称 → 并入；对象级事件「火灾」已有 → merge
    const renamed = buildMergeBadges(index, hierarchy, { "z-0": "储罐区", "z-0-o-0": "1号储罐" });
    expect(renamed.get("z-0")?.kind).toBe("merge");
    expect(renamed.get("z-0-o-0")?.kind).toBe("merge");
    expect(renamed.get("z-0-o-0-ev-0")?.kind).toBe("merge");
  });

  it("全新分区其下全部为 new", () => {
    const index = buildExistingIndex(existingForBadges);
    const hierarchy: SmartGuideZone[] = [
      { name: "锅炉房", objects: [{ name: "1号锅炉", units: [{ name: "炉体", events: [{ accident_type: "爆炸" }] }] }] },
    ];
    const badges = buildMergeBadges(index, hierarchy, {});
    expect(badges.get("z-0")?.kind).toBe("new");
    expect(badges.get("z-0-o-0")?.kind).toBe("new");
    expect(badges.get("z-0-o-0-u-0")?.kind).toBe("new");
    expect(badges.get("z-0-o-0-u-0-ev-0")?.kind).toBe("new");
  });
});

// 同名多分区（四色图识别产生的设备位置，如 4 个「加油机」）：AI 段数与现有数量不匹配时的分发/对应策略
const multiNameZones: HierarchyZone[] = [1, 2, 3].map((i) => ({
  id: `pump-${i}`, name: "加油机", description: null, objects: [],
})) as unknown as HierarchyZone[];

describe("planZoneTargets", () => {
  it("无同名分区 → 新建（空目标列表）", () => {
    const index = buildExistingIndex([]);
    const hierarchy: SmartGuideZone[] = [{ name: "锅炉房", objects: [] }];
    const plan = planZoneTargets(index, hierarchy, {});
    expect(plan.get("z-0")).toEqual([]);
  });

  it("常规一对一：1 段对 1 个现有同名分区", () => {
    const index = buildExistingIndex(multiNameZones.slice(0, 1));
    const hierarchy: SmartGuideZone[] = [{ name: "加油机", objects: [] }];
    const plan = planZoneTargets(index, hierarchy, {});
    expect(plan.get("z-0")).toEqual(["pump-1"]);
  });

  it("AI 段数 < 现有同名分区数 → 分发到全部同名分区", () => {
    const index = buildExistingIndex(multiNameZones);
    const hierarchy: SmartGuideZone[] = [{ name: "加油机", objects: [] }];
    const plan = planZoneTargets(index, hierarchy, {});
    expect(plan.get("z-0")).toEqual(["pump-1", "pump-2", "pump-3"]);
  });

  it("AI 段数 = 现有同名分区数 → 按出现顺序一一对应", () => {
    const index = buildExistingIndex(multiNameZones);
    const hierarchy: SmartGuideZone[] = [
      { name: "加油机", objects: [] },
      { name: "加油机", objects: [] },
      { name: "加油机", objects: [] },
    ];
    const plan = planZoneTargets(index, hierarchy, {});
    expect(plan.get("z-0")).toEqual(["pump-1"]);
    expect(plan.get("z-1")).toEqual(["pump-2"]);
    expect(plan.get("z-2")).toEqual(["pump-3"]);
  });

  it("AI 段数 > 现有同名分区数 → 前 k 段一一对应，超出部分新建", () => {
    const index = buildExistingIndex(multiNameZones.slice(0, 2));
    const hierarchy: SmartGuideZone[] = [
      { name: "加油机", objects: [] },
      { name: "加油机", objects: [] },
      { name: "加油机", objects: [] },
    ];
    const plan = planZoneTargets(index, hierarchy, {});
    expect(plan.get("z-0")).toEqual(["pump-1"]);
    expect(plan.get("z-1")).toEqual(["pump-2"]);
    expect(plan.get("z-2")).toEqual([]);
  });

  it("改名 override 参与同名判定", () => {
    const index = buildExistingIndex(multiNameZones);
    const hierarchy: SmartGuideZone[] = [{ name: "加油设备", objects: [] }];
    const renamed = planZoneTargets(index, hierarchy, { "z-0": "加油机" });
    expect(renamed.get("z-0")).toEqual(["pump-1", "pump-2", "pump-3"]);
  });
});

describe("buildMergeBadges 同名分发", () => {
  it("1 段并入 3 个同名分区 → merge ×3（分发）", () => {
    const index = buildExistingIndex(multiNameZones);
    const hierarchy: SmartGuideZone[] = [{ name: "加油机", objects: [] }];
    const badges = buildMergeBadges(index, hierarchy, {});
    expect(badges.get("z-0")).toEqual({ kind: "merge", count: 3 });
  });
});
