export type BeetsImportStatus =
  | 'queued'
  | 'processing'
  | 'imported'
  | 'review_required'
  | 'failed'
  | 'skipped'
  | 'kept_original';

export interface MatchCandidate {
  id: string;
  title: string;
  artist: string;
  year: number;
  format: string;
  track_count: number;
  mbid?: string;
  confidence: number;
  source: string;
}

export interface ReviewQueueItem {
  id: number;
  download_id?: number;
  artist: string;
  track: string;
  album?: string;
  downloaded_path: string;
  confidence_score: number;
  status: BeetsImportStatus;
  candidates: MatchCandidate[];
  selected_match?: MatchCandidate | null;
  created_at?: string;
}

export type ReviewAction = 'accept' | 'select_candidate' | 'keep_original' | 'skip';

export interface BeetsStatus {
  beet_cli_available: boolean;
  beet_version: string;
  config_path?: string | null;
  library_db_path?: string | null;
  library_track_count: number;
  pending_review_count: number;
  beets_api_url: string;
}
