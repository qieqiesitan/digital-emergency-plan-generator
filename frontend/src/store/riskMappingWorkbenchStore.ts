import { create } from "zustand";
import type {
  WorkbenchZone,
  PendingRegion,
  RiskCanvasText,
  EnterpriseFloor,
} from "@/types/riskMappingWorkbench";
import type { RiskObject } from "@/types/riskManagement";

export interface WorkbenchDomainState {
  floors: EnterpriseFloor[];
  currentFloorId: string;
  zones: WorkbenchZone[];
  riskPoints: RiskObject[];
  texts: RiskCanvasText[];
  pendingRegions: PendingRegion[];
  deletedZoneIds: string[];
  deletedRiskPointIds: string[];
}

interface WorkbenchState extends WorkbenchDomainState {
  selectedZoneId: string | null;
  selectedRegionId: string | null;
  selectedRiskPointId: string | null;
  selectedTextId: string | null;
  viewScale: number;
  viewX: number;
  viewY: number;
  tool: "select" | "rect" | "circle" | "polygon" | "pen" | "freehand" | "risk-point" | "text";
  gridEnabled: boolean;
  snapEnabled: boolean;
  guideEnabled: boolean;
  dirty: boolean;
  savedFingerprint: string | null;
  past: WorkbenchDomainState[];
  future: WorkbenchDomainState[];
  setSnapshot: (data: Partial<WorkbenchDomainState>) => void;
  commit: () => void;
  markSaved: () => void;
  zoomBy: (factor: number) => void;
  resetView: () => void;
  deleteZone: (zoneId: string) => void;
  deleteRiskPoint: (pointId: string) => void;
  deletePendingRegion: (regionId: string) => void;
  deleteZonePolygon: (zoneId: string, polygonId: string) => void;
  deleteText: (textId: string) => void;
  deleteSelected: () => void;
  reset: () => void;
}

const initial = {
  floors: [],
  currentFloorId: "",
  zones: [],
  riskPoints: [],
  texts: [],
  pendingRegions: [],
  deletedZoneIds: [],
  deletedRiskPointIds: [],
  selectedZoneId: null,
  selectedRegionId: null,
  selectedRiskPointId: null,
  selectedTextId: null,
  viewScale: 1,
  viewX: 0,
  viewY: 0,
  tool: "select" as const,
  gridEnabled: true,
  snapEnabled: true,
  guideEnabled: true,
  dirty: false,
  savedFingerprint: null,
  past: [],
  future: [],
};

const snapshotOf = (state: WorkbenchDomainState): WorkbenchDomainState => ({
  floors: state.floors,
  currentFloorId: state.currentFloorId,
  zones: state.zones,
  riskPoints: state.riskPoints,
  texts: state.texts,
  pendingRegions: state.pendingRegions,
  deletedZoneIds: state.deletedZoneIds,
  deletedRiskPointIds: state.deletedRiskPointIds,
});

const canonicalize = (value: unknown): unknown => {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value !== null && typeof value === "object") {
    return Object.keys(value as Record<string, unknown>)
      .sort()
      .reduce<Record<string, unknown>>((acc, key) => {
        acc[key] = canonicalize((value as Record<string, unknown>)[key]);
        return acc;
      }, {});
  }
  return value;
};

const fingerprintOf = (state: WorkbenchDomainState) => JSON.stringify(canonicalize(snapshotOf(state)));

