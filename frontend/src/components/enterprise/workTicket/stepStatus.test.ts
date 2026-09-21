import { describe, expect, it } from "vitest";
import type { FieldMeta, MeasureMeta } from "@/types/workTicket";
import { computeStepStates } from "./stepStatus";

const FIELDS = [
  { key: "applicant_unit", label: "作业申请单位" },
  { key: "work_content", label: "作业内容" },
];

const base = {
  requiredFields: FIELDS,
  values: { applicant_unit: "某某化工", work_content: "更换阀门" },
  valuesMeta: {} as Record<string, FieldMeta>,
  measures: [{ sort_order: 1 }, { sort_order: 2 }],
  measuresMeta: {} as Record<string, MeasureMeta>,
  requiresGasTest: true,
  gasTests: [{ sampled_at: new Date().toISOString() }],
};

describe("computeStepStates", () => {
  it("全部完成时每一步都没有待补项", () => {
    const { states, problems } = computeStepStates({
      ...base,
      measuresMeta: {
        "1": { state: "confirmed" },
        "2": { state: "not_applicable", reason_text: "本票不涉及" },
      },
    });
    expect(states[1].missing).toBe(0);
    expect(states[3].missing).toBe(0);
    expect(problems).toEqual([]);
  });

  it("票面必填项缺失归到第 1 步，并给出可读的缺项清单", () => {
    const { states, problems } = computeStepStates({
      ...base,
      values: { applicant_unit: "某某化工" },
      measuresMeta: { "1": { state: "confirmed" }, "2": { state: "confirmed" } },
    });
    expect(states[1].missing).toBe(1);
    expect(states[1].label).toContain("待补 1 项");
    expect(problems[0].step).toBe(1);
    expect(problems[0].message).toContain("作业内容");
  });

  it("AI 生成但未确认的字段也算票面未完成", () => {
    const { states } = computeStepStates({
      ...base,
      valuesMeta: { work_content: { source: "ai" } },
      measuresMeta: { "1": { state: "confirmed" }, "2": { state: "confirmed" } },
    });
    expect(states[1].missing).toBe(1);
  });

  it("需要气体检测却没有记录时归到第 2 步", () => {
    const { states, problems } = computeStepStates({
      ...base,
      gasTests: [],
      measuresMeta: { "1": { state: "confirmed" }, "2": { state: "confirmed" } },
    });
    expect(states[2].missing).toBe(1);
    expect(problems.some((p) => p.step === 2)).toBe(true);
  });

  it("不需要气体检测的票种第 2 步始终完成", () => {
    const { states } = computeStepStates({
      ...base,
      requiresGasTest: false,
      gasTests: [],
      measuresMeta: { "1": { state: "confirmed" }, "2": { state: "confirmed" } },
    });
    expect(states[2].missing).toBe(0);
  });

  it("未表态的措施归到第 3 步", () => {
    const { states, problems } = computeStepStates({
      ...base,
      measuresMeta: { "1": { state: "confirmed" } },
    });
    expect(states[3].missing).toBe(1);
    expect(problems.find((p) => p.step === 3)?.message).toContain("未表态");
  });

  it("问题清单按步骤顺序排列，便于跳到第一个出问题的步骤", () => {
    const { problems } = computeStepStates({
      ...base,
      values: {},
      gasTests: [],
      measuresMeta: {},
    });
    const steps = problems.map((p) => p.step);
    expect(steps).toEqual([...steps].sort((a, b) => a - b));
    expect(steps[0]).toBe(1);
  });

  it("类型与级别、JSA 两步不参与缺项统计（JSA 本就可选）", () => {
    const { states } = computeStepStates({
      ...base,
      measuresMeta: { "1": { state: "confirmed" }, "2": { state: "confirmed" } },
    });
    expect(states[0].missing).toBe(0);
    expect(states[4].missing).toBe(0);
  });
});
