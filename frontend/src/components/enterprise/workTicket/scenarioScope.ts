/**
 * 情景区的作用域工具。
 *
 * 情景项来自后端 `/templates` 响应的 `scenario_fields`（由 YAML + 生成器产出），
 * 因此**切换票种时情景区会自动跟着变**——不再像以前那样写死一组通用的动火情景。
 * 这里只保留两个纯函数：取该票种的情景项、清理不属于新票种的勾选。
 */

export interface ScenarioField {
  key: string;
  label: string;
}

/** 该票种的情景区；没有人工勾选项时返回空数组（界面据此显示提示文案）。 */
export function scenarioFieldsFor(
  template: { scenario_fields?: ScenarioField[] } | undefined,
): ScenarioField[] {
  return template?.scenario_fields ?? [];
}

/**
 * 切票种时清空上一票种的情景勾选，只保留新票种声明的键。
 *
 * 不做这一步会出现"在动火票勾了『设备内部动火』，切到受限空间票后它仍挂着"的串味问题。
 */
export function pruneScenario(
  scenario: Record<string, boolean>,
  fields: ScenarioField[],
): Record<string, boolean> {
  const allowed = new Set(fields.map((field) => field.key));
  return Object.fromEntries(
    Object.entries(scenario).filter(([key]) => allowed.has(key)),
  );
}
