import { describe, expect, it } from "vitest";
import { describePayload } from "@/utils/ingestPayload";

describe("describePayload", () => {
  it("把字段拼成一行可读文本", () => {
    expect(describePayload({ chemical_name: "氯", q_design_max: "5" })).toBe(
      "chemical_name: 氯 ｜ q_design_max: 5",
    );
  });

  it("跳过空值字段", () => {
    expect(describePayload({ a: "x", b: null, c: "", d: undefined })).toBe("a: x");
  });

  it("空载荷返回占位符", () => {
    expect(describePayload({})).toBe("—");
    expect(describePayload(null)).toBe("—");
  });

  it("嵌套对象序列化后展示", () => {
    expect(describePayload({ item: { x: 1 } })).toBe('item: {"x":1}');
  });

  it("超长文本截断", () => {
    const out = describePayload({ text: "甲".repeat(200) }, 20);
    expect(out.length).toBeLessThanOrEqual(21);
    expect(out.endsWith("…")).toBe(true);
  });
});
