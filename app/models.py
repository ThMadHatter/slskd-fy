import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    two_factor_secret = Column(String, nullable=True)
    two_factor_enabled = Column(Boolean, default=False, nullable=False)

class Wishlist(Base):
    __tablename__ = "wishlist"

    id = Column(Integer, primary_key=True, index=True)
    artist = Column(String, nullable=False)
    track = Column(String, nullable=False)
    album = Column(String, nullable=True)
    notes = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, searching, downloaded, imported, failed
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    fulfilled_at = Column(DateTime, nullable=True)

class Favorites(Base):
    __tablename__ = "favorites"

    id = Column(Integer, primary_key=True, index=True)
    artist = Column(String, nullable=False)
    track = Column(String, nullable=False)
    album = Column(String, nullable=False)
    source = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class DownloadHistory(Base):
    __tablename__ = "download_history"

    id = Column(Integer, primary_key=True, index=True)
    search_query = Column(String, nullable=False)
    artist = Column(String, nullable=False)
    track = Column(String, nullable=False)
    album = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    download_id = Column(String, nullable=True)
    source_user = Column(String, nullable=False)
    format = Column(String, nullable=False)
    bitrate = Column(Integer, nullable=True)
    sample_rate = Column(Integer, nullable=True)
    size_bytes = Column(Integer, nullable=True)
    status = Column(String, nullable=False)  # downloading, completed, tagged, imported, failed
    file_hash = Column(String, nullable=True) # for duplicate detection via hash
    downloaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    imported_at = Column(DateTime, nullable=True)

class SearchHistory(Base):
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    result_count = Column(Integer, default=0)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, nullable=False)
    details = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class CacheEntry(Base):
    __tablename__ = "cache_entries"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(String, nullable=False)  # JSON representation of the cached value
    entity_type = Column(String, nullable=False)  # artist, album, track, musicbrainz
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class CacheMetric(Base):
    __tablename__ = "cache_metrics"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String, unique=True, nullable=False)  # artist, album, track, musicbrainz
    hits = Column(Integer, default=0, nullable=False)
    misses = Column(Integer, default=0, nullable=False)

class BeetsImportJob(Base):
    __tablename__ = "beets_import_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, unique=True, index=True, nullable=False)
    source_path = Column(String, nullable=False)
    status = Column(String, default="queued", nullable=False) # queued, running, completed, completed_with_conflicts, failed, cancelled
    total_items = Column(Integer, default=0, nullable=False)
    imported_items = Column(Integer, default=0, nullable=False)
    conflicts_count = Column(Integer, default=0, nullable=False)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class BeetsReviewItem(Base):
    __tablename__ = "beets_review_items"

    id = Column(Integer, primary_key=True, index=True)
    conflict_id = Column(String, unique=True, index=True, nullable=True)
    fingerprint = Column(String, index=True, nullable=True)
    job_id = Column(String, nullable=True)
    download_id = Column(Integer, nullable=True)
    item_type = Column(String, default="album", nullable=False) # album or singleton
    artist = Column(String, nullable=False)
    track = Column(String, nullable=False)
    album = Column(String, nullable=True)
    downloaded_path = Column(String, nullable=False)
    confidence_score = Column(Integer, default=50) # e.g. 50-89% confidence
    status = Column(String, default="open", nullable=False) # open (review_required), resolving, resolved (imported), skipped, ignored (kept_original), failed, stale
    candidates_json = Column(String, nullable=False) # JSON list of match candidates
    selected_match_json = Column(String, nullable=True)
    differences_json = Column(String, nullable=True)
    provenance_json = Column(String, nullable=True)
    recommendation_text = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    resolution_audit = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
