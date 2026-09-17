import { describe, expect, it } from "vitest";
import { describePayload, extractTableHeaders } from "@/utils/ingestPayload";

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

describe("extractTableHeaders", () => {
  it("取第一条数据行按「|」拆成表头", () => {
    expect(extractTableHeaders("品名 | 设计最大量 | 备注\n甲醇 | 79 | 无")).toEqual([
      "品名",
      "设计最大量",
      "备注",
    ]);
  });

  it("跳过 xlsx 的工作表标记行与空行", () => {
    expect(extractTableHeaders("【工作表：Sheet1】\n\n品名 | 数量")).toEqual(["品名", "数量"]);
  });

  it("没有可用行时返回空数组", () => {
    expect(extractTableHeaders("")).toEqual([]);
    expect(extractTableHeaders("【工作表：Sheet1】")).toEqual([]);
  });
});
