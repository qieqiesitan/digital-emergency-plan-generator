import type { RiskPolygon, RiskZoneCreate, RiskZoneFloorPlanPolygon } from "@/types/riskManagement";

export interface ZoneSubmitValues {
  name?: string;
  description?: string;
  floor_plan_polygon?: RiskZoneFloorPlanPolygon | null;
  floor_id?: string | null;
}

// Build the create/update payload for a zone. floor_plan_polygon is only
// included when the user actually drew/submitted one, so that editing a zone
// from the legacy form never clears an existing workbench polygon with null.
// floor_id follows the same rule: only included when explicitly chosen, so an
// edit from the legacy form never clears an existing floor assignment.
export function buildZonePayload(
  values: ZoneSubmitValues
): Pick<RiskZoneCreate, "name" | "description" | "floor_plan_polygon" | "floor_id"> {
  const payload: Pick<RiskZoneCreate, "name" | "description" | "floor_plan_polygon" | "floor_id"> = {
    name: values.name || "",
    description: values.description || "",
  };
  if (values.floor_plan_polygon) {
    payload.floor_plan_polygon = values.floor_plan_polygon;
  }
  if (values.floor_id) {
    payload.floor_id = values.floor_id;
  }
  return payload;
}

// Merge the polygon the user just drew into the existing v2 floor_plan_polygon
// when editing a zone from the legacy form. Only the region loaded into the
// editor (polygons[0]) is replaced; other regions and the v2 color
// source/color are preserved so a multi-region zone is never silently
// reduced to a single region or reset to auto color.
export function mergeEditedPolygon(
  existing: RiskZoneFloorPlanPolygon | null | undefined,
  name: string | undefined,
  points: { x: number; y: number }[]
): RiskZoneFloorPlanPolygon {
  const current = existing?.version === 2 ? existing : null;
  const edited: RiskPolygon = {
    id: current?.polygons?.[0]?.id ?? crypto.randomUUID(),
    label: name || "未命名区域",
    points,
  };
  const rest = current?.polygons?.slice(1) ?? [];
  return {
    version: 2,
    color_source: current?.color_source ?? "auto",
    color: current?.color ?? null,
    polygons: [edited, ...rest],
  };
}
