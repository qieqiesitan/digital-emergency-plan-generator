import { describe, expect, it } from "vitest";
import {
  buildUnitPolygon,
  isClosingClick,
  isUnitPolygonComplete,
  parseUnitPolygon,
} from "@/utils/unitPolygon";

const square = [
  { x: 10, y: 10 },
  { x: 40, y: 10 },
  { x: 40, y: 40 },
  { x: 10, y: 40 },
];

describe("parseUnitPolygon", () => {
  it("解析合法落点并把坐标收进 0-100", () => {
    const out = parseUnitPolygon({ version: 1, points: [...square, { x: 120, y: -5 }] });
    expect(out).not.toBeNull();
    expect(out!.points[4]).toEqual({ x: 100, y: 0 });
  });

  it("少于 3 个顶点视为无落点", () => {
    expect(parseUnitPolygon({ points: square.slice(0, 2) })).toBeNull();
  });

  it("非对象/非数值一律返回 null，不抛错", () => {
    expect(parseUnitPolygon(null)).toBeNull();
    expect(parseUnitPolygon("x")).toBeNull();
    expect(parseUnitPolygon({ points: [{ x: 1, y: "2" }, { x: 3, y: 4 }, { x: 5, y: 6 }] })).toBeNull();
  });

  it("退化多边形（面积 0）视为无落点", () => {
    expect(
      parseUnitPolygon({
        points: [
          { x: 0, y: 0 },
          { x: 50, y: 50 },
          { x: 100, y: 100 },
        ],
      }),
    ).toBeNull();
  });
});

describe("buildUnitPolygon / isUnitPolygonComplete", () => {
  it("构造载荷时保留 version=1", () => {
    expect(buildUnitPolygon(square)).toEqual({ version: 1, points: square });
  });

  it("顶点不足时返回 null", () => {
    expect(buildUnitPolygon(square.slice(0, 2))).toBeNull();
    expect(isUnitPolygonComplete(square.slice(0, 2))).toBe(false);
    expect(isUnitPolygonComplete(square)).toBe(true);
  });
});

describe("isClosingClick", () => {
  it("点击首顶点附近视为闭合", () => {
    expect(isClosingClick(square, { x: 11, y: 11 })).toBe(true);
    expect(isClosingClick(square, { x: 60, y: 60 })).toBe(false);
  });

  it("顶点不足 3 个时永不闭合", () => {
    expect(isClosingClick(square.slice(0, 2), { x: 10, y: 10 })).toBe(false);
  });
});
