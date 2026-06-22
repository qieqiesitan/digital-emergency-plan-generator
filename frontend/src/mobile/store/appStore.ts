import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AppState {
  currentEnterpriseId: string | null;
  currentEnterpriseName: string | null;
  setCurrentEnterprise: (id: string, name: string) => void;
  clearCurrentEnterprise: () => void;

  activeTab: "dashboard" | "enterprises" | "plans" | "settings";
  setActiveTab: (tab: AppState["activeTab"]) => void;

  isOnline: boolean;
  setOnline: (online: boolean) => void;

  isKeyboardVisible: boolean;
  keyboardHeight: number;
  setKeyboard: (visible: boolean, height: number) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      currentEnterpriseId: null,
      currentEnterpriseName: null,
      setCurrentEnterprise: (id, name) =>
        set({ currentEnterpriseId: id, currentEnterpriseName: name }),
      clearCurrentEnterprise: () =>
        set({ currentEnterpriseId: null, currentEnterpriseName: null }),

      activeTab: "dashboard",
      setActiveTab: (tab) => set({ activeTab: tab }),

      isOnline: typeof navigator !== "undefined" ? navigator.onLine : true,
      setOnline: (online) => set({ isOnline: online }),

      isKeyboardVisible: false,
      keyboardHeight: 0,
      setKeyboard: (visible, height) =>
        set({ isKeyboardVisible: visible, keyboardHeight: height }),
    }),
    {
      name: "mobile-app-store",
      partialize: (state) => ({
        currentEnterpriseId: state.currentEnterpriseId,
        currentEnterpriseName: state.currentEnterpriseName,
      }),
    }
  )
);
