import type { HierarchyZone } from "@/types/riskManagement";

export interface HierarchyEventRow {
  id: string;
  accident_type: string;
  risk_level: string | null;
  zone: string;
  object: string;
  unit: string | null;
}

export function flattenHierarchyEvents(zones: HierarchyZone[]): HierarchyEventRow[] {
  return zones.flatMap((zone) =>
    (zone.objects || []).flatMap((obj) => {
      const objectEvents = (obj.events || []).map((ev) => ({
        id: ev.id,
        accident_type: ev.accident_type,
        risk_level: ev.risk_level,
        zone: zone.name,
        object: obj.name,
        unit: null,
      }));
      const unitEvents = (obj.units || []).flatMap((unit) =>
        (unit.events || []).map((ev) => ({
          id: ev.id,
          accident_type: ev.accident_type,
          risk_level: ev.risk_level,
          zone: zone.name,
          object: obj.name,
          unit: unit.name,
        }))
      );
      return [...objectEvents, ...unitEvents];
    })
  );
}
