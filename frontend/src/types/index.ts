export interface SlskdResult {
  filename: string;
  size: number;
  username: string;
  format: string;
  bitrate?: number;
  sample_rate?: number;
  queue_length: number;
  score?: number;
  parsed_artist?: string;
  parsed_track?: string;
  parsed_album?: string;
  parsed_year?: number;
  beets_confidence?: boolean;
}

export interface SearchQuery {
  artist: string;
  track: string;
  album?: string;
  mode: 'A' | 'B' | 'C';
}

export type DownloadStatus = 'downloading' | 'queued' | 'completed' | 'failed';

export interface DownloadItem {
  id: string;
  filename: string;
  username: string;
  status: DownloadStatus;
  size: number;
  bytesTransferred: number;
  speed: number;
  eta: number;
  progress: number;
}

export interface AutocompleteItem {
  id: string;
  name: string;
  type: 'artist' | 'album' | 'track';
  score?: number;
}
