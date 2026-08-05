import { beforeEach, describe, it, expect } from "vitest";
import { useRiskMappingWorkbenchStore, undo, redo } from "./riskMappingWorkbenchStore";
import type { EnterpriseFloor, WorkbenchZone } from "@/types/riskMappingWorkbench";
import type { RiskObject } from "@/types/riskManagement";
import {
  toPercent,
  toCanvasX,
  toCanvasY,
  pointsToKonva,
  circlePoints,
  ellipsePoints,
  polygonCentroid,
  quadraticCurvePoints,
  polygonArea,
  validatePolygon,
  simplifyPolygon,
} from "@/utils/riskMappingGeometry";

const makeFloor = (id: string): EnterpriseFloor => ({
  id,
  enterprise_id: "e1",
  name: `F${id}`,
  sort_order: 0,
  floor_plan_url: null,
  canvas_texts: [],
  is_default: false,
  updated_at: "2026-01-01T00:00:00Z",
});

const makeZone = (id: string): WorkbenchZone => ({
  id,
  enterprise_id: "e1",
  floor_id: "f1",
  floor_name: "F1",
  name: id,
  description: null,
  sort_order: 0,
  floor_plan_polygon: null,
  max_risk_level: null,
  effective_color: null,
  object_count: 0,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
});

const makeRiskPoint = (id: string): RiskObject => ({
  id,
  enterprise_id: "e1",
  zone_id: null,
  floor_id: "f1",
  name: `P${id}`,
  category: null,
  location: null,
  location_x: 50,
  location_y: 50,
  description: null,
  image_url: null,
  is_risk_point: true,
  sort_order: 0,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  unit_count: 0,
});

