import { describe, expect, it } from "vitest";
import {
  computeConclusionText,
  formatQty,
  levelColor,
  toNumber,
  UNIT_TYPE_LABEL,
} from "./majorHazardFormat";

describe("majorHazardFormat", () => {
  it("toNumber 兼容后端 Decimal 字符串", () => {
    expect(toNumber("1.500000")).toBe(1.5);
    expect(toNumber(2)).toBe(2);
    expect(toNumber(null)).toBeNull();
    expect(toNumber("")).toBeNull();
    expect(toNumber("abc")).toBeNull();
  });

  it("formatQty 去掉无意义尾零", () => {
    expect(formatQty("5.000000")).toBe("5");
    expect(formatQty("0.300000")).toBe("0.3");
    expect(formatQty("0.750000")).toBe("0.75");
    expect(formatQty(null)).toBe("—");
  });

  it("levelColor 按等级给色", () => {
    expect(levelColor("一级")).toBe("red");
    expect(levelColor("二级")).toBe("orange");
    expect(levelColor("三级")).toBe("gold");
    expect(levelColor("四级")).toBe("blue");
    expect(levelColor(null)).toBe("default");
    expect(levelColor(undefined)).toBe("default");
  });

  it("computeConclusionText 区分未计算与不构成", () => {
    expect(computeConclusionText(null)).toBe("未计算");
    expect(computeConclusionText(undefined)).toBe("未计算");
    expect(computeConclusionText({ is_major_hazard: false, level: null })).toBe("不构成");
    expect(computeConclusionText({ is_major_hazard: true, level: "二级" })).toBe("二级");
    // 构成但级别缺失时不显示空白
    expect(computeConclusionText({ is_major_hazard: true, level: null })).toBe("构成");
  });

  it("单元类型有中文名", () => {
    expect(UNIT_TYPE_LABEL.production).toBe("生产单元");
    expect(UNIT_TYPE_LABEL.storage).toBe("储存单元");
  });
});
