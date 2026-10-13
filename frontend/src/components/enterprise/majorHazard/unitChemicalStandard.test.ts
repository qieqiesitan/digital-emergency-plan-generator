import { describe, expect, it } from "vitest";
import { decideCriticalQuantity } from "./unitChemicalStandard";

describe("decideCriticalQuantity（查标准表后 Q 怎么写）", () => {
  it("标准表有值就采用", () => {
    expect(
      decideCriticalQuantity({
        returnedQ: 10,
        hazardSymbol: "W5.1",
        typedName: "汽油",
        previousResolvedName: "汽油",
      }),
    ).toBe("10");
  });

  it("首次查表1 没有的名字：不动（保护手填的 Q）", () => {
    expect(
      decideCriticalQuantity({ returnedQ: null, typedName: "某种混合物" }),
    ).toBeUndefined();
  });

  it("换了另一个品种、新名字不在表1：清空旧 Q", () => {
    expect(
      decideCriticalQuantity({
        returnedQ: null,
        typedName: "汽油",
        previousResolvedName: "氯",
      }),
    ).toBe("");
  });

  it("选类别时表2 没这个符号：不动（不能把表1 已取到的 Q 抹掉）", () => {
    expect(
      decideCriticalQuantity({
        returnedQ: null,
        hazardSymbol: "J3",
        typedName: "甲醇",
        previousResolvedName: "甲醇",
      }),
    ).toBeUndefined();
  });

  it("同名重查不清空（避免失焦重复查询把值打空）", () => {
    expect(
      decideCriticalQuantity({
        returnedQ: null,
        typedName: "汽油",
        previousResolvedName: "汽油",
      }),
    ).toBeUndefined();
  });

  it("品种名两边的空格不影响判定", () => {
    expect(
      decideCriticalQuantity({
        returnedQ: null,
        typedName: " 汽油 ",
        previousResolvedName: "汽油",
      }),
    ).toBeUndefined();
  });
});
