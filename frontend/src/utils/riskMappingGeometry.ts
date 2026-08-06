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

export const ellipsePoints = (
  center: RiskPolygonPoint,
  radiusX: number,
  radiusY: number,
  segments = 48,
): RiskPolygonPoint[] =>
  Array.from({ length: segments }, (_, i) => {
    const angle = (Math.PI * 2 * i) / segments;
    return clampPoint({
      x: center.x + Math.cos(angle) * radiusX,
      y: center.y + Math.sin(angle) * radiusY,
    });
  });

export const circlePoints = (center: RiskPolygonPoint, radius: number, segments = 48): RiskPolygonPoint[] =>
  ellipsePoints(center, radius, radius, segments);

export const polygonCentroid = (points: RiskPolygonPoint[]): RiskPolygonPoint => {
  if (!points.length) return { x: 50, y: 50 };
  const sum = points.reduce(
    (acc, p) => ({ x: acc.x + p.x, y: acc.y + p.y }),
    { x: 0, y: 0 },
  );
  return { x: sum.x / points.length, y: sum.y / points.length };
};

export const transformPolygonPoints = (
  points: RiskPolygonPoint[],
  options: { scale?: number; rotationDeg?: number; flipX?: boolean; flipY?: boolean; center?: RiskPolygonPoint },
): RiskPolygonPoint[] => {
  if (!points.length) return points;
  const center = options.center ?? polygonCentroid(points);
  const scale = options.scale ?? 1;
  const radians = ((options.rotationDeg ?? 0) * Math.PI) / 180;
  const cos = Math.cos(radians);
  const sin = Math.sin(radians);
  return points.map(p => {
    let dx = p.x - center.x;
    let dy = p.y - center.y;
    if (options.flipX) dx = -dx;
    if (options.flipY) dy = -dy;
    dx *= scale;
    dy *= scale;
    return clampPoint({
      x: center.x + dx * cos - dy * sin,
      y: center.y + dx * sin + dy * cos,
    });
  });
};

export const quadraticCurvePoints = (
  start: RiskPolygonPoint,
  control: RiskPolygonPoint,
  end: RiskPolygonPoint,
  segments = 16,
): RiskPolygonPoint[] =>
  Array.from({ length: segments + 1 }, (_, i) => {
    const t = i / segments;
    const inv = 1 - t;
    return clampPoint({
      x: inv * inv * start.x + 2 * inv * t * control.x + t * t * end.x,
      y: inv * inv * start.y + 2 * inv * t * control.y + t * t * end.y,
    });
  });

export const cubicBezierPoints = (
  start: RiskPolygonPoint,
  control1: RiskPolygonPoint,
  control2: RiskPolygonPoint,
  end: RiskPolygonPoint,
  segments = 20,
): RiskPolygonPoint[] =>
  Array.from({ length: segments + 1 }, (_, i) => {
    const t = i / segments;
    const inv = 1 - t;
    const a = inv * inv * inv;
    const b = 3 * inv * inv * t;
    const c = 3 * inv * t * t;
    const d = t * t * t;
    return clampPoint({
      x: a * start.x + b * control1.x + c * control2.x + d * end.x,
      y: a * start.y + b * control1.y + c * control2.y + d * end.y,
    });
  });

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
  if (points.some(p => !Number.isFinite(p.x) || !Number.isFinite(p.y))) return "坐标必须为有限数值";
  if (polygonArea(points) <= 0.001) return "多边形面积必须大于 0";
  return null;
};

const squaredDistance = (a: RiskPolygonPoint, b: RiskPolygonPoint) => {
  const dx = a.x - b.x;
  const dy = a.y - b.y;
  return dx * dx + dy * dy;
};

const perpendicularSquaredDistance = (p: RiskPolygonPoint, a: RiskPolygonPoint, b: RiskPolygonPoint) => {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const lengthSq = dx * dx + dy * dy;
  if (lengthSq === 0) return squaredDistance(p, a);
  const t = Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / lengthSq));
  return squaredDistance(p, { x: a.x + t * dx, y: a.y + t * dy });
};

const douglasPeucker = (points: RiskPolygonPoint[], toleranceSq: number) => {
  const keep = new Array<boolean>(points.length).fill(false);
  keep[0] = true;
  keep[points.length - 1] = true;
  const stack: Array<[number, number]> = [[0, points.length - 1]];
  while (stack.length) {
    const [start, end] = stack.pop()!;
    let maxDistSq = 0;
    let maxIndex = -1;
    for (let i = start + 1; i < end; i++) {
      const distSq = perpendicularSquaredDistance(points[i], points[start], points[end]);
      if (distSq > maxDistSq) {
        maxDistSq = distSq;
        maxIndex = i;
      }
    }
    if (maxIndex !== -1 && maxDistSq > toleranceSq) {
      keep[maxIndex] = true;
      stack.push([start, maxIndex], [maxIndex, end]);
    }
  }
  return points.filter((_, i) => keep[i]);
};

export const simplifyPolygon = (points: RiskPolygonPoint[], tolerance = 0.15) => {
  if (points.length <= 3) return points.slice();
  const toleranceSq = tolerance * tolerance;
  // Split the closed ring at its widest pair so simplification has no seam bias.
  let startIndex = 0;
  let endIndex = 1;
  let maxDistSq = -1;
  for (let i = 0; i < points.length; i++) {
    for (let j = i + 1; j < points.length; j++) {
      const distSq = squaredDistance(points[i], points[j]);
      if (distSq > maxDistSq) {
        maxDistSq = distSq;
        startIndex = i;
        endIndex = j;
      }
    }
  }
  const chain = (from: number, to: number) => {
    const sequence: RiskPolygonPoint[] = [];
    let index = from;
    while (index !== to) {
      sequence.push(points[index]);
      index = (index + 1) % points.length;
    }
    sequence.push(points[to]);
    return sequence;
  };
  const firstHalf = douglasPeucker(chain(startIndex, endIndex), toleranceSq);
  const secondHalf = douglasPeucker(chain(endIndex, startIndex), toleranceSq);
  const simplified = [...firstHalf, ...secondHalf.slice(1, -1)];
  if (simplified.length < 3 || validatePolygon(simplified) !== null) return points.slice();
  return simplified;
};
