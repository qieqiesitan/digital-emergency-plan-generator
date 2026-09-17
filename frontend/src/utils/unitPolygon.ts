import type {
  MajorHazardUnitPolygon,
  MajorHazardUnitPolygonPoint,
} from "@/types/majorHazard";
import { clampPoint, validatePolygon } from "@/utils/riskMappingGeometry";

/**
 * 单元落点多边形的读写纯函数。
 *
 * 坐标约定与四色图工作台一致：百分比 0-100，几何算法直接复用
 * `riskMappingGeometry`，本模块不重复实现。
 */

/** 宽容解析：脏数据一律当作"无落点"，不抛错、不猜。 */
export function parseUnitPolygon(raw: unknown): MajorHazardUnitPolygon | null {
  if (!raw || typeof raw !== "object") return null;
  const source = raw as { points?: unknown };
  if (!Array.isArray(source.points) || source.points.length < 3) return null;
  const points: MajorHazardUnitPolygonPoint[] = [];
  for (const item of source.points) {
    if (!item || typeof item !== "object") return null;
    const { x, y } = item as { x?: unknown; y?: unknown };
    if (typeof x !== "number" || typeof y !== "number") return null;
    if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
    points.push(clampPoint({ x, y }));
  }
  if (validatePolygon(points) !== null) return null;
  return { version: 1, points };
}

/** 构造待提交载荷；顶点不足或退化（面积为 0）时返回 null，由调用方提示。 */
export function buildUnitPolygon(
  points: MajorHazardUnitPolygonPoint[],
): MajorHazardUnitPolygon | null {
  const clamped = points.map(clampPoint);
  if (validatePolygon(clamped) !== null) return null;
  return { version: 1, points: clamped };
}

/** 顶点是否足够构成可保存的多边形（供按钮禁用态使用）。 */
export function isUnitPolygonComplete(points: MajorHazardUnitPolygonPoint[]): boolean {
  return buildUnitPolygon(points) !== null;
}

/**
 * 判断一次落点是否应视为「闭合」：点到首顶点的距离小于阈值。
 * 距离单位为百分比，默认 4（约 48px @1200 宽）。
 */
export function isClosingClick(
  points: MajorHazardUnitPolygonPoint[],
  candidate: MajorHazardUnitPolygonPoint,
  threshold = 4,
): boolean {
  if (points.length < 3) return false;
  const first = points[0];
  return Math.hypot(candidate.x - first.x, candidate.y - first.y) <= threshold;
}
