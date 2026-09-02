'use client';

import React from 'react';
import { useNotificationStore } from '../store/notificationStore';
import { useNavigationStore } from '../store/navigationStore';
import { NotificationType } from '../types/notification';
import {
  X,
  Bell,
  Check,
  Trash2,
  CheckCircle2,
  AlertCircle,
  XCircle,
  Download,
  ChevronRight,
} from 'lucide-react';

function getNotificationIcon(type: NotificationType) {
  switch (type) {
    case 'review_required':
      return <AlertCircle size={18} className="text-[#FC7C78] shrink-0" />;
    case 'import_completed':
      return <CheckCircle2 size={18} className="text-[#10B981] shrink-0" />;
    case 'import_failed':
      return <XCircle size={18} className="text-[#FC7C78] shrink-0" />;
    case 'download_completed':
      return <Download size={18} className="text-[#10B981] shrink-0" />;
    default:
      return <Bell size={18} className="text-[#10B981] shrink-0" />;
  }
}

function formatRelativeTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffSec = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diffSec < 60) return 'Just now';
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    return `${Math.floor(diffSec / 86400)}d ago`;
  } catch {
    return '';
  }
}

export default function NotificationDrawer() {
  const {
    notifications,
    isDrawerOpen,
    setDrawerOpen,
    markAsRead,
    markAllAsRead,
    clearAll,
    removeNotification,
  } = useNotificationStore();

  const { setActiveTab } = useNavigationStore();

  if (!isDrawerOpen) return null;

  const unreadCount = notifications.filter((n) => !n.read).length;

  const handleNotificationClick = (id: string, type: NotificationType) => {
    markAsRead(id);
    setDrawerOpen(false);

    if (type === 'review_required') {
      setActiveTab('review');
    } else if (
      type === 'download_completed' ||
      type === 'import_completed' ||
      type === 'import_failed'
    ) {
      setActiveTab('downloads');
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden flex justify-end bg-black/60 backdrop-blur-xs animate-fade-in">
      {/* Backdrop click to close */}
      <div
        className="absolute inset-0"
        onClick={() => setDrawerOpen(false)}
        aria-hidden="true"
      />

      {/* Drawer Panel */}
      <div className="relative w-full max-w-md bg-[#0A0A0B] border-l border-[#27272A] shadow-2xl h-full flex flex-col z-10 text-[#E4E4E7]">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[#27272A] bg-[#141417]">
          <div className="flex items-center gap-2">
            <Bell size={18} className="text-[#10B981]" />
            <h2 className="font-heading font-semibold text-base text-[#E4E4E7]">
              Notifications
            </h2>
            {unreadCount > 0 && (
              <span className="bg-[#10B981]/20 border border-[#10B981]/40 text-[#10B981] font-data-mono text-[11px] px-2 py-0.5 rounded-full font-medium">
                {unreadCount} new
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {unreadCount > 0 && (
              <button
                onClick={markAllAsRead}
                title="Mark all as read"
                className="p-1.5 text-[#8B8B94] hover:text-[#10B981] transition-colors rounded hover:bg-[#27272A] cursor-pointer"
              >
                <Check size={16} />
              </button>
            )}

            {notifications.length > 0 && (
              <button
                onClick={clearAll}
                title="Clear notification history"
                className="p-1.5 text-[#8B8B94] hover:text-[#FC7C78] transition-colors rounded hover:bg-[#27272A] cursor-pointer"
              >
                <Trash2 size={16} />
              </button>
            )}

            <button
              onClick={() => setDrawerOpen(false)}
              className="p-1.5 text-[#8B8B94] hover:text-[#E4E4E7] transition-colors rounded hover:bg-[#27272A] cursor-pointer"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Notifications History List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2 divide-y divide-[#1f1f23]/60">
          {notifications.length === 0 ? (
            <div className="h-64 flex flex-col items-center justify-center text-center p-6 text-[#63636C]">
              <Bell size={32} className="mb-3 opacity-40" />
              <p className="font-body-md text-sm font-medium">No notifications yet</p>
              <p className="font-body-sm text-xs mt-1 text-[#63636C]">
                Alerts for downloads, imports, and review tasks will appear here.
              </p>
            </div>
          ) : (
            notifications.map((n) => (
              <div
                key={n.id}
                onClick={() => handleNotificationClick(n.id, n.type)}
                className={`pt-2.5 pb-2 px-3 rounded-lg transition-colors cursor-pointer group flex items-start gap-3 ${
                  n.read
                    ? 'bg-transparent hover:bg-[#141417]/80 opacity-75'
                    : 'bg-[#18181B] border border-[#27272A] hover:border-[#10B981]/50'
                }`}
              >
                <div className="pt-0.5">{getNotificationIcon(n.type)}</div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <h4
                      className={`text-xs font-medium truncate ${
                        n.read ? 'text-[#8B8B94]' : 'text-[#E4E4E7] font-semibold'
                      }`}
                    >
                      {n.title}
                    </h4>
                    <span className="font-data-mono text-[10px] text-[#63636C] shrink-0">
                      {formatRelativeTime(n.timestamp)}
                    </span>
                  </div>

                  <p className="text-xs text-[#8B8B94] mt-1 leading-relaxed line-clamp-2">
                    {n.message}
                  </p>

                  {n.metadata?.filename && (
                    <div className="mt-1.5 font-data-mono text-[10px] text-[#10B981]/80 truncate bg-[#0A0A0B] px-2 py-0.5 rounded border border-[#27272A]">
                      {n.metadata.filename}
                    </div>
                  )}
                </div>

                <div className="flex flex-col items-end gap-1 shrink-0 pt-0.5">
                  {!n.read && (
                    <span
                      className="w-2 h-2 rounded-full bg-[#10B981] shadow-[0_0_6px_#10B981]"
                      title="Unread"
                    />
                  )}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      removeNotification(n.id);
                    }}
                    className="opacity-0 group-hover:opacity-100 text-[#63636C] hover:text-[#FC7C78] transition-opacity p-0.5 cursor-pointer"
                    title="Remove notification"
                  >
                    <X size={12} />
                  </button>
                  <ChevronRight size={14} className="text-[#63636C] group-hover:text-[#10B981] transition-colors mt-auto" />
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer Actions */}
        {notifications.length > 0 && (
          <div className="p-3 border-t border-[#27272A] bg-[#141417] flex items-center justify-between text-xs text-[#8B8B94]">
            <span>{notifications.length} total notifications</span>
            {unreadCount > 0 && (
              <button
                onClick={markAllAsRead}
                className="text-[#10B981] hover:underline cursor-pointer font-medium"
              >
                Mark all as read
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
