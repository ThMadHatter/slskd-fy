import { create } from 'zustand';
import { DownloadItem } from '../types';

interface DownloadState {
  queue: DownloadItem[];
  activeCount: number;
  totalSpeed: number;
  pollInterval: number;
  cancelledIds: string[];

  setQueue: (queue: DownloadItem[]) => void;
  fetchQueue: () => Promise<void>;
  addDownload: (item: Omit<DownloadItem, 'id' | 'bytesTransferred' | 'progress' | 'speed' | 'eta'>) => void;
  pauseDownload: (id: string) => void;
  resumeDownload: (id: string) => void;
  cancelDownload: (id: string, username?: string) => Promise<void>;
  retryDownload: (id: string) => void;
  pauseAll: () => void;
  resumeAll: () => void;
  clearCompleted: () => void;
}

export const useDownloadStore = create<DownloadState>((set, get) => ({
  queue: [],
  activeCount: 0,
  totalSpeed: 0,
  pollInterval: 3000,
  cancelledIds: [],

  setQueue: (queue) => set({ queue }),

  fetchQueue: async () => {
    try {
      const response = await fetch('/api/transfers');
      if (!response.ok) {
        throw new Error(`Server returned status ${response.status}`);
      }

      const data = await response.json();

      const mappedQueue: DownloadItem[] = data.flatMap((userDl: any) => {
        const username = userDl.username;
        const dirs = userDl.directories || [];
        const files = userDl.files || [];

        const mapFileStatus = (f: any): 'completed' | 'downloading' | 'failed' | 'queued' => {
          const rawState = (f.state || f.State || '').toString().toLowerCase();
          if (rawState.includes('succeeded') || rawState === 'completed' || rawState.includes('complete')) {
            return 'completed';
          }
          if (rawState.includes('downloading') || rawState.includes('inprogress') || rawState.includes('in_progress') || rawState.includes('initializing')) {
            return 'downloading';
          }
          if (rawState.includes('failed') || rawState.includes('errored') || rawState.includes('cancelled') || rawState.includes('rejected') || rawState.includes('aborted')) {
            return 'failed';
          }
          return 'queued';
        };

        const dirFiles = dirs.flatMap((d: any) => (d.files || []).map((f: any) => {
          const status = mapFileStatus(f);
          return {
            id: f.id || `${username}-${f.filename}`,
            filename: f.filename,
            username: username,
            status,
            size: f.size || 0,
            bytesTransferred: f.bytesTransferred || 0,
            speed: f.speed || 0,
            eta: f.eta || 0,
            progress: f.percentComplete || (status === 'completed' ? 100 : 0),
          };
        }));

        const flatFiles = files.map((f: any) => {
          const status = mapFileStatus(f);
          return {
            id: f.id || `${username}-${f.filename}`,
            filename: f.filename,
            username: username,
            status,
            size: f.size || 0,
            bytesTransferred: f.bytesTransferred || 0,
            speed: f.speed || 0,
            eta: f.eta || 0,
            progress: f.percentComplete || (status === 'completed' ? 100 : 0),
          };
        });

        return [...dirFiles, ...flatFiles];
      });

      // Filter out any recently cancelled IDs to ensure optimistic update integrity
      const { cancelledIds } = get();
      const filteredMapped = mappedQueue.filter(item => !cancelledIds.includes(item.id));

      set({
        queue: filteredMapped,
        activeCount: filteredMapped.filter(item => item.status === 'downloading').length,
        totalSpeed: filteredMapped.reduce((acc, item) => acc + item.speed, 0),
        pollInterval: 3000, // Reset backoff on success
      });
    } catch (err) {
      console.error('Fetch transfers failed. Applying network backoff...', err);
      // Double the interval up to 30 seconds
      set((state) => ({
        pollInterval: Math.min(state.pollInterval * 2, 30000)
      }));
    }
  },

  addDownload: (item) => set((state) => {
    const newItem: DownloadItem = {
      ...item,
      id: `dl-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      bytesTransferred: 0,
      progress: 0,
      speed: 0,
      eta: 0,
    };
    return { queue: [newItem, ...state.queue] };
  }),

  pauseDownload: (id) => set((state) => ({
    queue: state.queue.map((dl) => dl.id === id ? { ...dl, status: 'queued', speed: 0, eta: 0 } : dl)
  })),

  resumeDownload: (id) => set((state) => ({
    queue: state.queue.map((dl) => dl.id === id ? { ...dl, status: 'downloading', speed: 1.5 * 1024 * 1024, eta: 60 } : dl)
  })),

  cancelDownload: async (id: string, username?: string) => {
    // 1. Instantly perform optimistic update & register cancelled ID to prevent poll race conditions
    set((state) => ({
      queue: state.queue.filter((dl) => dl.id !== id),
      cancelledIds: [...state.cancelledIds, id]
    }));

    // 2. Perform background delete request
    try {
      if (username) {
        await fetch(`/api/transfers/${encodeURIComponent(username)}/${encodeURIComponent(id)}`, {
          method: 'DELETE',
        });
      }
    } catch (err) {
      console.error('Failed to cancel download on backend:', err);
    }
  },

  retryDownload: (id) => set((state) => ({
    queue: state.queue.map((dl) => dl.id === id ? { ...dl, status: 'downloading', speed: 1.2 * 1024 * 1024, eta: 90, progress: 0, bytesTransferred: 0 } : dl)
  })),

  pauseAll: () => set((state) => ({
    queue: state.queue.map((dl) => dl.status === 'downloading' ? { ...dl, status: 'queued', speed: 0, eta: 0 } : dl)
  })),

  resumeAll: () => set((state) => ({
    queue: state.queue.map((dl) => dl.status === 'queued' ? { ...dl, status: 'downloading', speed: 1.2 * 1024 * 1024, eta: 120 } : dl)
  })),

  clearCompleted: () => set((state) => ({
    queue: state.queue.filter((dl) => dl.status !== 'completed')
  })),
}));
