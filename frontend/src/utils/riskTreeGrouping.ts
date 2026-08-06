import type { HierarchyZone } from "@/types/riskManagement";
import type { EnterpriseFloor } from "@/types/riskMappingWorkbench";

export interface FloorZoneGroup {
  floorId: string | null;
  floorName: string;
  isDefault: boolean;
  zoneCount: number;
  riskPointCount: number;
  zones: HierarchyZone[];
}

const UNASSIGNED_NAME = "未分配楼层";

export function groupZonesByFloor(
  zones: HierarchyZone[],
  floors: EnterpriseFloor[]
): FloorZoneGroup[] {
  const ordered = [...floors].sort(
    (a, b) => a.sort_order - b.sort_order || a.id.localeCompare(b.id)
  );
  const floorOrder = new Map(ordered.map((f, i) => [f.id, i]));
  const groups: FloorZoneGroup[] = ordered.map((f) => ({
    floorId: f.id,
    floorName: f.name,
    isDefault: f.is_default,
    zoneCount: 0,
    riskPointCount: f.risk_point_count ?? 0,
    zones: [],
  }));
  const unassigned: FloorZoneGroup = {
    floorId: null,
    floorName: UNASSIGNED_NAME,
    isDefault: false,
    zoneCount: 0,
    riskPointCount: 0,
    zones: [],
  };
  for (const z of zones) {
    const idx = z.floor_id != null ? floorOrder.get(z.floor_id) : undefined;
    if (idx === undefined) {
      unassigned.zones.push(z);
    } else {
      groups[idx].zones.push(z);
    }
  }
  for (const g of groups) {
    g.zoneCount = g.zones.length;
  }
  return unassigned.zones.length > 0 ? [...groups, unassigned] : groups;
}
