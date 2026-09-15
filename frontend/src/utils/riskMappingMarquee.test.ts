import { describe, it, expect } from "vitest";
import {
  rectFromPoints,
  polygonIntersectsRect,
  collectRegionsInRect,
  transformRegionsAroundCenter,
} from "./riskMappingMarquee";

const square = (x: number, y: number, size = 10) => [
  { x, y },
  { x: x + size, y },
  { x: x + size, y: y + size },
  { x, y: y + size },
];

describe("rectFromPoints", () => {
  it("两点归一化为正宽高矩形", () => {
    expect(rectFromPoints({ x: 30, y: 40 }, { x: 10, y: 20 })).toEqual({ x: 10, y: 20, width: 20, height: 20 });
  });

  it("拖动距离小于阈值时返回 null", () => {
    expect(rectFromPoints({ x: 10, y: 10 }, { x: 10.1, y: 10.1 }, 0.5)).toBeNull();
  });
});

describe("polygonIntersectsRect", () => {
  const rect = { x: 0, y: 0, width: 20, height: 20 };

  it("完全包含的多边形命中", () => {
    expect(polygonIntersectsRect(square(2, 2, 5), rect)).toBe(true);
  });

  it("部分相交的多边形命中", () => {
    expect(polygonIntersectsRect(square(15, 15, 10), rect)).toBe(true);
  });

  it("完全分离的多边形不命中", () => {
    expect(polygonIntersectsRect(square(50, 50, 5), rect)).toBe(false);
  });

  it("仅边界接触也算命中", () => {
    expect(polygonIntersectsRect(square(20, 5, 5), rect)).toBe(true);
  });

  it("空点集不命中", () => {
    expect(polygonIntersectsRect([], rect)).toBe(false);
  });
});

describe("collectRegionsInRect", () => {
  it("返回命中的区域 id 列表", () => {
    const polygons = [
      { id: "a", points: square(1, 1, 5) },
      { id: "b", points: square(80, 80, 5) },
    ];
    expect(collectRegionsInRect(polygons, { x: 0, y: 0, width: 20, height: 20 })).toEqual(["a"]);
  });
});

describe("transformRegionsAroundCenter", () => {
  const polygons = [{ id: "a", points: square(0, 0, 10) }];

  it("绕配置中心旋转 90 度后中心不变、形状保持", () => {
    const [next] = transformRegionsAroundCenter(polygons, { rotationDeg: 90 }, { x: 5, y: 5 });
    const xs = next.points.map(p => p.x);
    const ys = next.points.map(p => p.y);
    expect((Math.min(...xs) + Math.max(...xs)) / 2).toBeCloseTo(5, 5);
    expect((Math.min(...ys) + Math.max(...ys)) / 2).toBeCloseTo(5, 5);
    expect(Math.max(...xs) - Math.min(...xs)).toBeCloseTo(10, 5);
  });

  it("缩放后顶点仍收敛在 0-100", () => {
    const [next] = transformRegionsAroundCenter(
      [{ id: "a", points: square(90, 90, 10) }],
      { scale: 3 },
      { x: 95, y: 95 },
    );
    for (const p of next.points) {
      expect(p.x).toBeGreaterThanOrEqual(0);
      expect(p.x).toBeLessThanOrEqual(100);
      expect(p.y).toBeGreaterThanOrEqual(0);
      expect(p.y).toBeLessThanOrEqual(100);
    }
  });
});
