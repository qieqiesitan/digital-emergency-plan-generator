import { create } from "zustand";

export interface DraftItem {
  sectionKey: string;
  planId: string;
  content: string;
  updatedAt: number;
  synced: boolean;
}

interface DraftState {
  drafts: DraftItem[];
  addDraft: (draft: Omit<DraftItem, "synced">) => void;
  removeDraft: (planId: string, sectionKey: string) => void;
  getPendingSyncDrafts: () => DraftItem[];
  markSynced: (planId: string, sectionKey: string) => void;
  getDraft: (planId: string, sectionKey: string) => DraftItem | undefined;
}

export const useDraftStore = create<DraftState>((set, get) => ({
  drafts: [],

  addDraft: (draft) =>
    set((state) => {
      const filtered = state.drafts.filter(
        (d) => !(d.planId === draft.planId && d.sectionKey === draft.sectionKey)
      );
      return { drafts: [...filtered, { ...draft, synced: false }] };
    }),

  removeDraft: (planId, sectionKey) =>
    set((state) => ({
      drafts: state.drafts.filter(
        (d) => !(d.planId === planId && d.sectionKey === sectionKey)
      ),
    })),

  getPendingSyncDrafts: () => get().drafts.filter((d) => !d.synced),

  markSynced: (planId, sectionKey) =>
    set((state) => ({
      drafts: state.drafts.map((d) =>
        d.planId === planId && d.sectionKey === sectionKey
          ? { ...d, synced: true }
          : d
      ),
    })),

  getDraft: (planId, sectionKey) =>
    get().drafts.find(
      (d) => d.planId === planId && d.sectionKey === sectionKey
    ),
}));