export const useRiskMappingWorkbenchStore = create<WorkbenchState>((set, get) => ({
  ...initial,
  setSnapshot: (data) => set({ ...data }),
  commit: () => {
    const state = get();
    set({ past: [...state.past.slice(-49), snapshotOf(state)], future: [], dirty: true });
  },
  zoomBy: (factor) => {
    const state = get();
    set({ viewScale: Math.min(4, Math.max(0.25, state.viewScale * factor)) });
  },
  resetView: () => set({ viewScale: 1, viewX: 0, viewY: 0 }),
  markSaved: () => {
    const state = get();
    set({ dirty: false, savedFingerprint: fingerprintOf(state), past: [], future: [] });
  },
  deleteZone: (zoneId) => {
    const state = get();
    if (!state.zones.some(z => z.id === zoneId)) return;
    const isPersisted = !zoneId.startsWith("new-zone-");
    const orphanPoints = state.riskPoints.filter(p => p.zone_id === zoneId);
    const deletedRiskPointIds = isPersisted
      ? [...state.deletedRiskPointIds, ...orphanPoints.filter(p => !p.id.startsWith("new-point-")).map(p => p.id)]
      : state.deletedRiskPointIds;
    set({
      zones: state.zones.filter(z => z.id !== zoneId),
      riskPoints: state.riskPoints.filter(p => p.zone_id !== zoneId),
      selectedZoneId: state.selectedZoneId === zoneId ? null : state.selectedZoneId,
      selectedRiskPointId: state.riskPoints.some(p => p.zone_id === zoneId && p.id === state.selectedRiskPointId)
        ? null
        : state.selectedRiskPointId,
      selectedRegionId: state.selectedRegionId?.startsWith(`zone:${zoneId}:`)
        ? null
        : state.selectedRegionId,
      deletedZoneIds: isPersisted
        ? [...state.deletedZoneIds, zoneId]
        : state.deletedZoneIds,
      deletedRiskPointIds,
    });
  },
  deleteRiskPoint: (pointId) => {
    const state = get();
    if (!state.riskPoints.some(p => p.id === pointId)) return;
    const isPersisted = !pointId.startsWith("new-point-");
    set({
      riskPoints: state.riskPoints.filter(p => p.id !== pointId),
      deletedRiskPointIds: isPersisted
        ? [...state.deletedRiskPointIds, pointId]
        : state.deletedRiskPointIds,
      selectedRiskPointId: state.selectedRiskPointId === pointId ? null : state.selectedRiskPointId,
    });
  },
  deletePendingRegion: (regionId) => {
    const state = get();
    set({
      pendingRegions: state.pendingRegions.filter(r => r.id !== regionId),
      selectedRegionId: state.selectedRegionId === `pending:${regionId}` ? null : state.selectedRegionId,
    });
  },
  deleteZonePolygon: (zoneId, polygonId) => {
    const state = get();
    set({
      zones: state.zones.map(z => {
        if (z.id !== zoneId || !z.floor_plan_polygon) return z;
        return {
          ...z,
          floor_plan_polygon: {
            ...z.floor_plan_polygon,
            polygons: z.floor_plan_polygon.polygons.filter(p => p.id !== polygonId),
          },
        };
      }),
      selectedRegionId: state.selectedRegionId === `zone:${zoneId}:${polygonId}` ? null : state.selectedRegionId,
    });
  },
  deleteText: (textId) => {
    const state = get();
    set({
      texts: state.texts.filter(t => t.id !== textId),
      selectedTextId: state.selectedTextId === textId ? null : state.selectedTextId,
    });
  },
  deleteSelected: () => {
    const state = get();
    if (!state.selectedRegionId && !state.selectedRiskPointId && !state.selectedTextId) return;
    state.commit();
    const current = get();
    if (current.selectedRegionId?.startsWith("pending:")) {
      current.deletePendingRegion(current.selectedRegionId.slice("pending:".length));
      return;
    }
    if (current.selectedRegionId?.startsWith("zone:")) {
      const body = current.selectedRegionId.slice("zone:".length);
      const separator = body.indexOf(":");
      const zoneId = body.slice(0, separator);
      const polygonId = body.slice(separator + 1);
      current.deleteZonePolygon(zoneId, polygonId);
      return;
    }
    if (current.selectedRiskPointId) {
      current.deleteRiskPoint(current.selectedRiskPointId);
      return;
    }
    if (current.selectedTextId) {
      current.deleteText(current.selectedTextId);
    }
  },
  reset: () => set({ ...initial }),
}));

export const undo = () => useRiskMappingWorkbenchStore.setState(state => {
  if (!state.past.length) return state;
  const previous = state.past[state.past.length - 1];
  const restored = {
    ...previous,
    selectedZoneId: state.selectedZoneId,
    selectedRegionId: state.selectedRegionId,
    selectedRiskPointId: state.selectedRiskPointId,
    selectedTextId: state.selectedTextId,
    tool: state.tool,
    gridEnabled: state.gridEnabled,
    snapEnabled: state.snapEnabled,
    guideEnabled: state.guideEnabled,
    viewScale: state.viewScale,
    viewX: state.viewX,
    viewY: state.viewY,
  };
  return {
    ...restored,
    past: state.past.slice(0, -1),
    future: [snapshotOf(state), ...state.future],
    dirty: state.savedFingerprint === null || fingerprintOf(restored) !== state.savedFingerprint,
  };
});

export const redo = () => useRiskMappingWorkbenchStore.setState(state => {
  if (!state.future.length) return state;
  const next = state.future[0];
  const restored = {
    ...next,
    selectedZoneId: state.selectedZoneId,
    selectedRegionId: state.selectedRegionId,
    selectedRiskPointId: state.selectedRiskPointId,
    selectedTextId: state.selectedTextId,
    tool: state.tool,
    gridEnabled: state.gridEnabled,
    snapEnabled: state.snapEnabled,
    guideEnabled: state.guideEnabled,
    viewScale: state.viewScale,
    viewX: state.viewX,
    viewY: state.viewY,
  };
  return {
    ...restored,
    past: [...state.past, snapshotOf(state)],
    future: state.future.slice(1),
    dirty: state.savedFingerprint === null || fingerprintOf(restored) !== state.savedFingerprint,
  };
});
