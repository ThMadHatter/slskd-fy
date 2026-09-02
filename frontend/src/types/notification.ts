export type NotificationType =
  | 'review_required'
  | 'import_completed'
  | 'import_failed'
  | 'download_completed';

export interface NotificationItem {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  timestamp: string; // ISO string or formatted timestamp
  read: boolean;
  metadata?: {
    filename?: string;
    artist?: string;
    track?: string;
    itemId?: number | string;
    [key: string]: any;
  };
}
