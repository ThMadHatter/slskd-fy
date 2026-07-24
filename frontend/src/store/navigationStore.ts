import { create } from 'zustand';

export type TabType = 'home' | 'explore' | 'search' | 'downloads' | 'settings';

interface NavigationState {
  activeTab: TabType;
  commandPaletteOpen: boolean;
  setActiveTab: (tab: TabType) => void;
  setCommandPaletteOpen: (open: boolean) => void;
  toggleCommandPalette: () => void;
}

export const useNavigationStore = create<NavigationState>((set) => ({
  activeTab: 'home',
  commandPaletteOpen: false,
  setActiveTab: (tab) => set({ activeTab: tab }),
  setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),
  toggleCommandPalette: () => set((state) => ({ commandPaletteOpen: !state.commandPaletteOpen })),
}));
