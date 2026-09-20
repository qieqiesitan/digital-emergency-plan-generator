import { describe, expect, it } from "vitest";
import {
  buildChecklistItems,
  buildOrgNodes,
  buildPlanPayloads,
  WIZARD_WEEKDAY_FALLBACK,
} from "./hazardSetupWizard";

const ZONES = [
  { id: "z1", name: "储罐区" },
  { id: "z2", name: "装卸区" },
];
const MEMBERS = [
  { user_id: "u1", name: "张伟", email: "zhang@example.com", enabled: true },
  { user_id: "u2", name: "李娜", email: "li@example.com", enabled: false },
];

describe("buildPlanPayloads", () => {
  it("把分区名映射成 id，并记录没匹配上的名字", () => {
    const out = buildPlanPayloads(
      [{ name: "罐区周查", category: "comprehensive", frequency: "weekly", weekdays: [1, 5], zone_names: ["储罐区", "不存在的区"] }],
      ZONES,
      MEMBERS,
    );
    expect(out).toHaveLength(1);
    expect(out[0].payload.zone_ids).toEqual(["z1"]);
    expect(out[0].unmatchedZones).toEqual(["不存在的区"]);
  });

  it("责任人按姓名匹配启用成员，匹配不到时不写 responsible_user_id", () => {
    const [hit, miss] = buildPlanPayloads(
      [
        { name: "A", category: "daily", frequency: "daily", responsible_user_name: "张伟" },
        { name: "B", category: "daily", frequency: "daily", responsible_user_name: "查无此人" },
      ],
      ZONES,
      MEMBERS,
    );
    expect(hit.payload.responsible_user_id).toBe("u1");
    expect(hit.responsibleMatched).toBe(true);
    expect(miss.payload.responsible_user_id).toBeUndefined();
    expect(miss.responsibleMatched).toBe(false);
  });

  it("weekly/custom 缺 weekdays 时补默认工作日；其它频次丢弃 weekdays", () => {
    const [weekly, monthly] = buildPlanPayloads(
      [
        { name: "W", category: "daily", frequency: "weekly" },
        { name: "M", category: "daily", frequency: "monthly", weekdays: [3] },
      ],
      ZONES,
      MEMBERS,
    );
    expect(weekly.payload.weekdays).toEqual(WIZARD_WEEKDAY_FALLBACK);
    expect(monthly.payload.weekdays).toBeUndefined();
  });

  it("空输入返回空数组且不抛错", () => {
    expect(buildPlanPayloads([], ZONES, MEMBERS)).toEqual([]);
  });
});

describe("buildOrgNodes", () => {
  it("把后端 nodes 建议转成 OrgNode（members 为空数组）", () => {
    const out = buildOrgNodes({
      nodes: [
        { id: "n1", type: "dept", name: "安全管理部", parent_id: null },
        { id: "n2", type: "team", name: "罐区班组", parent_id: "n1" },
      ],
    });
    expect(out).toEqual([
      { id: "n1", type: "dept", name: "安全管理部", parent_id: null, members: [] },
      { id: "n2", type: "team", name: "罐区班组", parent_id: "n1", members: [] },
    ]);
  });

  it("丢弃未知 type、重复 id，并把悬空 parent_id 归零", () => {
    const out = buildOrgNodes({
      nodes: [
        { id: "n1", type: "dept", name: "安全管理部" },
        { id: "n1", type: "dept", name: "重复 id" },
        { id: "n2", type: "unknown", name: "未知类型" },
        { id: "n3", type: "position", name: "安全总监", parent_id: "不存在" },
      ],
    });
    expect(out.map(n => n.id)).toEqual(["n1", "n3"]);
    expect(out[1].parent_id).toBeNull();
  });

  it("缺失/异常输入返回空数组", () => {
    expect(buildOrgNodes(undefined)).toEqual([]);
    expect(buildOrgNodes({ nodes: "oops" })).toEqual([]);
  });
});

describe("buildChecklistItems", () => {
  it("保留 content 与 expected_note，去掉空条目", () => {
    expect(buildChecklistItems([
      { content: " 检查液位计 ", expected_note: "现场查看" },
      { content: "   " },
      { content: "检查围堰" },
    ])).toEqual([
      { content: "检查液位计", expected_note: "现场查看" },
      { content: "检查围堰", expected_note: undefined },
    ]);
  });

  it("非数组输入返回空数组", () => {
    expect(buildChecklistItems(null)).toEqual([]);
  });
});
