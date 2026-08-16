import { describe, expect, it } from "vitest";
import type { RightColumn, SignItem } from "@/types/riskNoticeCard";
import {
  MAX_SIGNS_PER_CATEGORY,
  MAX_TOTAL_SIGNS,
  applySignSuggestion,
  buildNameLookup,
  buildSignLookup,
  categoryOf,
  countSignsByCategory,
  mergeOptimizedContent,
  signSrc,
  sortSignsByCategory,
} from "./riskNoticeCardSigns";

const fireWarning: SignItem = { category: "warning", name: "当心火灾", svg_name: "warning-fire" };
const noSmoking: SignItem = { category: "prohibition", name: "禁止烟火", svg_name: "prohibition-smoking" };
const helmet: SignItem = { category: "instruction", name: "必须戴安全帽", svg_name: "instruction-helmet" };
const exit: SignItem = { category: "notice", name: "紧急出口", svg_name: "notice-exit" };

describe("categoryOf", () => {
  it("按 svg_name 前缀推断四类类别", () => {
    expect(categoryOf("warning-fire")).toBe("warning");
    expect(categoryOf("prohibition-smoking")).toBe("prohibition");
    expect(categoryOf("instruction-helmet")).toBe("instruction");
    expect(categoryOf("notice-exit")).toBe("notice");
  });

  it("未知前缀兜底为 notice", () => {
    expect(categoryOf("custom-sign")).toBe("notice");
  });
});

describe("signSrc", () => {
  it("拼接 /signs/{svg_name}.svg（不重复扩展名）", () => {
    expect(signSrc("warning-fire")).toBe("/signs/warning-fire.svg");
  });
});

describe("sortSignsByCategory", () => {
  it("按 警告→禁止→指令→提示 排序，类内保持原顺序", () => {
    const result = sortSignsByCategory([helmet, exit, fireWarning, noSmoking]);
    expect(result.map((s) => s.svg_name)).toEqual([
      "warning-fire",
      "prohibition-smoking",
      "instruction-helmet",
      "notice-exit",
    ]);
  });

  it("不修改原数组", () => {
    const input = [exit, fireWarning];
    sortSignsByCategory(input);
    expect(input.map((s) => s.svg_name)).toEqual(["notice-exit", "warning-fire"]);
  });
});

describe("buildSignLookup / buildNameLookup", () => {
  it("按 svg_name 建立查找表", () => {
    const lookup = buildSignLookup([fireWarning, exit]);
    expect(lookup.get("warning-fire")).toEqual(fireWarning);
    expect(lookup.get("notice-exit")?.name).toBe("紧急出口");
    expect(buildNameLookup([fireWarning]).get("warning-fire")).toBe("当心火灾");
  });
});

describe("countSignsByCategory", () => {
  it("按类别统计数量", () => {
    const counts = countSignsByCategory([fireWarning, noSmoking, exit, exit]);
    expect(counts.get("warning")).toBe(1);
    expect(counts.get("prohibition")).toBe(1);
    expect(counts.get("notice")).toBe(2);
    expect(counts.get("instruction")).toBeUndefined();
  });
});

describe("applySignSuggestion", () => {
  it("remove 去掉、add 加入并去重，结果按类别排序", () => {
    const result = applySignSuggestion(
      [fireWarning, noSmoking, exit],
      {
        remove: ["prohibition-smoking", "warning-fire"],
        add: ["warning-fall", "notice-exit", "instruction-helmet"],
        reasons: [],
      },
      [
        fireWarning,
        noSmoking,
        helmet,
        exit,
        { category: "warning", name: "当心滑倒", svg_name: "warning-fall" },
      ],
    );
    expect(result.map((s) => s.svg_name)).toEqual([
      "warning-fall",
      "instruction-helmet",
      "notice-exit",
    ]);
    // add 行中文名/类别来自候选库，而非 svg_name 兜底
    expect(result[0]).toEqual({ category: "warning", name: "当心滑倒", svg_name: "warning-fall" });
  });

  it("无候选库时 add 按 svg_name 前缀推断类别、中文名兜底为 svg_name", () => {
    const result = applySignSuggestion([], {
      remove: [],
      add: ["warning-fall"],
      reasons: [],
    });
    expect(result).toEqual([{ category: "warning", name: "warning-fall", svg_name: "warning-fall" }]);
  });

  it("add 与当前标志重复时不重复添加", () => {
    const result = applySignSuggestion([fireWarning], {
      remove: [],
      add: ["warning-fire"],
      reasons: [],
    });
    expect(result).toEqual([fireWarning]);
  });

  it("remove 与 add 含同一 svg_name 时按先删后加处理，候选库恢复中文名", () => {
    const result = applySignSuggestion(
      [fireWarning],
      {
        remove: ["warning-fire"],
        add: ["warning-fire"],
        reasons: [],
      },
      [fireWarning],
    );
    expect(result).toEqual([fireWarning]);
  });
});

describe("mergeOptimizedContent", () => {
  it("右栏四块原值保留 + 自定义 signs + 来源透传（覆盖 optimized 自带缺省 signs）", () => {
    const optimized: RightColumn & {
      signs: SignItem[];
      signs_source: "rule" | "ai" | "manual" | null;
    } = {
      hazard_description: "优化后描述",
      accident_types: ["火灾"],
      control_measures: ["优化后控制措施"],
      emergency_measures: ["优化后应急措施"],
      // 后端 RightColumn.model_dump() 缺省会带空标志：采用时必须被自定义 signs 覆盖
      signs: [],
      signs_source: null,
    };
    const result = mergeOptimizedContent(optimized, [fireWarning, noSmoking], "ai");
    expect(result).toEqual({
      hazard_description: "优化后描述",
      accident_types: ["火灾"],
      control_measures: ["优化后控制措施"],
      emergency_measures: ["优化后应急措施"],
      signs: [fireWarning, noSmoking],
      signs_source: "ai",
    });
  });

  it("signs_source 缺失时回落 rule", () => {
    const optimized: RightColumn = {
      hazard_description: "x",
      accident_types: [],
      control_measures: [],
      emergency_measures: [],
    };
    const result = mergeOptimizedContent(optimized, [], undefined);
    expect(result.signs).toEqual([]);
    expect(result.signs_source).toBe("rule");
  });
});

describe("限量常量", () => {
  it("每类 ≤2、总数 ≤8，与后端 normalize_signs 默认一致", () => {
    expect(MAX_SIGNS_PER_CATEGORY).toBe(2);
    expect(MAX_TOTAL_SIGNS).toBe(8);
  });
});
