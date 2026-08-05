import type { RiskPolygonPoint } from "@/types/riskMappingWorkbench";

export const toPercent = (value: number, max: number) => Math.min(100, Math.max(0, (value / max) * 100));
export const toCanvasX = (value: number, width = 1200) => (value / 100) * width;
export const toCanvasY = (value: number, height = 900) => (value / 100) * height;

export const clampPoint = (p: RiskPolygonPoint): RiskPolygonPoint => ({
  x: Math.min(100, Math.max(0, p.x)),
  y: Math.min(100, Math.max(0, p.y)),
});

export const pointsToKonva = (points: RiskPolygonPoint[], width = 1200, height = 900) =>
  points.flatMap(p => [toCanvasX(p.x, width), toCanvasY(p.y, height)]);

export const polygonArea = (points: RiskPolygonPoint[]) => {
  let area = 0;
  for (let i = 0; i < points.length; i++) {
    const a = points[i];
    const b = points[(i + 1) % points.length];
    area += a.x * b.y - b.x * a.y;
  }
  return Math.abs(area) / 2;
};

export const validatePolygon = (points: RiskPolygonPoint[]) => {
  if (points.length < 3) return "至少需要 3 个顶点";
  if (polygonArea(points) <= 0.001) return "多边形面积必须大于 0";
  return null;
};

export const simplifyPolygon = (points: RiskPolygonPoint[], tolerance = 0.15) => {
  if (points.length <= 3) return points;
  return points.filter((_, i) => i % 2 === 0 || i === points.length - 1);
};
