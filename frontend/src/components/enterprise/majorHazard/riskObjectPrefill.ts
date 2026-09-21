import type { LinkableRiskObject, MajorHazardUnitPayload } from "@/types/majorHazard";

/**
 * 单元表单可被风险点带出的字段。
 *
 * 单独成文件：组件文件只能导出组件（react-refresh/only-export-components），
 * 常量与纯函数混在组件里会触发 lint。参照 workTicket/fieldSources.ts。
 */
export const PREFILL_FIELD_LABELS = {
  address: "所在位置",
  department: "责任部门",
  responsible_person: "责任人",
  responsible_phone: "联系电话",
} as const;

export type PrefillField = keyof typeof PREFILL_FIELD_LABELS;

/** 空白定义：null / undefined / 纯空格都算空白。 */
function isBlank(v: unknown): boolean {
  return v == null || String(v).trim() === "";
}

export interface UnitPrefillResult {
  /**
   * 只含可带出的 4 个字段——刻意不用 `Partial<MajorHazardUnitPayload>`，
   * 好让调用方不必强转就能塞进 form.setFieldsValue 与来源标记状态。
   */
  patch: Partial<Record<PrefillField, string>>;
  fields: PrefillField[];
}

/**
 * 从风险点带出单元表单的空白项。
 *
 * 只填空白项、不覆盖人工值：目标是省一遍打字，不是纠正人工值。
 * 名称、楼层、多边形不参与带出——名单和单元不是同一命名维度，而楼层与多边形在
 * 接口上必须成对提交（`PUT /units/{id}/polygon`），且风险点存的是一个坐标点，
 * 不是单元边界。详见规格 §2.4。
 */
export function buildUnitPrefill(
  source: LinkableRiskObject,
  current: Partial<MajorHazardUnitPayload>,
): UnitPrefillResult {
  const mapping: Array<[PrefillField, string | null | undefined]> = [
    ["address", source.location],
    ["department", source.responsible_unit],
    ["responsible_person", source.responsible_person],
    ["responsible_phone", source.contact_phone],
  ];
  const patch: Partial<Record<PrefillField, string>> = {};
  const fields: PrefillField[] = [];
  for (const [field, value] of mapping) {
    if (isBlank(value)) continue;
    if (!isBlank(current[field])) continue;
    patch[field] = String(value).trim();
    fields.push(field);
  }
  return { patch, fields };
}

/**
 * 来源标记是否还该显示。
 *
 * 判定标准是"值没被改过"，而不是"填过一次"——用户只要动过这个字段，
 * 它就不再是"来自风险点"的值了，继续标着反而误导。
 */
export function isPrefillMarkVisible(
  prefilled: Partial<Record<string, string>>,
  field: string,
  currentValue: unknown,
): boolean {
  const v = prefilled[field];
  return v != null && currentValue === v;
}
