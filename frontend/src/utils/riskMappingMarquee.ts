import type { RiskPolygonPoint } from "@/types/riskManagement";
import { clampPoint, transformPolygonPoints } from "@/utils/riskMappingGeometry";

export interface MarqueeRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export const MARQUEE_MIN_SIZE = 0.5; // 百分比单位（约 6px @1200 宽）

/** 由拖拽起止点构造归一化矩形；拖动距离小于阈值时返回 null（视为单击）。 */
export function rectFromPoints(
  a: RiskPolygonPoint,
  b: RiskPolygonPoint,
  minSize = MARQUEE_MIN_SIZE,
): MarqueeRect | null {
  const rect: MarqueeRect = {
    x: Math.min(a.x, b.x),
    y: Math.min(a.y, b.y),
    width: Math.abs(a.x - b.x),
    height: Math.abs(a.y - b.y),
  };
  if (rect.width < minSize || rect.height < minSize) return null;
  return rect;
}

const pointInRect = (p: RiskPolygonPoint, r: MarqueeRect) =>
  p.x >= r.x && p.x <= r.x + r.width && p.y >= r.y && p.y <= r.y + r.height;

const pointInPolygon = (p: RiskPolygonPoint, points: RiskPolygonPoint[]) => {
  let inside = false;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const xi = points[i].x;
    const yi = points[i].y;
    const xj = points[j].x;
    const yj = points[j].y;
    const intersects = yi > p.y !== yj > p.y && p.x < ((xj - xi) * (p.y - yi)) / (yj - yi) + xi;
    if (intersects) inside = !inside;
  }
  return inside;
};

const orientation = (a: RiskPolygonPoint, b: RiskPolygonPoint, c: RiskPolygonPoint) =>
  (b.y - a.y) * (c.x - b.x) - (b.x - a.x) * (c.y - b.y);

const onSegment = (a: RiskPolygonPoint, b: RiskPolygonPoint, c: RiskPolygonPoint) =>
  Math.min(a.x, b.x) <= c.x &&
  c.x <= Math.max(a.x, b.x) &&
  Math.min(a.y, b.y) <= c.y &&
  c.y <= Math.max(a.y, b.y);

const segmentsIntersect = (
  p1: RiskPolygonPoint,
  q1: RiskPolygonPoint,
  p2: RiskPolygonPoint,
  q2: RiskPolygonPoint,
) => {
  const o1 = orientation(p1, q1, p2);
  const o2 = orientation(p1, q1, q2);
  const o3 = orientation(p2, q2, p1);
  const o4 = orientation(p2, q2, q1);
  if (o1 * o2 < 0 && o3 * o4 < 0) return true;
  if (o1 === 0 && onSegment(p1, q1, p2)) return true;
  if (o2 === 0 && onSegment(p1, q1, q2)) return true;
  if (o3 === 0 && onSegment(p2, q2, p1)) return true;
  if (o4 === 0 && onSegment(p2, q2, q1)) return true;
  return false;
};

/** 多边形与选框相交（完全包含 / 部分相交 / 边界接触均视为命中）。 */
export function polygonIntersectsRect(points: RiskPolygonPoint[], rect: MarqueeRect): boolean {
  if (points.length < 3) return false;
  if (points.some(p => pointInRect(p, rect))) return true;
  const corners: RiskPolygonPoint[] = [
    { x: rect.x, y: rect.y },
    { x: rect.x + rect.width, y: rect.y },
    { x: rect.x + rect.width, y: rect.y + rect.height },
    { x: rect.x, y: rect.y + rect.height },
  ];
  if (corners.some(c => pointInPolygon(c, points))) return true;
  for (let i = 0; i < points.length; i++) {
    const a = points[i];
    const b = points[(i + 1) % points.length];
    for (let j = 0; j < 4; j++) {
      if (segmentsIntersect(a, b, corners[j], corners[(j + 1) % 4])) return true;
    }
  }
  return false;
}

/** 收集落在选框内的多边形 id。 */
export function collectRegionsInRect<T extends { id: string; points: RiskPolygonPoint[] }>(
  polygons: T[],
  rect: MarqueeRect,
): string[] {
  return polygons.filter(p => polygonIntersectsRect(p.points, rect)).map(p => p.id);
}

/** 绕指定中心（缺省为各自中心）批量变换多边形，顶点统一收敛到 0-100。 */
export function transformRegionsAroundCenter<T extends { id: string; points: RiskPolygonPoint[] }>(
  polygons: T[],
  options: { scale?: number; rotationDeg?: number; flipX?: boolean; flipY?: boolean },
  center?: RiskPolygonPoint,
): { id: string; points: RiskPolygonPoint[] }[] {
  return polygons.map(p => ({
    id: p.id,
    points: transformPolygonPoints(p.points, { ...options, center }).map(clampPoint),
  }));
}
