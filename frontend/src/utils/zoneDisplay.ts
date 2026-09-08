import type { WorkbenchZone } from "@/types/riskMappingWorkbench";
import { RISK_LEVEL_COLORS } from "@/utils/riskMethodEngine";

export type ZoneColorMode = "current" | "inherent";

/**
 * 分区展示色的唯一事实源解析：
 * level_mode=manual 时颜色由 floor_plan_polygon.risk_level 实时派生（本地修改立即生效）；
 * auto 时使用后端按风险对象推导的 effective_color。
 */
export function zoneDisplayColor(zone: WorkbenchZone, mode: ZoneColorMode): string {
  const poly = zone.floor_plan_polygon;
  if (poly?.level_mode === "manual" && poly.risk_level && RISK_LEVEL_COLORS[poly.risk_level]) {
    return RISK_LEVEL_COLORS[poly.risk_level];
  }
  const autoColor = mode === "inherent"
    ? zone.inherent_effective_color ?? zone.effective_color
    : zone.effective_color;
  return autoColor ?? "#d9d9d9";
}

/** 分区展示等级：手动指定优先，否则用后端推导等级。 */
export function zoneDisplayLevel(zone: WorkbenchZone): string {
  const poly = zone.floor_plan_polygon;
  if (poly?.level_mode === "manual" && poly.risk_level) {
    return poly.risk_level;
  }
  return zone.max_risk_level || "未评估";
}
