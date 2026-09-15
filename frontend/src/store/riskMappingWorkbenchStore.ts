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
  selectedRegionIds: string[];
  selectedRiskPointId: string | null;
  selectedTextId: string | null;
  viewScale: number;
  viewX: number;
  viewY: number;
  tool: "select" | "rect" | "circle" | "polygon" | "pen" | "freehand" | "risk-point" | "text";
  gridEnabled: boolean;
  snapEnabled: boolean;
  guideEnabled: boolean;
  showFloorPlan: boolean;
  dirty: boolean;
  savedFingerprint: string | null;
  past: WorkbenchDomainState[];
  future: WorkbenchDomainState[];
  setSnapshot: (data: Partial<WorkbenchDomainState>) => void;
  setSelectedRegions: (ids: string[], options?: { append?: boolean }) => void;
  toggleRegionSelection: (id: string) => void;
  deleteSelectedRegions: () => void;
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
  selectedRegionIds: [],
  selectedRiskPointId: null,
  selectedTextId: null,
  viewScale: 1,
  viewX: 0,
  viewY: 0,
  tool: "select" as const,
  gridEnabled: true,
  snapEnabled: true,
  guideEnabled: true,
  showFloorPlan: true,
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
  setSelectedRegions: (ids, options) => set(state => {
    const next = options?.append ? Array.from(new Set([...state.selectedRegionIds, ...ids])) : ids;
    return { selectedRegionIds: next, selectedRiskPointId: null, selectedTextId: null };
  }),
  toggleRegionSelection: (id) => set(state => {
    const has = state.selectedRegionIds.includes(id);
    return {
      selectedRegionIds: has ? state.selectedRegionIds.filter(x => x !== id) : [...state.selectedRegionIds, id],
      selectedRiskPointId: null,
      selectedTextId: null,
    };
  }),
  deleteSelectedRegions: () => {
    const state = get();
    if (!state.selectedRegionIds.length) return;
    state.commit();
    const current = get();
    const pendingIds = new Set<string>();
    const zonePolygons = new Map<string, Set<string>>();
    for (const id of current.selectedRegionIds) {
      if (id.startsWith("pending:")) {
        pendingIds.add(id.slice("pending:".length));
      } else if (id.startsWith("zone:")) {
        const body = id.slice("zone:".length);
        const separator = body.indexOf(":");
        const zoneId = body.slice(0, separator);
        const polygonId = body.slice(separator + 1);
        if (!zonePolygons.has(zoneId)) zonePolygons.set(zoneId, new Set());
        zonePolygons.get(zoneId)!.add(polygonId);
      }
    }
    set({
      pendingRegions: current.pendingRegions.filter(r => !pendingIds.has(r.id)),
      zones: current.zones.map(z => {
        const removing = zonePolygons.get(z.id);
        if (!removing || !z.floor_plan_polygon) return z;
        return {
          ...z,
          floor_plan_polygon: {
            ...z.floor_plan_polygon,
            polygons: z.floor_plan_polygon.polygons.filter(p => !removing.has(p.id)),
          },
        };
      }),
      selectedRegionIds: [],
    });
  },
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
      selectedRegionIds: state.selectedRegionIds.filter(id => !id.startsWith(`zone:${zoneId}:`)),
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
      selectedRegionIds: state.selectedRegionIds.filter(id => id !== `pending:${regionId}`),
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
      selectedRegionIds: state.selectedRegionIds.filter(id => id !== `zone:${zoneId}:${polygonId}`),
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
    if (!state.selectedRegionIds.length && !state.selectedRiskPointId && !state.selectedTextId) return;
    if (state.selectedRegionIds.length) {
      state.deleteSelectedRegions();
      return;
    }
    state.commit();
    const current = get();
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
    selectedRegionIds: state.selectedRegionIds,
    selectedRiskPointId: state.selectedRiskPointId,
    selectedTextId: state.selectedTextId,
    tool: state.tool,
    gridEnabled: state.gridEnabled,
    snapEnabled: state.snapEnabled,
    guideEnabled: state.guideEnabled,
    showFloorPlan: state.showFloorPlan,
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
    selectedRegionIds: state.selectedRegionIds,
    selectedRiskPointId: state.selectedRiskPointId,
    selectedTextId: state.selectedTextId,
    tool: state.tool,
    gridEnabled: state.gridEnabled,
    snapEnabled: state.snapEnabled,
    guideEnabled: state.guideEnabled,
    showFloorPlan: state.showFloorPlan,
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
