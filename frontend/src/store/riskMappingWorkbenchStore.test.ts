import { describe, it, expect } from "vitest";
import { useRiskMappingWorkbenchStore } from "./riskMappingWorkbenchStore";
import {
  toPercent,
  toCanvasX,
  toCanvasY,
  pointsToKonva,
  polygonArea,
  validatePolygon,
  simplifyPolygon,
} from "@/utils/riskMappingGeometry";

describe("riskMappingWorkbenchStore", () => {
  it("commit marks dirty and pushes history", () => {
    useRiskMappingWorkbenchStore.setState({ past: [], future: [], dirty: false });
    useRiskMappingWorkbenchStore.getState().commit();
    expect(useRiskMappingWorkbenchStore.getState().dirty).toBe(true);
    expect(useRiskMappingWorkbenchStore.getState().past.length).toBe(1);
  });
});

describe("riskMappingGeometry", () => {
  it("converts between percent and canvas coordinates", () => {
    expect(toPercent(600, 1200)).toBe(50);
    expect(toPercent(1500, 1200)).toBe(100);
    expect(toCanvasX(50)).toBe(600);
    expect(toCanvasY(50)).toBe(450);
    expect(toCanvasX(50, 900)).toBe(450);
    expect(toCanvasY(50, 600)).toBe(300);
  });

  it("builds flat konva points and computes polygon area", () => {
    const points = [
      { x: 0, y: 0 },
      { x: 10, y: 0 },
      { x: 10, y: 10 },
      { x: 0, y: 10 },
    ];
    expect(pointsToKonva(points, 1000, 1000)).toEqual([0, 0, 100, 0, 100, 100, 0, 100]);
    expect(polygonArea(points)).toBe(100);
  });

  it("validates polygon requirements", () => {
    expect(validatePolygon([])).toBe("至少需要 3 个顶点");
    expect(validatePolygon([{ x: 0, y: 0 }, { x: 1, y: 1 }])).toBe("至少需要 3 个顶点");
    expect(validatePolygon([{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 0.5, y: 0 }])).toBe("多边形面积必须大于 0");
    expect(validatePolygon([{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 0, y: 1 }])).toBeNull();
  });

  it("simplifies polygons with more than 3 vertices", () => {
    const points = [
      { x: 0, y: 0 },
      { x: 1, y: 0 },
      { x: 2, y: 0 },
      { x: 3, y: 1 },
    ];
    expect(simplifyPolygon(points)).toHaveLength(3);
    expect(simplifyPolygon(points.slice(0, 3))).toHaveLength(3);
  });
});
