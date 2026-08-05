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
  tool: "select" | "rect" | "polygon" | "freehand" | "risk-point" | "text";
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
  deleteZone: (zoneId: string) => void;
  deleteRiskPoint: (pointId: string) => void;
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
    });
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
    tool: state.tool,
    gridEnabled: state.gridEnabled,
    snapEnabled: state.snapEnabled,
    guideEnabled: state.guideEnabled,
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
    tool: state.tool,
    gridEnabled: state.gridEnabled,
    snapEnabled: state.snapEnabled,
    guideEnabled: state.guideEnabled,
  };
  return {
    ...restored,
    past: [...state.past, snapshotOf(state)],
    future: state.future.slice(1),
    dirty: state.savedFingerprint === null || fingerprintOf(restored) !== state.savedFingerprint,
  };
});
