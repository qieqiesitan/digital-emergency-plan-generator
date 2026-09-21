import dayjs from "dayjs";
import type { FieldMeta, MeasureMeta } from "@/types/workTicket";

/** 向导步骤序号（与 WorkTicketNewPage 的 STEPS 顺序一致）。 */
export const STEP = {
  TYPE_LEVEL: 0,
  FIELDS: 1,
  GAS_TEST: 2,
  MEASURES: 3,
  JSA: 4,
  SUBMIT: 5,
} as const;

export interface StepProblem {
  /** 该问题属于哪一步（用于提交失败时自动跳转） */
  step: number;
  message: string;
}

export interface StepState {
  /** 该步还差几项（0 = 完成） */
  missing: number;
  /** 步骤条上显示的短描述 */
  label: string;
}

export interface StepStatusInput {
  requiredFields: { key: string; label: string }[];
  values: Record<string, unknown>;
  valuesMeta: Record<string, FieldMeta>;
  measures: { sort_order: number }[];
  measuresMeta: Record<string, MeasureMeta>;
  requiresGasTest: boolean;
  gasTests: { sampled_at: string }[];
  /** 气体检测有效期（分钟），默认 30 */
  gasTestMaxAgeMinutes?: number;
}

/**
 * 计算每一步的完成状态与全量问题清单。
 *
 * 为什么要有它：向导此前只在提交时用一句提示把 11 条问题甩给用户，用户得一步步退回去找。
 * 现在每步的缺项都算得出来 —— 步骤条上直接显示「待补 N 项」，提交失败也能跳到第一个出问题的步骤。
 * 注意：这里**不拦人**，只做提示与定位（放行策略，见 2026-09-21 与用户的约定）。
 */
export function computeStepStates(input: StepStatusInput): {
  states: StepState[];
  problems: StepProblem[];
} {
  const maxAge = input.gasTestMaxAgeMinutes ?? 30;
  const problems: StepProblem[] = [];
  const states: StepState[] = [
    { missing: 0, label: "" }, // 0 类型与级别：始终有值（默认票种+级别）
    { missing: 0, label: "" },
    { missing: 0, label: "" },
    { missing: 0, label: "" },
    { missing: 0, label: "" }, // 4 JSA：可选，不参与缺项统计
    { missing: 0, label: "" }, // 5 人员与提交：只是摘要页
  ];

  // 第 1 步：必填项缺失 + AI 生成未确认
  for (const field of input.requiredFields) {
    const value = input.values[field.key];
    if (value === undefined || value === null || value === "") {
      problems.push({ step: STEP.FIELDS, message: `必填项「${field.label}」尚未填写` });
      continue;
    }
    const meta = input.valuesMeta[field.key];
    if (meta?.source === "ai" && !meta.confirmed_at) {
      problems.push({
        step: STEP.FIELDS,
        message: `「${field.label}」为 AI 生成内容，尚未经人工确认`,
      });
    }
  }

  // 第 2 步：强制气体检测的票种需要有有效期内的记录
  if (input.requiresGasTest) {
    if (input.gasTests.length === 0) {
      problems.push({
        step: STEP.GAS_TEST,
        message: "动火/受限空间作业必须至少录入一次气体检测记录",
      });
    } else {
      const latest = input.gasTests
        .map((gas) => dayjs(gas.sampled_at))
        .sort((a, b) => b.valueOf() - a.valueOf())[0];
      if (dayjs().diff(latest, "minute") > maxAge) {
        problems.push({
          step: STEP.GAS_TEST,
          message: "气体检测取样时间已超过 30 分钟，请重新检测后再提交",
        });
      }
    }
  }

  // 第 3 步：措施必须全部表态（确认涉及 / 本票不涉及）
  const pending = input.measures.filter((measure) => {
    const state = input.measuresMeta[String(measure.sort_order)]?.state;
    return state !== "confirmed" && state !== "not_applicable";
  });
  if (pending.length > 0) {
    problems.push({
      step: STEP.MEASURES,
      message: `还有 ${pending.length} 条安全措施未表态`,
    });
  }
  for (const [key, meta] of Object.entries(input.measuresMeta)) {
    if (meta.state === "not_applicable" && !meta.reason_text?.trim()) {
      problems.push({
        step: STEP.MEASURES,
        message: `第 ${key} 条措施标记为「本票不涉及」，但未填写理由`,
      });
    }
  }

  for (const problem of problems) {
    states[problem.step].missing += 1;
  }
  for (const state of states) {
    state.label = state.missing > 0 ? `待补 ${state.missing} 项` : "";
  }
  return { states, problems };
}
