import { describe, expect, it } from "vitest";
import { mergeOrgNodes } from "./orgMerge";
import type { OrgNode } from "@/types/enterpriseOrg";

describe("mergeOrgNodes", () => {
  it("adds all incoming nodes when existing is empty", () => {
    const incoming: OrgNode[] = [
      { id: "root", type: "dept", name: "应急组织机构", members: [], parent_id: null },
      { id: "t1", type: "team", name: "疏散引导组", members: [], parent_id: "root" },
      { id: "p1", type: "position", name: "组长", members: [], parent_id: "t1" },
    ];
    const merged = mergeOrgNodes([], incoming);
    expect(merged.map(n => n.name)).toEqual(["应急组织机构", "疏散引导组", "组长"]);
    expect(merged.every(n => n.id && !n.id.startsWith("preset-"))).toBe(true);
  });

  it("keeps existing nodes and only adds missing ones (no duplicates)", () => {
    const existing: OrgNode[] = [
      { id: "root", type: "dept", name: "应急组织机构", members: [], parent_id: null },
      { id: "t1", type: "team", name: "疏散引导组", members: [], parent_id: "root" },
      { id: "company", type: "dept", name: "公司", members: [], parent_id: null },
    ];
    const incoming: OrgNode[] = [
      { id: "preset-org-root", type: "dept", name: "应急组织机构", members: [], parent_id: null },
      { id: "preset-evacuation", type: "team", name: "疏散引导组", members: [], parent_id: "preset-org-root" },
      { id: "preset-evacuation-0", type: "position", name: "组长", members: [], parent_id: "preset-evacuation" },
      { id: "preset-evacuation-1", type: "position", name: "副组长", members: [], parent_id: "preset-evacuation" },
      { id: "preset-medical", type: "team", name: "医疗救护组", members: [], parent_id: "preset-org-root" },
    ];
    const merged = mergeOrgNodes(existing, incoming);
    expect(merged.filter(n => n.name === "应急组织机构")).toHaveLength(1);
    expect(merged.filter(n => n.name === "疏散引导组")).toHaveLength(1);
    expect(merged.filter(n => n.name === "公司")).toHaveLength(1);
    expect(merged.filter(n => n.name === "组长")).toHaveLength(1);
    expect(merged.filter(n => n.name === "医疗救护组")).toHaveLength(1);
    expect(merged.find(n => n.name === "医疗救护组")?.parent_id).toBe(
      merged.find(n => n.name === "应急组织机构")?.id,
    );
  });

  it("reuses a same-named team anywhere instead of duplicating it", () => {
    const existing: OrgNode[] = [
      { id: "company", type: "dept", name: "公司", members: [], parent_id: null },
      { id: "t1", type: "team", name: "疏散引导组", members: [], parent_id: "company" },
    ];
    const incoming: OrgNode[] = [
      { id: "preset-org-root", type: "dept", name: "应急组织机构", members: [], parent_id: null },
      { id: "preset-evacuation", type: "team", name: "疏散引导组", members: [], parent_id: "preset-org-root" },
      { id: "preset-evacuation-0", type: "position", name: "组长", members: [], parent_id: "preset-evacuation" },
      { id: "preset-evacuation-1", type: "position", name: "副组长", members: [], parent_id: "preset-evacuation" },
    ];
    const merged = mergeOrgNodes(existing, incoming);
    expect(merged.filter(n => n.name === "疏散引导组")).toHaveLength(1);
    expect(merged.find(n => n.name === "疏散引导组")?.parent_id).toBe("company");
    expect(merged.filter(n => n.name === "组长")).toHaveLength(1);
    expect(merged.find(n => n.name === "组长")?.parent_id).toBe("t1");
    expect(merged.filter(n => n.name === "副组长")).toHaveLength(1);
    expect(merged.find(n => n.name === "应急组织机构")?.parent_id).toBeNull();
  });

  it("merges AI suggestion into existing tree with parent mapping", () => {
    const existing: OrgNode[] = [
      { id: "company", type: "dept", name: "公司", members: [], parent_id: null },
    ];
    const suggestion: OrgNode[] = [
      { id: "s1", type: "team", name: "应急指挥部", members: [], parent_id: null },
      { id: "s2", type: "position", name: "总指挥", members: [{ name: "张三" }], parent_id: "s1" },
    ];
    const merged = mergeOrgNodes(existing, suggestion);
    expect(merged.map(n => n.name)).toEqual(expect.arrayContaining(["公司", "应急指挥部", "总指挥"]));
    const hq = merged.find(n => n.name === "应急指挥部")!;
    const chief = merged.find(n => n.name === "总指挥")!;
    expect(chief.parent_id).toBe(hq.id);
    expect(chief.members).toEqual([{ name: "张三" }]);
  });

  it("avoids id collisions when adding new nodes", () => {
    const existing: OrgNode[] = [
      { id: "node-1", type: "dept", name: "公司", members: [], parent_id: null },
    ];
    const incoming: OrgNode[] = [
      { id: "node-1", type: "team", name: "疏散引导组", members: [], parent_id: null },
    ];
    const merged = mergeOrgNodes(existing, incoming);
    const ids = merged.map(n => n.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(merged.find(n => n.name === "疏散引导组")?.id).toBe("node-2");
  });
});
