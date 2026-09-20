import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { MeasureSuggestion, WorkTicketMeasureDef } from "@/types/workTicket";
import { MeasureChecklist } from "./MeasureChecklist";
import {
  partitionMeasures,
  withConfirmed,
  withNotApplicable,
  withReverted,
} from "./measureMeta";

const measures: WorkTicketMeasureDef[] = [
  { sort_order: 1, measure_text: "措施一", article_anchor: "GB 30871-2022 5" },
  { sort_order: 4, measure_text: "措施四", article_anchor: "GB 30871-2022 5" },
  { sort_order: 8, measure_text: "措施八", article_anchor: "GB 30871-2022 5" },
];

describe("partitionMeasures", () => {
  it("建议不涉及且未表态的措施进入折叠区", () => {
    const suggestions: MeasureSuggestion[] = [
      { sort_order: 4, suggest: "not_applicable", reason: "本票不涉及：作业点在油气罐区防火堤内" },
    ];
    const out = partitionMeasures(measures, suggestions, {});
    expect(out.main.map((m) => m.sort_order)).toEqual([1, 8]);
    expect(out.folded.map((m) => m.sort_order)).toEqual([4]);
    expect(out.statedCount).toBe(0);
    expect(out.total).toBe(3);
  });

  it("已表态的措施不再进折叠区（撤销/确认后回到主线）", () => {
    const suggestions: MeasureSuggestion[] = [
      { sort_order: 4, suggest: "not_applicable", reason: "不涉及" },
    ];
    const meta = withNotApplicable({}, 4, "no_condition", "现场无该条件");
    const out = partitionMeasures(measures, suggestions, meta);
    expect(out.folded).toHaveLength(0);
    expect(out.main.map((m) => m.sort_order)).toEqual([1, 4, 8]);
    expect(out.statedCount).toBe(1);
  });

  it("统计建议涉及且未表态的条数，供批量确认按钮使用", () => {
    const suggestions: MeasureSuggestion[] = [
      { sort_order: 1, suggest: "applicable", reason: null },
      { sort_order: 8, suggest: "applicable", reason: null },
    ];
    const out = partitionMeasures(measures, suggestions, withConfirmed({}, 1));
    expect(out.suggestedApplicableCount).toBe(1);
    expect(out.statedCount).toBe(1);
  });
});

describe("meta 变更纯函数", () => {
  it("确认涉及写入状态与时间", () => {
    const next = withConfirmed({}, 4);
    expect(next["4"].state).toBe("confirmed");
    expect(next["4"].acted_at).toBeTruthy();
  });

  it("标记不涉及必须带理由字段", () => {
    const next = withNotApplicable({}, 4, "no_medium", "作业点无相关介质");
    expect(next["4"].state).toBe("not_applicable");
    expect(next["4"].reason_code).toBe("no_medium");
    expect(next["4"].reason_text).toBe("作业点无相关介质");
  });

  it("撤销回到未表态", () => {
    const next = withReverted(withConfirmed({}, 4), 4);
    expect(next["4"]).toBeUndefined();
  });
});

describe("MeasureChecklist 渲染", () => {
  it("显示表态计数，且不提供无条件全部确认", () => {
    const html = renderToStaticMarkup(
      <MeasureChecklist measures={measures} suggestions={[]} meta={{}} onChange={() => {}} />,
    );
    expect(html).toContain("已表态 0 / 3 条");
    expect(html).not.toContain("全部确认<");
  });

  it("折叠区展示「建议不涉及」与判定理由", () => {
    const html = renderToStaticMarkup(
      <MeasureChecklist
        measures={measures}
        suggestions={[
          { sort_order: 4, suggest: "not_applicable", reason: "本票不涉及：作业点在油气罐区防火堤内" },
        ]}
        meta={{}}
        onChange={() => {}}
      />,
    );
    expect(html).toContain("建议不涉及（1 条）");
    expect(html).toContain("作业点在油气罐区防火堤内");
  });

  it("作业包提示只在传入时出现", () => {
    const without = renderToStaticMarkup(
      <MeasureChecklist measures={measures} suggestions={[]} meta={{}} onChange={() => {}} />,
    );
    const withHint = renderToStaticMarkup(
      <MeasureChecklist
        measures={measures}
        suggestions={[]}
        meta={{}}
        onChange={() => {}}
        packageHint="本包已包含：受限空间票 YXKJ-X-0003（已提交）"
      />,
    );
    expect(without).not.toContain("本包已包含");
    expect(withHint).toContain("本包已包含");
  });
});
