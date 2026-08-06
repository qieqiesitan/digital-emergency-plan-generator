import { describe, it, expect } from "vitest";
import { buildZonePayload, mergeEditedPolygon } from "./zoneSubmit";
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

  it("includes floor_id when the zone form carries a floor", () => {
    const payload = buildZonePayload({ name: "储罐区", floor_id: "floor-2" });

    expect(payload.floor_id).toBe("floor-2");
  });

  it("omits floor_id when undefined, so edits never clear an existing floor", () => {
    const payload = buildZonePayload({ name: "储罐区" });

    expect(payload).not.toHaveProperty("floor_id");
  });
});

describe("mergeEditedPolygon", () => {
  const multiRegion: RiskZoneFloorPlanPolygon = {
    version: 2,
    color_source: "manual",
    color: "#ff0000",
    polygons: [
      {
        id: "p1",
        label: "储罐区",
        points: [
          { x: 1, y: 1 },
          { x: 2, y: 1 },
          { x: 1, y: 2 },
        ],
      },
      {
        id: "p2",
        label: "装卸区",
        points: [
          { x: 5, y: 5 },
          { x: 6, y: 5 },
          { x: 5, y: 6 },
        ],
      },
    ],
  };

  it("replaces only the edited region and preserves the other regions", () => {
    const result = mergeEditedPolygon(multiRegion, "储罐区", [
      { x: 10, y: 10 },
      { x: 20, y: 10 },
      { x: 15, y: 20 },
    ]);

    expect(result.polygons).toHaveLength(2);
    expect(result.polygons[0].id).toBe("p1");
    expect(result.polygons[0].points).toEqual([
      { x: 10, y: 10 },
      { x: 20, y: 10 },
      { x: 15, y: 20 },
    ]);
    expect(result.polygons[1]).toEqual(multiRegion.polygons[1]);
  });

  it("keeps the v2 color_source and color instead of resetting to auto", () => {
    const result = mergeEditedPolygon(multiRegion, "储罐区", multiRegion.polygons[0].points);

    expect(result.version).toBe(2);
    expect(result.color_source).toBe("manual");
    expect(result.color).toBe("#ff0000");
  });

  it("creates a fresh auto-colored single-region polygon when nothing existed", () => {
    const result = mergeEditedPolygon(null, "新区域", [
      { x: 0, y: 0 },
      { x: 1, y: 0 },
      { x: 0, y: 1 },
    ]);

    expect(result.version).toBe(2);
    expect(result.color_source).toBe("auto");
    expect(result.color).toBeNull();
    expect(result.polygons).toHaveLength(1);
    expect(result.polygons[0].label).toBe("新区域");
  });
});
