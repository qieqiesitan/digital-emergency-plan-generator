import { beforeEach, describe, it, expect } from "vitest";
import { useRiskMappingWorkbenchStore, undo, redo } from "./riskMappingWorkbenchStore";
import type { EnterpriseFloor, WorkbenchZone } from "@/types/riskMappingWorkbench";
import {
  toPercent,
  toCanvasX,
  toCanvasY,
  pointsToKonva,
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

describe("riskMappingWorkbenchStore", () => {
  beforeEach(() => {
    useRiskMappingWorkbenchStore.getState().reset();
  });

  it("commit marks dirty and pushes a domain-only snapshot", () => {
    const store = useRiskMappingWorkbenchStore;
    store.setState({ tool: "polygon", selectedZoneId: "z1", dirty: false });
    store.getState().setSnapshot({ zones: [makeZone("a")] });
    store.getState().commit();
    const state = store.getState();
    expect(state.dirty).toBe(true);
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
    expect(state.past[0].zones).toEqual([makeZone("a")]);
  });

  it("undo restores domain fields while preserving UI state", () => {
    const store = useRiskMappingWorkbenchStore;
    store.setState({ tool: "polygon", selectedZoneId: "z-sel", gridEnabled: false, snapEnabled: false, guideEnabled: false });
    store.getState().setSnapshot({ floors: [makeFloor("a")], currentFloorId: "a", zones: [makeZone("a")] });
    store.getState().commit();
    store.setState({ tool: "select", selectedZoneId: null, gridEnabled: true, snapEnabled: true, guideEnabled: true });
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
    expect(state.past).toHaveLength(0);
    expect(state.future).toHaveLength(1);
    expect(state.dirty).toBe(true);
  });

  it("redo replays the next domain snapshot and keeps UI state", () => {
    const store = useRiskMappingWorkbenchStore;
    store.setState({ tool: "polygon", selectedZoneId: "z-sel" });
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
    expect(state.past).toHaveLength(1);
    expect(state.future).toHaveLength(0);
  });

  it("a new commit after undo clears the future stack", () => {
    const store = useRiskMappingWorkbenchStore;
    store.getState().setSnapshot({ zones: [makeZone("a")] });
    store.getState().commit();
    store.getState().setSnapshot({ zones: [makeZone("b")] });
    undo();
    expect(store.getState().future).toHaveLength(1);

    store.getState().setSnapshot({ zones: [makeZone("c")] });
    store.getState().commit();
    expect(store.getState().future).toHaveLength(0);
    expect(store.getState().past).toHaveLength(1);
  });

  it("caps history at 50 snapshots", () => {
    const store = useRiskMappingWorkbenchStore;
    for (let i = 0; i < 60; i++) {
      store.getState().setSnapshot({ zones: [makeZone(`z${i}`)] });
      store.getState().commit();
    }
    const state = store.getState();
    expect(state.past).toHaveLength(50);
    expect(state.past[49].zones[0].id).toBe("z59");
    expect(state.future).toHaveLength(0);
  });

  it("keeps dirty true across commit, undo and redo", () => {
    const store = useRiskMappingWorkbenchStore;
    store.setState({ dirty: false });
    store.getState().setSnapshot({ zones: [makeZone("a")] });
    store.getState().commit();
    expect(store.getState().dirty).toBe(true);
    store.getState().setSnapshot({ zones: [makeZone("b")] });
    undo();
    expect(store.getState().dirty).toBe(true);
    redo();
    expect(store.getState().dirty).toBe(true);
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
