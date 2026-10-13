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
  /** 分区名 → 分区 id 列表（同名多分区，如四色图识别出的多个「加油机」，按顺序保留） */
  zones: Map<string, string[]>;
  /** 分区 id → (对象名 → 对象 id)（按 id 存：同名分区各自的对象不串数据） */
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
  const zonesMap = new Map<string, string[]>();
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
    const ids = zonesMap.get(z.name) ?? [];
    ids.push(z.id);
    zonesMap.set(z.name, ids);
    const objByName = new Map<string, string>();
    objectsMap.set(z.id, objByName);
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

/**
 * 决策每个 AI 分区段要并入的现有分区 id 列表（空数组 = 新建）。
 *
 * 现有树里可能存在多个同名分区（四色图识别出的设备位置，如 4 个「加油机」），
 * 它们是多个实体、不是重复数据。策略：
 * - 无同名 → 新建；
 * - AI 同名段数 ≥ 现有同名分区数 → 按出现顺序一一对应（第 k 段 → 第 k 个现有，超出则新建）；
 * - AI 同名段数 <  现有同名分区数 → 该段分发到全部同名分区（同类设备共享相同风险内容）。
 */
export function planZoneTargets(
  index: ExistingIndex,
  hierarchy: SmartGuideZone[],
  nameOverrides: Record<string, string> = {},
): Map<string, string[]> {
  const occurrences = new Map<string, number>();
  hierarchy.forEach((zone, zi) => {
    const name = nameOverrides[`z-${zi}`] ?? zone.name;
    occurrences.set(name, (occurrences.get(name) ?? 0) + 1);
  });
  const plan = new Map<string, string[]>();
  const seen = new Map<string, number>();
  hierarchy.forEach((zone, zi) => {
    const zoneKey = `z-${zi}`;
    const name = nameOverrides[zoneKey] ?? zone.name;
    const existing = index.zones.get(name) ?? [];
    const emitted = seen.get(name) ?? 0;
    seen.set(name, emitted + 1);
    if (existing.length === 0) {
      plan.set(zoneKey, []);
      return;
    }
    if ((occurrences.get(name) ?? 1) >= existing.length) {
      const target = existing[emitted];
      plan.set(zoneKey, target ? [target] : []);
    } else {
      plan.set(zoneKey, [...existing]);
    }
  });
  return plan;
}

export interface MergeBadge {
  kind: "new" | "merge";
  /** 目标现有分区数（>1 表示分发到多个同名分区，UI 显示「并入 ×N」） */
  count: number;
}

/**
 * 预判 AI 生成树各节点导入时是「并入现有」还是「新增」。
 * key 体系与预览树一致（z-{zi} / {parent}-o-{oi} / {parent}-u-{ui} / {parent}-ev-{ei}）；
 * 分区级判定与 planZoneTargets 完全一致（含同名分发 ×N）；
 * 对象/单元/事件级在分发场景取第一个目标分区的数据做近似提示（导入结果统计以实际执行为准）。
 */
export function buildMergeBadges(
  index: ExistingIndex,
  hierarchy: SmartGuideZone[],
  nameOverrides: Record<string, string> = {},
): Map<string, MergeBadge> {
  const badges = new Map<string, MergeBadge>();
  const plan = planZoneTargets(index, hierarchy, nameOverrides);
  const single = (kind: "new" | "merge"): MergeBadge => ({ kind, count: 1 });
  hierarchy.forEach((zone, zi) => {
    const zoneKey = `z-${zi}`;
    const targets = plan.get(zoneKey) ?? [];
    badges.set(zoneKey, targets.length
      ? { kind: "merge", count: targets.length }
      : single("new"));
    const anyZoneId = targets[0];
    const objById = anyZoneId ? index.objects.get(anyZoneId) : undefined;

    (zone.objects || []).forEach((obj, oi) => {
      const objKey = `${zoneKey}-o-${oi}`;
      const objName = nameOverrides[objKey] ?? obj.name;
      const objId = objById?.get(objName);
      badges.set(objKey, single(objId ? "merge" : "new"));

      (obj.units || []).forEach((unit, ui) => {
        const unitKey = `${objKey}-u-${ui}`;
        const unitName = nameOverrides[unitKey] ?? unit.name;
        const unitId = objId ? index.units.get(objId)?.get(unitName) : undefined;
        badges.set(unitKey, single(unitId ? "merge" : "new"));

        (unit.events || []).forEach((ev, ei) => {
          const evKey = `${unitKey}-ev-${ei}`;
          const evName = nameOverrides[evKey] ?? ev.accident_type;
          const merged = unitId ? index.eventIds.get(unitId)?.has(evName) ?? false : false;
          badges.set(evKey, single(merged ? "merge" : "new"));
        });
      });

      (obj.events || []).forEach((ev, ei) => {
        const evKey = `${objKey}-ev-${ei}`;
        const evName = nameOverrides[evKey] ?? ev.accident_type;
        const merged = objId ? index.eventIds.get(objId)?.has(evName) ?? false : false;
        badges.set(evKey, single(merged ? "merge" : "new"));
      });
    });
  });
  return badges;
}
