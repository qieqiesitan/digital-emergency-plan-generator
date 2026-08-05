import { describe, it, expect } from "vitest";
import { buildZonePayload } from "./zoneSubmit";
import type { RiskZoneFloorPlanPolygon } from "@/types/riskManagement";

const polygon: RiskZoneFloorPlanPolygon = {
  version: 2,
  color_source: "auto",
  color: null,
  polygons: [
    {
      id: "p1",
      label: "储罐区",
      points: [
        { x: 10, y: 10 },
        { x: 20, y: 10 },
        { x: 15, y: 20 },
      ],
    },
  ],
};

describe("buildZonePayload", () => {
  it("includes floor_plan_polygon when the user drew and submitted a polygon", () => {
    const payload = buildZonePayload({
      name: "储罐区",
      description: "描述",
      floor_plan_polygon: polygon,
    });

    expect(payload.name).toBe("储罐区");
    expect(payload.description).toBe("描述");
    expect(payload.floor_plan_polygon).toEqual(polygon);
  });

  it("omits floor_plan_polygon when editing without drawing, so the backend keeps the existing polygon", () => {
    const payload = buildZonePayload({ name: "储罐区", description: "描述" });

    expect(payload).not.toHaveProperty("floor_plan_polygon");
  });

  it("omits floor_plan_polygon when the form value is explicitly null", () => {
    const payload = buildZonePayload({ name: "储罐区", floor_plan_polygon: null });

    expect(payload).not.toHaveProperty("floor_plan_polygon");
  });
});
