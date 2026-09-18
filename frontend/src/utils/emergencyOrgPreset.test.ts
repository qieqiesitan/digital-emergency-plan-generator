import { describe, expect, it } from "vitest";
import { buildPresetUnits, mergeEmergencyUnits } from "./emergencyOrgPreset";
import type { EmergencyUnit } from "@/types/emergencyOrg";

describe("buildPresetUnits", () => {
  it("生成顶层 + 6 个应急小组 + 18 个角色", () => {
    const units = buildPresetUnits();
    expect(units).toHaveLength(7);
    expect(units[0].name).toBe("应急组织机构");
    expect(units[0].parent_id).toBeNull();
    expect(units.flatMap(u => u.roles)).toHaveLength(18);
  });

  it("指挥部角色为总指挥/副总指挥/成员，且总指挥与副总指挥为必填", () => {
    const hq = buildPresetUnits().find(u => u.name === "应急指挥部")!;
    expect(hq.roles.map(r => r.name)).toEqual(["总指挥", "副总指挥", "成员"]);
    expect(hq.roles.find(r => r.name === "总指挥")!.is_required).toBe(true);
    expect(hq.roles.find(r => r.name === "副总指挥")!.is_required).toBe(true);
    expect(hq.roles.find(r => r.name === "成员")!.is_required).toBe(false);
  });

  it("其余小组角色为组长/副组长/组员且都不必填", () => {
    const rescue = buildPresetUnits().find(u => u.name === "抢险救灾组")!;
    expect(rescue.roles.map(r => r.name)).toEqual(["组长", "副组长", "组员"]);
    expect(rescue.roles.every(r => r.is_required === false)).toBe(true);
  });
});

describe("mergeEmergencyUnits", () => {
  it("同名同父单元复用已有节点，只补缺失角色，保留已有指派", () => {
    const existing: EmergencyUnit[] = [
      { id: "keep", parent_id: null, name: "应急组织机构", roles: [] },
      {
        id: "keep-hq",
        parent_id: "keep",
        name: "应急指挥部",
        roles: [{ id: "r1", name: "总指挥", is_required: true, member_ids: ["m1"] }],
      },
    ];
    const merged = mergeEmergencyUnits(existing, buildPresetUnits());
    const hq = merged.find(u => u.name === "应急指挥部")!;
    expect(hq.id).toBe("keep-hq");
    expect(hq.roles.find(r => r.name === "总指挥")!.member_ids).toEqual(["m1"]);
    // 补齐了副总指挥与成员
    expect(hq.roles.map(r => r.name)).toEqual(["总指挥", "副总指挥", "成员"]);
    // 补齐了缺失的小组
    expect(merged.some(u => u.name === "抢险救灾组")).toBe(true);
    // 原顶层单元被复用，未新建
    expect(merged.filter(u => u.parent_id === null)).toHaveLength(1);
  });

  it("不修改传入的 existing 对象（纯函数）", () => {
    const existing: EmergencyUnit[] = [
      { id: "keep", parent_id: null, name: "应急组织机构", roles: [] },
    ];
    const snapshot = JSON.parse(JSON.stringify(existing));
    mergeEmergencyUnits(existing, buildPresetUnits());
    expect(existing).toEqual(snapshot);
  });
});
