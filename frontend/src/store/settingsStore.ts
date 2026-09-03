import { create } from 'zustand';

interface SettingsState {
  slskdUrl: string;
  slskdKey: string;
  searchTimeoutSec: number;
  waitUntilComplete: boolean;
  navidromeUrl: string;
  navidromeUser: string;
  navidromePass: string;
  lastfmKey: string;
  lastfmSecret: string;
  beetsPath: string;
  minScoreThreshold: number;

  updateSettings: (updates: Partial<Omit<SettingsState, 'updateSettings'>>) => void;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  slskdUrl: 'http://localhost:5030/api/v0',
  slskdKey: 'your_slskd_api_key_here',
  searchTimeoutSec: 15,
  waitUntilComplete: false,
  navidromeUrl: 'http://localhost:4533',
  navidromeUser: 'admin',
  navidromePass: 'navidrome_admin_password',
  lastfmKey: 'lastfm_api_key',
  lastfmSecret: 'lastfm_secret',
  beetsPath: '/mnt/music/Music',
  minScoreThreshold: 85,

  updateSettings: (updates) => set((state) => ({ ...state, ...updates })),
}));
