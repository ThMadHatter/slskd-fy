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
