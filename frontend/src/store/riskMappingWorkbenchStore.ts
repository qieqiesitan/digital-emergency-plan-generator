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
  past: WorkbenchDomainState[];
  future: WorkbenchDomainState[];
  setSnapshot: (data: Partial<WorkbenchDomainState>) => void;
  commit: () => void;
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

export const useRiskMappingWorkbenchStore = create<WorkbenchState>((set, get) => ({
  ...initial,
  setSnapshot: (data) => set({ ...data }),
  commit: () => {
    const state = get();
    set({ past: [...state.past.slice(-49), snapshotOf(state)], future: [], dirty: true });
  },
  reset: () => set({ ...initial }),
}));

export const undo = () => useRiskMappingWorkbenchStore.setState(state => {
  if (!state.past.length) return state;
  const previous = state.past[state.past.length - 1];
  return {
    ...previous,
    selectedZoneId: state.selectedZoneId,
    selectedRegionId: state.selectedRegionId,
    tool: state.tool,
    gridEnabled: state.gridEnabled,
    snapEnabled: state.snapEnabled,
    guideEnabled: state.guideEnabled,
    past: state.past.slice(0, -1),
    future: [snapshotOf(state), ...state.future],
    dirty: true,
  };
});

export const redo = () => useRiskMappingWorkbenchStore.setState(state => {
  if (!state.future.length) return state;
  const next = state.future[0];
  return {
    ...next,
    selectedZoneId: state.selectedZoneId,
    selectedRegionId: state.selectedRegionId,
    tool: state.tool,
    gridEnabled: state.gridEnabled,
    snapEnabled: state.snapEnabled,
    guideEnabled: state.guideEnabled,
    past: [...state.past, snapshotOf(state)],
    future: state.future.slice(1),
    dirty: true,
  };
});
