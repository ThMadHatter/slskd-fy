import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { NotificationItem, NotificationType } from '../types/notification';

interface NotificationState {
  notifications: NotificationItem[];
  isDrawerOpen: boolean;

  // Actions
  addNotification: (notification: Omit<NotificationItem, 'id' | 'timestamp' | 'read'>) => void;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  removeNotification: (id: string) => void;
  clearAll: () => void;
  toggleDrawer: () => void;
  setDrawerOpen: (open: boolean) => void;
}

export const useNotificationStore = create<NotificationState>()(
  persist(
    (set, get) => ({
      notifications: [],
      isDrawerOpen: false,

      addNotification: (item) => {
        const newNotification: NotificationItem = {
          ...item,
          id: `notif-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
          timestamp: new Date().toISOString(),
          read: false,
        };

        // Prepend new notification, cap history at 100 entries
        set((state) => ({
          notifications: [newNotification, ...state.notifications].slice(0, 100),
        }));
      },

      markAsRead: (id: string) => {
        set((state) => ({
          notifications: state.notifications.map((n) =>
            n.id === id ? { ...n, read: true } : n
          ),
        }));
      },

      markAllAsRead: () => {
        set((state) => ({
          notifications: state.notifications.map((n) => ({ ...n, read: true })),
        }));
      },

      removeNotification: (id: string) => {
        set((state) => ({
          notifications: state.notifications.filter((n) => n.id !== id),
        }));
      },

      clearAll: () => {
        set({ notifications: [] });
      },

      toggleDrawer: () => {
        set((state) => ({ isDrawerOpen: !state.isDrawerOpen }));
      },

      setDrawerOpen: (open: boolean) => {
        set({ isDrawerOpen: open });
      },
    }),
    {
      name: 'sonic_notifications_v1',
      // Persist only notifications array, not ephemeral UI state like isDrawerOpen
      partialize: (state) => ({ notifications: state.notifications }),
    }
  )
);
