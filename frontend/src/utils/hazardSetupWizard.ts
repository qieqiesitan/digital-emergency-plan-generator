/**
 * 「AI 智能引导」的纯映射逻辑（无 React、可单测）。
 *
 * 为什么单独抽出来：AI 只给**名字**（分区名、责任人姓名、节点 type），
 * 而落库端点要的是 **id** 与固定枚举。这套"名字 → id + 缺省补齐"的规则
 * 与「AI 生成计划」弹窗完全一致（HazardPlanPage.adoptBuiltPlan），
 * 若各写一份必然漂移，所以统一放这里，两处共用。
 */
import type { HazardChecklistTemplateItem, HazardInspectionPlanCreate, HazardPlanBuilderResult } from "@/types/hazard";
import type { OrgNode, OrgNodeType } from "@/types/enterpriseOrg";

/** weekly/custom 未给 weekdays 时的兜底（与后端 _check_frequency_weekdays 的必填约束对齐）。 */
export const WIZARD_WEEKDAY_FALLBACK = [1, 2, 3, 4, 5];

const ORG_NODE_TYPES: OrgNodeType[] = ["dept", "team", "position"];

export interface WizardZone {
  id: string;
  name: string;
}

export interface WizardMember {
  user_id: string | null;
  name?: string | null;
  email?: string | null;
  enabled?: boolean;
}

export interface MappedPlan {
  payload: HazardInspectionPlanCreate;
  /** 建议里出现、但企业现有分区中找不到的名字（需要用户手动补选）。 */
  unmatchedZones: string[];
  /** 建议的责任人姓名是否匹配到了启用成员。 */
  responsibleMatched: boolean;
}

function isWeeklyish(frequency: string): boolean {
  return frequency === "weekly" || frequency === "custom";
}

/** AI 计划建议 → 可直接提交给 POST /hazard-inspection/plans 的载荷。 */
export function buildPlanPayloads(
  plans: ReadonlyArray<HazardPlanBuilderResult["plans"][number]> | null | undefined,
  zones: WizardZone[],
  members: WizardMember[],
): MappedPlan[] {
  return (plans ?? []).map((plan) => {
    const zoneNames = plan.zone_names ?? [];
    const zoneIds = zoneNames
      .map((name) => zones.find((z) => z.name === name)?.id)
      .filter((v): v is string => Boolean(v));
    const unmatchedZones = zoneNames.filter((name) => !zones.some((z) => z.name === name));
    const member = plan.responsible_user_name
      ? members.find((m) => (m.name || m.email || m.user_id) === plan.responsible_user_name)
      : undefined;
    const frequency = plan.frequency;
    return {
      payload: {
        name: plan.name,
        category: plan.category,
        frequency,
        // 非 weekly/custom 一律不带 weekdays —— 与新建弹窗保存时的规则一致
        // （后端 _check_frequency_weekdays 只对 weekly/custom 强制必填，
        //  带上月度计划的旧 weekdays 会让后续编辑界面出现无意义的值）。
        weekdays: isWeeklyish(frequency)
          ? (plan.weekdays?.length ? plan.weekdays : [...WIZARD_WEEKDAY_FALLBACK])
          : undefined,
        zone_ids: Array.from(new Set(zoneIds)),
        template_id: null,
        responsible_user_id: member?.user_id ?? undefined,
        ai_suggestion: { source: "setup_wizard", responsible_user_name: plan.responsible_user_name ?? null },
        enabled: true,
      },
      unmatchedZones,
      responsibleMatched: Boolean(member),
    };
  });
}

/** AI 组织树建议（{nodes:[{id,type,name,parent_id}]}）→ 可直接 PUT /org/nodes 的 OrgNode[]。 */
export function buildOrgNodes(suggestion: unknown): OrgNode[] {
  const raw = (suggestion as { nodes?: unknown } | null | undefined)?.nodes;
  if (!Array.isArray(raw)) return [];
  const nodes: OrgNode[] = [];
  const seen = new Set<string>();
  const parentOf = new Map<string, unknown>();
  for (const item of raw) {
    if (!item || typeof item !== "object") continue;
    const { id, type, name, parent_id } = item as Record<string, unknown>;
    if (typeof id !== "string" || !id.trim() || seen.has(id)) continue;
    if (typeof name !== "string" || !name.trim()) continue;
    if (typeof type !== "string" || !ORG_NODE_TYPES.includes(type as OrgNodeType)) continue;
    seen.add(id);
    parentOf.set(id, parent_id);
    nodes.push({ id, type: type as OrgNodeType, name: name.trim(), parent_id: null, members: [] });
  }
  // 悬空 parent_id 一律归零（后端 normalize 会拒绝不存在的父节点）
  for (const node of nodes) {
    const parent = parentOf.get(node.id);
    node.parent_id = typeof parent === "string" && seen.has(parent) ? parent : null;
  }
  return nodes;
}

/** AI 检查表条目 → 模板 items（丢弃空内容）。 */
export function buildChecklistItems(
  items: ReadonlyArray<{ content?: unknown; expected_note?: unknown }> | null | undefined,
): HazardChecklistTemplateItem[] {
  if (!Array.isArray(items)) return [];
  const out: HazardChecklistTemplateItem[] = [];
  for (const item of items) {
    const content = typeof item?.content === "string" ? item.content.trim() : "";
    if (!content) continue;
    const note = typeof item?.expected_note === "string" ? item.expected_note.trim() : "";
    out.push({ content, expected_note: note || undefined });
  }
  return out;
}
