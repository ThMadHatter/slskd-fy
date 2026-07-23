import { create } from 'zustand';
import { DownloadItem } from '../types';

interface DownloadState {
  queue: DownloadItem[];
  activeCount: number;
  totalSpeed: number;

  setQueue: (queue: DownloadItem[]) => void;
  addDownload: (item: Omit<DownloadItem, 'id' | 'bytesTransferred' | 'progress' | 'speed' | 'eta'>) => void;
  pauseDownload: (id: string) => void;
  resumeDownload: (id: string) => void;
  cancelDownload: (id: string) => void;
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

  cancelDownload: (id) => set((state) => ({
    queue: state.queue.filter((dl) => dl.id !== id)
  })),

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
