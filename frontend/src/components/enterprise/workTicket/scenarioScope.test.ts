import { describe, expect, it } from "vitest";
import { pruneScenario, scenarioFieldsFor } from "./scenarioScope";

describe("scenarioFieldsFor", () => {
  it("动火票返回 7 项（来自模板响应，不写死在组件里）", () => {
    const fields = scenarioFieldsFor({
      scenario_fields: Array.from({ length: 7 }, (_, i) => ({
        key: `k${i}`,
        label: `项${i}`,
      })),
    });
    expect(fields).toHaveLength(7);
  });

  it("断路票没有人工勾选项（唯一条件是自动判定的夜间）", () => {
    expect(scenarioFieldsFor({ scenario_fields: [] })).toEqual([]);
  });

  it("模板缺失时返回空数组", () => {
    expect(scenarioFieldsFor(undefined)).toEqual([]);
  });
});

describe("pruneScenario", () => {
  it("切票种时丢弃不属于新票种的勾选（避免把动火情景带到受限空间票）", () => {
    const kept = pruneScenario(
      { hazardous_residue: true, internal_work: true },
      [{ key: "hazardous_residue", label: "受限空间盛装过有毒/可燃物料" }],
    );
    expect(kept).toEqual({ hazardous_residue: true });
  });

  it("新票种没有情景项时清空全部勾选", () => {
    expect(pruneScenario({ internal_work: true }, [])).toEqual({});
  });
});
