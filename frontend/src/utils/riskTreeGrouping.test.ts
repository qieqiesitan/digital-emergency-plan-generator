import { describe, it, expect } from "vitest";
import { groupZonesByFloor } from "./riskTreeGrouping";
import type { HierarchyZone } from "@/types/riskManagement";
import type { EnterpriseFloor } from "@/types/riskMappingWorkbench";

function zone(id: string, floorId: string | null): HierarchyZone {
  return {
    id,
    name: `分区-${id}`,
    description: null,
    floor_id: floorId,
    floor_name: floorId ? `楼层-${floorId}` : null,
    floor_plan_polygon: null,
    objects: [],
  };
}

function floor(id: string, name: string, isDefault = false, sortOrder = 0): EnterpriseFloor {
  return {
    id,
    enterprise_id: "e1",
    name,
    sort_order: sortOrder,
    floor_plan_url: null,
    canvas_texts: [],
    is_default: isDefault,
    zone_count: 0,
    risk_point_count: 0,
    updated_at: "2026-08-06T00:00:00+08:00",
  };
}

describe("groupZonesByFloor", () => {
  it("groups zones by floor in floor sort order", () => {
    const floors = [floor("f2", "二层", false, 1), floor("f1", "一层", true, 0)];
    const groups = groupZonesByFloor([zone("a", "f1"), zone("b", "f2"), zone("c", "f1")], floors);

    expect(groups.map((g) => g.floorId)).toEqual(["f1", "f2"]);
    expect(groups[0].zones.map((z) => z.id)).toEqual(["a", "c"]);
    expect(groups[1].zones.map((z) => z.id)).toEqual(["b"]);
    expect(groups[0].isDefault).toBe(true);
  });

  it("collects null or unknown floor zones into a trailing unassigned group", () => {
    const floors = [floor("f1", "一层")];
    const groups = groupZonesByFloor([zone("x", null), zone("y", "ghost")], floors);

    expect(groups).toHaveLength(1);
    expect(groups[0].floorName).toBe("未分配楼层");
    expect(groups[0].zones.map((z) => z.id)).toEqual(["x", "y"]);
  });

  it("hides floors that have no zones", () => {
    const floors = [floor("f1", "一层", true), floor("f2", "二层")];
    const groups = groupZonesByFloor([zone("a", "f1")], floors);

    expect(groups.map((g) => g.floorId)).toEqual(["f1"]);
  });
});
