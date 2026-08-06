import type { SmartGuideZone } from "@/types/riskManagement";

export interface ImportPlan {
  filteredHierarchy: SmartGuideZone[];
  skippedZones: string[];
}

/** 过滤与现有分区重名的分区；nameOverrides 以 z-{index} 为 key（与组件约定一致）。 */
export function buildImportPlan(
  hierarchy: SmartGuideZone[],
  nameOverrides: Record<string, string>,
  existingZoneNames: Set<string>,
): ImportPlan {
  const filteredHierarchy: SmartGuideZone[] = [];
  const skippedZones: string[] = [];
  hierarchy.forEach((zone, zi) => {
    const effectiveName = nameOverrides[`z-${zi}`] ?? zone.name;
    if (existingZoneNames.has(effectiveName)) {
      skippedZones.push(effectiveName);
      return;
    }
    filteredHierarchy.push(zone);
  });
  return { filteredHierarchy, skippedZones };
}
