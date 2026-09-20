import type {
  MeasureMeta,
  MeasureSuggestion,
  WorkTicketMeasureDef,
} from "@/types/workTicket";

/** 「本票不涉及」的固定理由（必选），保证审计时能看懂为什么跳过某条措施。 */
export const REASON_OPTIONS = [
  { value: "no_condition", label: "现场不具备该条件" },
  { value: "not_this_method", label: "本次作业方式不涉及" },
  { value: "covered_by_other", label: "已由其他作业票覆盖" },
  { value: "no_medium", label: "作业点无相关介质" },
];

export interface MeasurePartition {
  /** 主线：需要逐条处理的措施 */
  main: WorkTicketMeasureDef[];
  /** 折叠区：引擎建议"本票不涉及"且尚未表态的措施 */
  folded: WorkTicketMeasureDef[];
  /** 已表态条数（confirmed + not_applicable） */
  statedCount: number;
  total: number;
  /** 引擎建议"涉及"且尚未表态的条数（用于"确认全部建议涉及的"按钮） */
  suggestedApplicableCount: number;
}

/** 按三态与引擎建议把措施分成主线与折叠区，并算出台账式的计数。 */
export function partitionMeasures(
  measures: WorkTicketMeasureDef[],
  suggestions: MeasureSuggestion[],
  meta: Record<string, MeasureMeta>,
): MeasurePartition {
  const suggestionByOrder = new Map(
    suggestions.map((item) => [item.sort_order, item.suggest]),
  );
  const stateOf = (order: number): string => meta[String(order)]?.state ?? "pending";

  const main: WorkTicketMeasureDef[] = [];
  const folded: WorkTicketMeasureDef[] = [];
  let statedCount = 0;
  let suggestedApplicableCount = 0;

  for (const measure of measures) {
    const state = stateOf(measure.sort_order);
    if (state !== "pending") statedCount += 1;
    const suggestion = suggestionByOrder.get(measure.sort_order);
    if (suggestion === "not_applicable" && state === "pending") {
      folded.push(measure);
      continue;
    }
    if (suggestion === "applicable" && state === "pending") suggestedApplicableCount += 1;
    main.push(measure);
  }
  return {
    main,
    folded,
    statedCount,
    total: measures.length,
    suggestedApplicableCount,
  };
}

export function withConfirmed(
  meta: Record<string, MeasureMeta>,
  order: number,
): Record<string, MeasureMeta> {
  return {
    ...meta,
    [String(order)]: {
      ...meta[String(order)],
      state: "confirmed",
      acted_at: new Date().toISOString(),
    },
  };
}

export function withNotApplicable(
  meta: Record<string, MeasureMeta>,
  order: number,
  reasonCode: string,
  reasonText: string,
): Record<string, MeasureMeta> {
  return {
    ...meta,
    [String(order)]: {
      ...meta[String(order)],
      state: "not_applicable",
      reason_code: reasonCode,
      reason_text: reasonText,
      acted_at: new Date().toISOString(),
    },
  };
}

export function withReverted(
  meta: Record<string, MeasureMeta>,
  order: number,
): Record<string, MeasureMeta> {
  const next = { ...meta };
  delete next[String(order)];
  return next;
}
