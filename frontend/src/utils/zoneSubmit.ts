import type { RiskZoneCreate, RiskZoneFloorPlanPolygon } from "@/types/riskManagement";

export interface ZoneSubmitValues {
  name?: string;
  description?: string;
  floor_plan_polygon?: RiskZoneFloorPlanPolygon | null;
}

// Build the create/update payload for a zone. floor_plan_polygon is only
// included when the user actually drew/submitted one, so that editing a zone
// from the legacy form never clears an existing workbench polygon with null.
export function buildZonePayload(
  values: ZoneSubmitValues
): Pick<RiskZoneCreate, "name" | "description" | "floor_plan_polygon"> {
  const payload: Pick<RiskZoneCreate, "name" | "description" | "floor_plan_polygon"> = {
    name: values.name || "",
    description: values.description || "",
  };
  if (values.floor_plan_polygon) {
    payload.floor_plan_polygon = values.floor_plan_polygon;
  }
  return payload;
}
