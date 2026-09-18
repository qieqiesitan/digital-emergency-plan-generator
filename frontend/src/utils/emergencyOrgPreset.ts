import { PRESET_EMERGENCY_GROUPS } from "@/utils/constants";
import type { EmergencyUnit } from "@/types/emergencyOrg";

const HQ_KEY = "headquarters";
const PRESET_ROOT_ID = "preset-emergency-root";

/**
 * 预置应急组织：顶层「应急组织机构」→ 各应急小组 → 组内角色。
 * 顺序：顶层在前，保证合并时父节点映射可解析。
 */
export function buildPresetUnits(): EmergencyUnit[] {
  const units: EmergencyUnit[] = [
    { id: PRESET_ROOT_ID, parent_id: null, name: "应急组织机构", duties: "", roles: [] },
  ];
  Object.entries(PRESET_EMERGENCY_GROUPS).forEach(([key, name], gi) => {
    const unitId = `preset-${key}`;
    const roleNames = key === HQ_KEY ? ["总指挥", "副总指挥", "成员"] : ["组长", "副组长", "组员"];
    units.push({
      id: unitId,
      parent_id: PRESET_ROOT_ID,
      name,
      duties: "",
      sort_order: gi,
      roles: roleNames.map((roleName, ri) => ({
        id: `${unitId}-role-${ri}`,
        name: roleName,
        duties: "",
        sort_order: ri,
        is_required: roleName === "总指挥" || roleName === "副总指挥",
        member_ids: [],
      })),
    });
  });
  return units;
}

/**
 * 增量合并应急组织：保留已有单元、已有角色与已有人员指派，只补缺失的单元与角色。
 * 单元按 (name, 父单元) 匹配，避免同名小组重复建树；不修改传入的 existing（纯函数）。
 */
export function mergeEmergencyUnits(
  existing: EmergencyUnit[],
  incoming: EmergencyUnit[],
): EmergencyUnit[] {
  const result: EmergencyUnit[] = existing.map(u => ({
    ...u,
    roles: (u.roles ?? []).map(r => ({ ...r, member_ids: [...(r.member_ids ?? [])] })),
  }));
  // incoming 父单元 id → 合并后实际节点 id
  const idMap = new Map<string, string>();

  for (const inc of incoming) {
    const parentId = inc.parent_id ? (idMap.get(inc.parent_id) ?? null) : null;
    const found = result.find(u => u.name === inc.name && (u.parent_id ?? null) === parentId);
    if (found) {
      idMap.set(inc.id ?? inc.name, found.id ?? inc.name);
      for (const role of inc.roles ?? []) {
        if (!(found.roles ?? []).some(r => r.name === role.name)) {
          found.roles = [...(found.roles ?? []), { ...role, member_ids: [] }];
        }
      }
      continue;
    }
    const newId = inc.id ?? `unit-${result.length + 1}`;
    result.push({
      ...inc,
      id: newId,
      parent_id: parentId,
      roles: (inc.roles ?? []).map(r => ({ ...r, member_ids: [] })),
    });
    idMap.set(inc.id ?? inc.name, newId);
  }
  return result;
}
