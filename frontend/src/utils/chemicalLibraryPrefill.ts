import type { ChemicalLibraryItem } from "@/types/chemicalLibrary";

/** 库条目 → 企业台账表单预填值（标准字段复制 + library_id 来源标记）。 */
export function libraryItemToPrefill(item: ChemicalLibraryItem): Record<string, unknown> {
  const keys = [
    "name", "cas_no", "un_no", "physical_state", "flash_point", "explosion_limit",
    "ignition_temp", "density", "boiling_point", "health_hazard", "fire_hazard",
    "leak_response", "storage_transport", "first_aid", "protective_measures",
  ] as const;
  const out: Record<string, unknown> = { library_id: item.id };
  for (const k of keys) {
    out[k] = item[k] ?? undefined;
  }
  return out;
}
