import type { HierarchyZone, SmartGuideZone } from "@/types/riskManagement";

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

export interface ExistingIndex {
  /** 分区名 → 分区 id */
  zones: Map<string, string>;
  /** 分区名 → (对象名 → 对象 id) */
  objects: Map<string, Map<string, string>>;
  /** 对象 id → (单元名 → 单元 id) */
  units: Map<string, Map<string, string>>;
  /** 父节点 id（对象/单元）→ 已有事故类型集合 */
  events: Map<string, Set<string>>;
  /** 父节点 id → (事故类型 → 事件 id)，用于向已有事件补充缺失措施 */
  eventIds: Map<string, Map<string, string>>;
  /** 事件 id → 「类别|描述」措施键集合 */
  measures: Map<string, Set<string>>;
}

/** 把现有风险层级树建成去重索引，供智能引导「补充合并」导入使用。 */
export function buildExistingIndex(zones: HierarchyZone[]): ExistingIndex {
  const zonesMap = new Map<string, string>();
  const objectsMap = new Map<string, Map<string, string>>();
  const unitsMap = new Map<string, Map<string, string>>();
  const eventsMap = new Map<string, Set<string>>();
  const eventIdsMap = new Map<string, Map<string, string>>();
  const measuresMap = new Map<string, Set<string>>();

  const addEvent = (parentId: string, ev: { id: string; accident_type: string; measures?: Array<{ measure_category?: string | null; description?: string | null }> }) => {
    const set = eventsMap.get(parentId) ?? new Set<string>();
    set.add(ev.accident_type);
    eventsMap.set(parentId, set);
    const ids = eventIdsMap.get(parentId) ?? new Map<string, string>();
    ids.set(ev.accident_type, ev.id);
    eventIdsMap.set(parentId, ids);
    const measureKeys = new Set<string>();
    measuresMap.set(ev.id, measureKeys);
    for (const m of ev.measures ?? []) {
      measureKeys.add(`${m.measure_category ?? ""}|${m.description ?? ""}`);
    }
  };

  for (const z of zones) {
    zonesMap.set(z.name, z.id);
    const objByName = new Map<string, string>();
    objectsMap.set(z.name, objByName);
    for (const o of z.objects ?? []) {
      objByName.set(o.name, o.id);
      const unitByName = new Map<string, string>();
      unitsMap.set(o.id, unitByName);
      for (const u of o.units ?? []) unitByName.set(u.name, u.id);
      for (const ev of o.events ?? []) addEvent(o.id, ev);
      for (const u of o.units ?? []) {
        for (const ev of u.events ?? []) addEvent(u.id, ev);
      }
    }
  }
  return {
    zones: zonesMap,
    objects: objectsMap,
    units: unitsMap,
    events: eventsMap,
    eventIds: eventIdsMap,
    measures: measuresMap,
  };
}

export type MergeBadge = "new" | "merge";

/**
 * 预判 AI 生成树各节点导入时是「并入现有」还是「新增」。
 * key 体系与预览树一致（z-{zi} / {parent}-o-{oi} / {parent}-u-{ui} / {parent}-ev-{ei}）；
 * 判定与 RiskSmartGuideModal.importMut 的合并逻辑一一对应；父节点新增时子节点必为 new。
 */
export function buildMergeBadges(
  index: ExistingIndex,
  hierarchy: SmartGuideZone[],
  nameOverrides: Record<string, string> = {},
): Map<string, MergeBadge> {
  const badges = new Map<string, MergeBadge>();
  hierarchy.forEach((zone, zi) => {
    const zoneKey = `z-${zi}`;
    const zoneName = nameOverrides[zoneKey] ?? zone.name;
    const zoneId = index.zones.get(zoneName);
    badges.set(zoneKey, zoneId ? "merge" : "new");

    (zone.objects || []).forEach((obj, oi) => {
      const objKey = `${zoneKey}-o-${oi}`;
      const objName = nameOverrides[objKey] ?? obj.name;
      const objId = zoneId ? index.objects.get(zoneName)?.get(objName) : undefined;
      badges.set(objKey, objId ? "merge" : "new");

      (obj.units || []).forEach((unit, ui) => {
        const unitKey = `${objKey}-u-${ui}`;
        const unitName = nameOverrides[unitKey] ?? unit.name;
        const unitId = objId ? index.units.get(objId)?.get(unitName) : undefined;
        badges.set(unitKey, unitId ? "merge" : "new");

        (unit.events || []).forEach((ev, ei) => {
          const evKey = `${unitKey}-ev-${ei}`;
          const evName = nameOverrides[evKey] ?? ev.accident_type;
          const merged = unitId ? index.eventIds.get(unitId)?.has(evName) ?? false : false;
          badges.set(evKey, merged ? "merge" : "new");
        });
      });

      (obj.events || []).forEach((ev, ei) => {
        const evKey = `${objKey}-ev-${ei}`;
        const evName = nameOverrides[evKey] ?? ev.accident_type;
        const merged = objId ? index.eventIds.get(objId)?.has(evName) ?? false : false;
        badges.set(evKey, merged ? "merge" : "new");
      });
    });
  });
  return badges;
}
