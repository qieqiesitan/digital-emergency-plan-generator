import { describe, it, expect } from "vitest";
import type { WorkbenchZone } from "@/types/riskMappingWorkbench";
import { RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";
import { zoneDisplayColor, zoneDisplayLevel } from "./zoneDisplay";

function makeZone(overrides: Partial<WorkbenchZone> = {}): WorkbenchZone {
  return {
    id: "z1",
    enterprise_id: "e1",
    floor_id: "f1",
    floor_name: "一层",
    name: "原料库",
    description: null,
    sort_order: 0,
    floor_plan_polygon: null,
    max_risk_level: "较大",
    effective_color: "#fa8c16",
    inherent_max_level: "低",
    inherent_effective_color: "#52c41a",
    object_count: 0,
    created_at: "2026-09-08T00:00:00+08:00",
    updated_at: "2026-09-08T00:00:00+08:00",
    objects: [],
    ...overrides,
  };
}

describe("zoneDisplayColor", () => {
  it("手动指定等级后立即返回该等级色，即使 effective_color 字段仍是旧值", () => {
    const zone = makeZone({
      effective_color: "#fa8c16", // 陈旧派生值
      floor_plan_polygon: {
        version: 2,
        level_mode: "manual",
        risk_level: "重大",
        polygons: [],
      },
    });
    expect(zoneDisplayColor(zone, "current")).toBe(RISK_LEVEL_COLORS["重大"]);
    expect(zoneDisplayColor(zone, "inherent")).toBe(RISK_LEVEL_COLORS["重大"]);
  });

  it("auto 模式 current 读 effective_color", () => {
    const zone = makeZone();
    expect(zoneDisplayColor(zone, "current")).toBe("#fa8c16");
  });

  it("auto 模式 inherent 优先读 inherent_effective_color", () => {
    const zone = makeZone();
    expect(zoneDisplayColor(zone, "inherent")).toBe("#52c41a");
  });

  it("auto 模式无任何颜色时兜底灰色", () => {
    const zone = makeZone({ effective_color: null, inherent_effective_color: null });
    expect(zoneDisplayColor(zone, "current")).toBe("#d9d9d9");
  });
});

describe("zoneDisplayLevel", () => {
  it("手动指定等级时返回该等级", () => {
    const zone = makeZone({
      max_risk_level: "较大",
      floor_plan_polygon: {
        version: 2,
        level_mode: "manual",
        risk_level: "重大",
        polygons: [],
      },
    });
    expect(zoneDisplayLevel(zone)).toBe("重大");
  });

  it("auto 模式返回后端推导等级", () => {
    expect(zoneDisplayLevel(makeZone())).toBe("较大");
  });

  it("auto 模式无等级时显示未评估", () => {
    expect(zoneDisplayLevel(makeZone({ max_risk_level: null }))).toBe("未评估");
  });
});