describe("riskMappingWorkbenchStore", () => {
  beforeEach(() => {
    useRiskMappingWorkbenchStore.getState().reset();
  });

  it("commit-then-setSnapshot pushes the pre-change domain snapshot", () => {
    const store = useRiskMappingWorkbenchStore;
    store.setState({ tool: "polygon", selectedZoneId: "z1", dirty: false });
    store.getState().commit();
    store.getState().setSnapshot({ zones: [makeZone("a")] });
    const state = store.getState();
    expect(state.dirty).toBe(true);
    expect(state.zones).toEqual([makeZone("a")]);
    expect(state.past).toHaveLength(1);
    expect(Object.keys(state.past[0]).sort()).toEqual([
      "currentFloorId",
      "deletedRiskPointIds",
      "deletedZoneIds",
      "floors",
      "pendingRegions",
      "riskPoints",
      "texts",
      "zones",
    ]);
    expect(state.past[0].zones).toEqual([]);
  });

  it("undo restores domain fields while preserving UI state", () => {
    const store = useRiskMappingWorkbenchStore;
    store.setState({ tool: "polygon", selectedZoneId: "z-sel", gridEnabled: false, snapEnabled: false, guideEnabled: false });
    store.getState().commit();
    store.getState().setSnapshot({ floors: [makeFloor("a")], currentFloorId: "a", zones: [makeZone("a")] });
    store.setState({ tool: "select", selectedZoneId: null, gridEnabled: true, snapEnabled: true, guideEnabled: true });
    store.getState().commit();
    store.getState().setSnapshot({ floors: [makeFloor("b")], currentFloorId: "b", zones: [makeZone("b")] });

    undo();

    const state = store.getState();
    expect(state.floors).toEqual([makeFloor("a")]);
    expect(state.currentFloorId).toBe("a");
    expect(state.zones).toEqual([makeZone("a")]);
    expect(state.tool).toBe("select");
    expect(state.selectedZoneId).toBeNull();
    expect(state.gridEnabled).toBe(true);
    expect(state.snapEnabled).toBe(true);
    expect(state.guideEnabled).toBe(true);
    expect(state.past).toHaveLength(1);
    expect(state.future).toHaveLength(1);
    expect(state.dirty).toBe(true);
  });

  it("redo replays the next domain snapshot and keeps UI state", () => {
    const store = useRiskMappingWorkbenchStore;
    store.setState({ tool: "polygon", selectedZoneId: "z-sel" });
    store.getState().commit();
    store.getState().setSnapshot({ zones: [makeZone("a")] });
    store.getState().commit();
    store.getState().setSnapshot({ zones: [makeZone("b")] });
    undo();
    expect(store.getState().zones).toEqual([makeZone("a")]);
    redo();

    const state = store.getState();
    expect(state.zones).toEqual([makeZone("b")]);
    expect(state.tool).toBe("polygon");
    expect(state.selectedZoneId).toBe("z-sel");
    expect(state.past).toHaveLength(2);
    expect(state.future).toHaveLength(0);
  });

  it("a new commit after undo clears the future stack", () => {
    const store = useRiskMappingWorkbenchStore;
    store.getState().commit();
    store.getState().setSnapshot({ zones: [makeZone("a")] });
    store.getState().commit();
    store.getState().setSnapshot({ zones: [makeZone("b")] });
    undo();
    expect(store.getState().future).toHaveLength(1);

    store.getState().commit();
    store.getState().setSnapshot({ zones: [makeZone("c")] });
    expect(store.getState().future).toHaveLength(0);
    expect(store.getState().past).toHaveLength(2);
  });

  it("caps history at 50 snapshots", () => {
    const store = useRiskMappingWorkbenchStore;
    for (let i = 0; i < 60; i++) {
      store.getState().commit();
      store.getState().setSnapshot({ zones: [makeZone(`z${i}`)] });
    }
    const state = store.getState();
    expect(state.past).toHaveLength(50);
    expect(state.past[49].zones[0].id).toBe("z58");
    expect(state.future).toHaveLength(0);
  });

  it("keeps dirty true across commit, undo and redo", () => {
    const store = useRiskMappingWorkbenchStore;
    store.setState({ dirty: false });
    store.getState().commit();
    store.getState().setSnapshot({ zones: [makeZone("a")] });
    expect(store.getState().dirty).toBe(true);
    store.getState().commit();
    store.getState().setSnapshot({ zones: [makeZone("b")] });
    undo();
    expect(store.getState().dirty).toBe(true);
    redo();
    expect(store.getState().dirty).toBe(true);
  });

  it("undo reverts the actual component call sequence (commit then setSnapshot)", () => {
    const store = useRiskMappingWorkbenchStore;
    store.getState().commit();
    store.getState().setSnapshot({
      pendingRegions: [
        {
          id: "pending-1",
          floor_id: "f1",
          points: [
            { x: 0, y: 0 },
            { x: 10, y: 0 },
            { x: 10, y: 10 },
          ],
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
    expect(store.getState().pendingRegions).toHaveLength(1);

    undo();
    expect(store.getState().pendingRegions).toHaveLength(0);

    redo();
    expect(store.getState().pendingRegions).toHaveLength(1);
  });

  it("undo back to the saved snapshot clears dirty, redo marks it again", () => {
    const store = useRiskMappingWorkbenchStore;
    store.getState().setSnapshot({ zones: [makeZone("a")] });
    store.getState().markSaved();
    expect(store.getState().dirty).toBe(false);

    store.getState().commit();
    store.getState().setSnapshot({ zones: [makeZone("b")] });
    expect(store.getState().dirty).toBe(true);

    undo();
    expect(store.getState().zones).toEqual([makeZone("a")]);
    expect(store.getState().dirty).toBe(false);

    redo();
    expect(store.getState().zones).toEqual([makeZone("b")]);
    expect(store.getState().dirty).toBe(true);
  });

  it("deleteZone removes risk points under the zone and enqueues persisted ids only", () => {
    const store = useRiskMappingWorkbenchStore;
    store.setState({
      zones: [makeZone("z-persisted"), makeZone("z-new")],
      riskPoints: [
        { ...makeRiskPoint("p-persisted"), zone_id: "z-persisted" },
        { ...makeRiskPoint("new-point-2"), zone_id: "z-persisted" },
        { ...makeRiskPoint("p-other"), zone_id: "z-new" },
      ],
      deletedZoneIds: [],
      deletedRiskPointIds: [],
    });

    store.getState().deleteZone("z-persisted");

    const state = store.getState();
    expect(state.zones.map(z => z.id)).toEqual(["z-new"]);
    expect(state.riskPoints.map(p => p.id)).toEqual(["p-other"]);
    expect(state.deletedZoneIds).toEqual(["z-persisted"]);
    expect(state.deletedRiskPointIds).toEqual(["p-persisted"]);
    expect(state.deletedRiskPointIds).not.toContain("new-point-2");
  });

  it("deleteZone for a new zone never enqueues deletion ids", () => {
    const store = useRiskMappingWorkbenchStore;
    store.setState({
      zones: [makeZone("new-zone-1")],
      riskPoints: [{ ...makeRiskPoint("new-point-1"), zone_id: "new-zone-1" }],
      deletedZoneIds: [],
      deletedRiskPointIds: [],
    });

    store.getState().deleteZone("new-zone-1");

    const state = store.getState();
    expect(state.zones).toEqual([]);
    expect(state.riskPoints).toEqual([]);
    expect(state.deletedZoneIds).toEqual([]);
    expect(state.deletedRiskPointIds).toEqual([]);
  });

  it("deleteRiskPoint skips the deleted queue for new-point client ids", () => {
    const store = useRiskMappingWorkbenchStore;
    store.setState({
      riskPoints: [makeRiskPoint("new-point-1"), makeRiskPoint("p-persisted")],
      deletedRiskPointIds: [],
    });

    store.getState().deleteRiskPoint("new-point-1");
    expect(store.getState().deletedRiskPointIds).toEqual([]);

    store.getState().deleteRiskPoint("p-persisted");
    expect(store.getState().deletedRiskPointIds).toEqual(["p-persisted"]);
  });

  it("markSaved clears both past and future history stacks", () => {
    const store = useRiskMappingWorkbenchStore;
    store.getState().commit();
    store.getState().setSnapshot({ zones: [makeZone("a")] });
    store.getState().commit();
    store.getState().setSnapshot({ zones: [makeZone("b")] });
    expect(store.getState().past.length).toBeGreaterThan(0);

    store.getState().setSnapshot({ zones: [makeZone("c")] });
    store.getState().markSaved();

    const state = store.getState();
    expect(state.dirty).toBe(false);
    expect(state.past).toEqual([]);
    expect(state.future).toEqual([]);

    undo();
    expect(store.getState().zones.map(z => z.id)).toEqual(["c"]);
    redo();
    expect(store.getState().zones.map(z => z.id)).toEqual(["c"]);
  });

  it("markSaved clears the future stack populated by undo", () => {
    const store = useRiskMappingWorkbenchStore;
    store.getState().commit();
    store.getState().setSnapshot({ zones: [makeZone("a")] });
    undo();
    expect(store.getState().future.length).toBeGreaterThan(0);

    store.getState().markSaved();

    expect(store.getState().past).toEqual([]);
    expect(store.getState().future).toEqual([]);
    expect(store.getState().dirty).toBe(false);
  });

  it("deletePendingRegion removes only the selected pending region", () => {
    const store = useRiskMappingWorkbenchStore;
    store.setState({
      pendingRegions: [
        {
          id: "r1",
          floor_id: "f1",
          points: [
            { x: 0, y: 0 },
            { x: 1, y: 0 },
            { x: 1, y: 1 },
          ],
          created_at: "2026-01-01T00:00:00Z",
        },
        {
          id: "r2",
          floor_id: "f1",
          points: [
            { x: 0, y: 0 },
            { x: 1, y: 0 },
            { x: 1, y: 1 },
          ],
          created_at: "2026-01-01T00:00:00Z",
        },
      ],
      selectedRegionId: "pending:r1",
    });

    store.getState().deletePendingRegion("r1");

    expect(store.getState().pendingRegions.map(r => r.id)).toEqual(["r2"]);
    expect(store.getState().selectedRegionId).toBeNull();
  });

  it("deleteZonePolygon removes a single polygon from the zone", () => {
    const store = useRiskMappingWorkbenchStore;
    store.setState({
      zones: [
        {
          ...makeZone("z1"),
          floor_plan_polygon: {
            version: 2,
            color_source: "auto",
            color: null,
            polygons: [
              { id: "p1", label: "p1", points: [{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 1, y: 1 }] },
              { id: "p2", label: "p2", points: [{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 1, y: 1 }] },
            ],
          },
        },
      ],
      selectedRegionId: "zone:z1:p1",
    });

    store.getState().deleteZonePolygon("z1", "p1");

    const polygons = store.getState().zones[0].floor_plan_polygon?.polygons ?? [];
    expect(polygons.map(p => p.id)).toEqual(["p2"]);
    expect(store.getState().selectedRegionId).toBeNull();
  });

  it("deleteSelected commits once and removes the selected risk point", () => {
    const store = useRiskMappingWorkbenchStore;
    store.setState({
      riskPoints: [makeRiskPoint("p1"), makeRiskPoint("p2")],
      selectedRiskPointId: "p1",
    });

    store.getState().deleteSelected();

    expect(store.getState().riskPoints.map(p => p.id)).toEqual(["p2"]);
    expect(store.getState().selectedRiskPointId).toBeNull();
    expect(store.getState().past).toHaveLength(1);
  });

  it("zoomBy clamps scale and resetView restores defaults", () => {
    const store = useRiskMappingWorkbenchStore;
    store.getState().zoomBy(1.2);
    expect(store.getState().viewScale).toBeCloseTo(1.2);
    store.getState().zoomBy(100);
    expect(store.getState().viewScale).toBe(4);
    store.getState().zoomBy(0.0001);
    expect(store.getState().viewScale).toBe(0.25);
    store.setState({ viewX: 10, viewY: -10 });
    store.getState().resetView();
    expect(store.getState()).toMatchObject({ viewScale: 1, viewX: 0, viewY: 0 });
  });
});

describe("riskMappingGeometry", () => {
  it("converts between percent and canvas coordinates", () => {
    expect(toPercent(600, 1200)).toBe(50);
    expect(toPercent(1500, 1200)).toBe(100);
    expect(toCanvasX(50)).toBe(600);
    expect(toCanvasY(50)).toBe(450);
    expect(toCanvasX(50, 900)).toBe(450);
    expect(toCanvasY(50, 600)).toBe(300);
  });

  it("builds flat konva points and computes polygon area", () => {
    const points = [
      { x: 0, y: 0 },
      { x: 10, y: 0 },
      { x: 10, y: 10 },
      { x: 0, y: 10 },
    ];
    expect(pointsToKonva(points, 1000, 1000)).toEqual([0, 0, 100, 0, 100, 100, 0, 100]);
    expect(polygonArea(points)).toBe(100);
  });

  it("builds a closed circle approximation within canvas bounds", () => {
    const points = circlePoints({ x: 50, y: 50 }, 20, 360);
    expect(points).toHaveLength(360);
    expect(Math.abs(points[0].x - points[359].x)).toBeLessThan(0.5);
    expect(Math.abs(points[0].y - points[359].y)).toBeLessThan(0.5);
    expect(points.every(p => p.x >= 30 && p.x <= 70 && p.y >= 30 && p.y <= 70)).toBe(true);
    expect(validatePolygon(points)).toBeNull();
  });

  it("builds an aspect-correct ellipse approximation for non-square canvases", () => {
    const points = ellipsePoints({ x: 50, y: 50 }, 20, 12, 72);
    expect(points).toHaveLength(72);
    expect(points[0]).toEqual({ x: 70, y: 50 });
    expect(Math.min(...points.map(p => p.x))).toBeCloseTo(30);
    expect(Math.min(...points.map(p => p.y))).toBeCloseTo(38);
    expect(validatePolygon(points)).toBeNull();
  });

  it("computes the average centroid of a polygon", () => {
    expect(polygonCentroid([
      { x: 0, y: 0 },
      { x: 10, y: 0 },
      { x: 10, y: 10 },
      { x: 0, y: 10 },
    ])).toEqual({ x: 5, y: 5 });
  });

  it("builds a quadratic curve approximation with endpoints preserved", () => {
    const points = quadraticCurvePoints({ x: 0, y: 0 }, { x: 50, y: 80 }, { x: 100, y: 0 }, 10);
    expect(points).toHaveLength(11);
    expect(points[0]).toEqual({ x: 0, y: 0 });
    expect(points[10]).toEqual({ x: 100, y: 0 });
    expect(points[5].y).toBeGreaterThan(0);
    expect(points.every(p => p.x >= 0 && p.x <= 100)).toBe(true);
  });

  it("validates polygon requirements", () => {
    expect(validatePolygon([])).toBe("至少需要 3 个顶点");
    expect(validatePolygon([{ x: 0, y: 0 }, { x: 1, y: 1 }])).toBe("至少需要 3 个顶点");
    expect(validatePolygon([{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 0.5, y: 0 }])).toBe("多边形面积必须大于 0");
    expect(validatePolygon([{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 0, y: 1 }])).toBeNull();
  });

  it("rejects NaN or Infinity coordinates", () => {
    expect(validatePolygon([{ x: 0, y: 0 }, { x: NaN, y: 1 }, { x: 0, y: 1 }])).toBe("坐标必须为有限数值");
    expect(validatePolygon([{ x: 0, y: 0 }, { x: 1, y: Infinity }, { x: 0, y: 1 }])).toBe("坐标必须为有限数值");
    expect(validatePolygon([{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 0, y: 1 }])).toBeNull();
  });

  it("simplifies polygons based on tolerance", () => {
    const points = [
      { x: 0, y: 0 },
      { x: 0.2, y: 0.05 },
      { x: 1, y: 0 },
      { x: 1, y: 1 },
      { x: 0, y: 1 },
    ];
    expect(simplifyPolygon(points, 0.02)).toHaveLength(5);
    const simplified = simplifyPolygon(points, 0.15);
    expect(simplified).toHaveLength(4);
    expect(validatePolygon(simplified)).toBeNull();
  });

  it("returns the original polygon when simplification degenerates", () => {
    const degenerate = [
      { x: 0, y: 0 },
      { x: 1, y: 0 },
      { x: 2, y: 0 },
      { x: 3, y: 0 },
      { x: 4, y: 0 },
    ];
    expect(simplifyPolygon(degenerate, 10)).toEqual(degenerate);
    expect(simplifyPolygon(degenerate.slice(0, 3))).toEqual(degenerate.slice(0, 3));
  });
});
