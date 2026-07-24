import { create } from 'zustand';
import { DownloadItem } from '../types';

interface DownloadState {
  queue: DownloadItem[];
  activeCount: number;
  totalSpeed: number;

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

const mockDownloads: DownloadItem[] = [
  {
    id: 'dl-1',
    filename: 'Aphex Twin - Selected Ambient Works 85-92 [FLAC].zip',
    username: 'user_analog',
    status: 'downloading',
    size: 412 * 1024 * 1024,
    bytesTransferred: 412 * 1024 * 1024 * 0.68,
    speed: 2.4 * 1024 * 1024,
    eta: 134,
    progress: 68,
  },
  {
    id: 'dl-2',
    filename: 'Burial - Untrue (2007) [320kbps].rar',
    username: 'ambient_drone',
    status: 'downloading',
    size: 104 * 1024 * 1024,
    bytesTransferred: 104 * 1024 * 1024 * 0.12,
    speed: 1.1 * 1024 * 1024,
    eta: 285,
    progress: 12,
  },
  {
    id: 'dl-3',
    filename: 'Boards of Canada - Geogaddi.zip',
    username: 'fast_leecher',
    status: 'queued',
    size: 250 * 1024 * 1024,
    bytesTransferred: 0,
    speed: 0,
    eta: 0,
    progress: 0,
  },
  {
    id: 'dl-4',
    filename: 'Autechre - Tri Repetae.rar',
    username: 'archive_bot',
    status: 'queued',
    size: 180 * 1024 * 1024,
    bytesTransferred: 0,
    speed: 0,
    eta: 0,
    progress: 0,
  },
  {
    id: 'dl-5',
    filename: 'Massive Attack - Mezzanine (FLAC).zip',
    username: 'user_analog',
    status: 'completed',
    size: 385 * 1024 * 1024,
    bytesTransferred: 385 * 1024 * 1024,
    speed: 0,
    eta: 0,
    progress: 100,
  },
  {
    id: 'dl-6',
    filename: 'Various Artists - 90s Jungle Classics.rar',
    username: 'ambient_drone',
    status: 'failed',
    size: 450 * 1024 * 1024,
    bytesTransferred: 45 * 1024 * 1024,
    speed: 0,
    eta: 0,
    progress: 10,
  }
];

export const useDownloadStore = create<DownloadState>((set) => ({
  queue: mockDownloads,
  activeCount: 4,
  totalSpeed: 3.5 * 1024 * 1024,

  setQueue: (queue) => set({ queue }),

  fetchQueue: async () => {
    try {
      const response = await fetch('/api/transfers');
      if (!response.ok) throw new Error('Failed to fetch transfers');
      const data = await response.json();

      const mappedQueue: DownloadItem[] = data.flatMap((userDl: any) => {
        const username = userDl.username;
        const dirs = userDl.directories || [];
        const files = userDl.files || [];

        const dirFiles = dirs.flatMap((d: any) => (d.files || []).map((f: any) => ({
          id: f.id || `${username}-${f.filename}`,
          filename: f.filename,
          username: username,
          status: (f.state === 'Completed' ? 'completed' : f.state === 'Downloading' ? 'downloading' : f.state === 'Failed' ? 'failed' : 'queued') as any,
          size: f.size || 0,
          bytesTransferred: f.bytesTransferred || 0,
          speed: f.speed || 0,
          eta: f.eta || 0,
          progress: f.percentComplete || 0,
        })));

        const flatFiles = files.map((f: any) => ({
          id: f.id || `${username}-${f.filename}`,
          filename: f.filename,
          username: username,
          status: (f.state === 'Completed' ? 'completed' : f.state === 'Downloading' ? 'downloading' : f.state === 'Failed' ? 'failed' : 'queued') as any,
          size: f.size || 0,
          bytesTransferred: f.bytesTransferred || 0,
          speed: f.speed || 0,
          eta: f.eta || 0,
          progress: f.percentComplete || 0,
        }));

        return [...dirFiles, ...flatFiles];
      });

      set({
        queue: mappedQueue.length > 0 ? mappedQueue : mockDownloads,
        activeCount: mappedQueue.filter(item => item.status === 'downloading').length || mockDownloads.filter(item => item.status === 'downloading').length,
        totalSpeed: mappedQueue.reduce((acc, item) => acc + item.speed, 0) || 3.5 * 1024 * 1024,
      });
    } catch (err) {
      console.error(err);
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
    try {
      if (username) {
        await fetch(`/api/transfers/${encodeURIComponent(username)}/${encodeURIComponent(id)}`, {
          method: 'DELETE',
        });
      }
      set((state) => ({
        queue: state.queue.filter((dl) => dl.id !== id)
      }));
    } catch (err) {
      console.error(err);
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
