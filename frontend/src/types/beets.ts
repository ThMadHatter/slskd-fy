export type BeetsImportStatus =
  | 'queued'
  | 'processing'
  | 'imported'
  | 'review_required'
  | 'open'
  | 'failed'
  | 'skipped'
  | 'kept_original'
  | 'ignored'
  | 'resolving';

export interface MatchCandidate {
  id: string;
  source: string;
  candidate_type: 'album' | 'singleton';
  artist: string;
  album?: string;
  title: string;
  year: number;
  release_id?: string;
  recording_id?: string;
  release_group_id?: string;
  country?: string;
  label?: string;
  catalog_num?: string;
  media?: string;
  format?: string;
  track_count: number;
  ui_similarity_score: number;
  raw_distance?: number;
  penalties?: Record<string, number>;
  mbid?: string;
  url?: string;
  confidence?: number;
}

export interface MetadataProvenance {
  embedded_tags: {
    artist?: string | null;
    track?: string | null;
    album?: string | null;
    year?: number | null;
  };
  filename_inferred: {
    artist?: string | null;
    track?: string | null;
    album?: string | null;
  };
  parent_dir_inferred: {
    artist?: string | null;
    album?: string | null;
    year?: number | null;
  };
  technical_props: {
    format: string;
    bitrate?: number | null;
    sample_rate?: number | null;
    channels?: number | null;
  };
  clean_album_hint?: string;
}

export interface ReviewQueueItem {
  id: number;
  conflict_id?: string;
  fingerprint?: string;
  job_id?: string;
  download_id?: number;
  item_type: 'album' | 'singleton';
  artist: string;
  track: string;
  album?: string;
  downloaded_path: string;
  confidence_score: number;
  raw_distance?: number | null;
  status: BeetsImportStatus;
  provenance?: MetadataProvenance;
  candidates: MatchCandidate[];
  selected_match?: MatchCandidate | null;
  differences?: Record<string, { current: string; candidate: string }>;
  recommendation?: string;
  retry_count?: number;
  created_at?: string;
}

export type ReviewAction = 'accept' | 'select_candidate' | 'keep_original' | 'skip' | 'ignore' | 'retry';

export interface FailedPlugin {
  name: string;
  reason: string;
}

export interface MetadataSourceInfo {
  name: string;
  type: string;
  active: boolean;
}

export interface BeetsStatus {
  beet_cli_available: boolean;
  beet_version: string;
  config_path?: string | null;
  library_db_path?: string | null;
  music_directory?: string;
  library_track_count: number;
  pending_review_count: number;
  configured_plugins: string[];
  loaded_plugins: string[];
  failed_plugins?: FailedPlugin[];
  missing_dependencies?: string[];
  metadata_sources?: MetadataSourceInfo[];
  musicbrainz_connected?: boolean;
  beets_api_url: string;
}
