import { create } from 'zustand';
import { ReviewQueueItem, ReviewAction, BeetsStatus } from '../types/beets';

interface ReviewQueueState {
  items: ReviewQueueItem[];
  selectedItemId: number | null;
  loading: boolean;
  scanning: boolean;
  error: string | null;
  status: BeetsStatus | null;
  fetchQueue: () => Promise<void>;
  fetchStatus: () => Promise<void>;
  scanLibrary: () => Promise<void>;
  seedTestItems: () => Promise<void>;
  selectItem: (id: number) => void;
  selectNext: () => void;
  selectPrev: () => void;
  resolveAction: (itemId: number, action: ReviewAction, candidateId?: string) => Promise<void>;
}

export const useReviewQueueStore = create<ReviewQueueState>((set, get) => ({
  items: [],
  selectedItemId: null,
  loading: false,
  scanning: false,
  error: null,
  status: null,

  fetchQueue: async () => {
    set({ loading: true, error: null });
    try {
      const res = await fetch('/api/beets/review-queue');
      if (res.ok) {
        const data: ReviewQueueItem[] = await res.json();
        set({ items: data, loading: false });
        if (data.length > 0 && get().selectedItemId === null) {
          set({ selectedItemId: data[0].id });
        }
      } else {
        set({ loading: false, error: 'Failed to fetch review queue' });
      }
    } catch (err: any) {
      set({ loading: false, error: err?.message || 'Network error fetching review queue' });
    }
  },

  fetchStatus: async () => {
    try {
      const res = await fetch('/api/beets/status');
      if (res.ok) {
        const data: BeetsStatus = await res.json();
        set({ status: data });
      }
    } catch (err) {
      // Non-critical
    }
  },

  scanLibrary: async () => {
    set({ scanning: true });
    try {
      await fetch('/api/beets/scan-library', { method: 'POST' });
      await get().fetchQueue();
      await get().fetchStatus();
    } catch (err) {
      // Non-critical
    } finally {
      set({ scanning: false });
    }
  },

  seedTestItems: async () => {
    set({ loading: true });
    try {
      await fetch('/api/beets/seed-test-items', { method: 'POST' });
      await get().fetchQueue();
      await get().fetchStatus();
    } catch (err) {
      // Non-critical
    } finally {
      set({ loading: false });
    }
  },

  selectItem: (id: number) => {
    set({ selectedItemId: id });
  },

  selectNext: () => {
    const { items, selectedItemId } = get();
    if (items.length === 0) return;
    const currentIndex = items.findIndex((i) => i.id === selectedItemId);
    if (currentIndex < items.length - 1) {
      set({ selectedItemId: items[currentIndex + 1].id });
    }
  },

  selectPrev: () => {
    const { items, selectedItemId } = get();
    if (items.length === 0) return;
    const currentIndex = items.findIndex((i) => i.id === selectedItemId);
    if (currentIndex > 0) {
      set({ selectedItemId: items[currentIndex - 1].id });
    }
  },

  resolveAction: async (itemId: number, action: ReviewAction, candidateId?: string) => {
    const previousItems = get().items;
    const filteredItems = previousItems.filter((i) => i.id !== itemId);

    const currentIdx = previousItems.findIndex((i) => i.id === itemId);
    const nextItem = filteredItems[currentIdx] || filteredItems[currentIdx - 1] || null;

    set({
      items: filteredItems,
      selectedItemId: nextItem ? nextItem.id : null,
    });

    try {
      const res = await fetch(`/api/beets/review-queue/${itemId}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, candidate_id: candidateId }),
      });
      if (!res.ok) {
        set({ items: previousItems, selectedItemId: itemId });
      } else {
        await get().fetchStatus();
      }
    } catch (err) {
      set({ items: previousItems, selectedItemId: itemId });
    }
  },
}));
