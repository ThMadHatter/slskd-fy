import { create } from 'zustand';

export type TabType = 'home' | 'explore' | 'search' | 'downloads' | 'settings';

interface NavigationState {
  activeTab: TabType;
  commandPaletteOpen: boolean;
  mobileMenuOpen: boolean;
  setActiveTab: (tab: TabType) => void;
  setCommandPaletteOpen: (open: boolean) => void;
  setMobileMenuOpen: (open: boolean) => void;
  toggleCommandPalette: () => void;
  toggleMobileMenu: () => void;
}

export const useNavigationStore = create<NavigationState>((set) => ({
  activeTab: 'home',
  commandPaletteOpen: false,
  mobileMenuOpen: false,
  setActiveTab: (tab) => set({ activeTab: tab, mobileMenuOpen: false }), // Auto-close menu on navigate
  setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),
  setMobileMenuOpen: (open) => set({ mobileMenuOpen: open }),
  toggleCommandPalette: () => set((state) => ({ commandPaletteOpen: !state.commandPaletteOpen })),
  toggleMobileMenu: () => set((state) => ({ mobileMenuOpen: !state.mobileMenuOpen })),
}));
