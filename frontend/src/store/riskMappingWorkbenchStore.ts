import { create } from "zustand";
import type { WorkbenchZone, PendingRegion, RiskCanvasText } from "@/types/riskMappingWorkbench";
import type { RiskObject } from "@/types/riskManagement";

interface WorkbenchState {
  floors: import("@/types/riskMappingWorkbench").EnterpriseFloor[];
  currentFloorId: string;
  zones: WorkbenchZone[];
  riskPoints: RiskObject[];
  texts: RiskCanvasText[];
  pendingRegions: PendingRegion[];
  deletedZoneIds: string[];
  deletedRiskPointIds: string[];
  selectedZoneId: string | null;
  selectedRegionId: string | null;
  tool: "select" | "rect" | "polygon" | "freehand" | "risk-point" | "text";
  gridEnabled: boolean;
  snapEnabled: boolean;
  guideEnabled: boolean;
  dirty: boolean;
  past: WorkbenchState[];
  future: WorkbenchState[];
  setSnapshot: (data: Partial<WorkbenchState>) => void;
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

export const useRiskMappingWorkbenchStore = create<WorkbenchState>((set, get) => ({
  ...initial,
  setSnapshot: (data) => set({ ...data }),
  commit: () => {
    const state = get();
    set({ past: [...state.past.slice(-49), state], future: [], dirty: true });
  },
  reset: () => set({ ...initial }),
}));

export const undo = () => useRiskMappingWorkbenchStore.setState(state => {
  if (!state.past.length) return state;
  const previous = state.past[state.past.length - 1];
  return {
    ...previous,
    past: state.past.slice(0, -1),
    future: [state, ...state.future],
    dirty: true,
  };
});

export const redo = () => useRiskMappingWorkbenchStore.setState(state => {
  if (!state.future.length) return state;
  const next = state.future[0];
  return {
    ...next,
    past: [...state.past, state],
    future: state.future.slice(1),
    dirty: true,
  };
});
