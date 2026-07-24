import { create } from 'zustand';
import { SlskdResult } from '../types';

interface SearchFilters {
  format: { flac: boolean; mp3: boolean; wav: boolean };
  bitrate: 'All' | 'Lossless' | '320kbps' | 'V0 (VBR)' | '256kbps';
  maxSize: number;
  queueLength: 'any' | 'empty' | 'under5';
  username: string;
}

interface SearchState {
  artist: string;
  track: string;
  searchMode: 'A' | 'B' | 'C';
  results: SlskdResult[];
  isSearching: boolean;
  selectedFilenames: string[];
  filters: SearchFilters;

  setArtist: (artist: string) => void;
  setTrack: (track: string) => void;
  setSearchMode: (mode: 'A' | 'B' | 'C') => void;
  setResults: (results: SlskdResult[]) => void;
  setIsSearching: (isSearching: boolean) => void;
  toggleSelectedFilename: (filename: string) => void;
  setSelectedFilenames: (filenames: string[]) => void;
  clearSelection: () => void;
  updateFilters: (updates: Partial<SearchFilters>) => void;
  toggleFormatFilter: (format: 'flac' | 'mp3' | 'wav') => void;
  clearFilters: () => void;
}

const defaultFilters: SearchFilters = {
  format: { flac: true, mp3: true, wav: false },
  bitrate: 'All',
  maxSize: 100,
  queueLength: 'any',
  username: '',
};

export const useSearchStore = create<SearchState>((set) => ({
  artist: '',
  track: '',
  searchMode: 'A',
  results: [],
  isSearching: false,
  selectedFilenames: [],
  filters: { ...defaultFilters },

  setArtist: (artist) => set({ artist }),
  setTrack: (track) => set({ track }),
  setSearchMode: (searchMode) => set({ searchMode }),
  setResults: (results) => set({ results }),
  setIsSearching: (isSearching) => set({ isSearching }),

  toggleSelectedFilename: (filename) => set((state) => {
    const isSelected = state.selectedFilenames.includes(filename);
    const selectedFilenames = isSelected
      ? state.selectedFilenames.filter((f) => f !== filename)
      : [...state.selectedFilenames, filename];
    return { selectedFilenames };
  }),
  setSelectedFilenames: (selectedFilenames) => set({ selectedFilenames }),
  clearSelection: () => set({ selectedFilenames: [] }),
  updateFilters: (updates) => set((state) => ({
    filters: { ...state.filters, ...updates }
  })),
  toggleFormatFilter: (format) => set((state) => ({
    filters: {
      ...state.filters,
      format: {
        ...state.filters.format,
        [format]: !state.filters.format[format],
      },
    }
  })),
  clearFilters: () => set({ filters: { ...defaultFilters } }),
}));
