from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime

# --- User Schemas ---
class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

# --- Wishlist Schemas ---
class WishlistBase(BaseModel):
    artist: str
    track: str
    album: Optional[str] = None
    notes: Optional[str] = None

class WishlistCreate(WishlistBase):
    pass

class WishlistUpdate(BaseModel):
    status: Optional[str] = None
    artist: Optional[str] = None
    track: Optional[str] = None
    album: Optional[str] = None
    notes: Optional[str] = None

class WishlistResponse(WishlistBase):
    id: int
    status: str
    created_at: datetime
    fulfilled_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

# --- Favorites Schemas ---
class FavoriteBase(BaseModel):
    artist: str
    track: str
    album: str
    source: str

class FavoriteCreate(FavoriteBase):
    pass

class FavoriteResponse(FavoriteBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# --- DownloadHistory Schemas ---
class DownloadHistoryBase(BaseModel):
    search_query: str
    artist: str
    track: str
    album: str
    filename: str
    download_id: Optional[str] = None
    source_user: str
    format: str
    bitrate: Optional[int] = None
    sample_rate: Optional[int] = None
    size_bytes: Optional[int] = None
    status: str
    file_hash: Optional[str] = None

class DownloadHistoryCreate(DownloadHistoryBase):
    pass

class DownloadHistoryResponse(DownloadHistoryBase):
    id: int
    downloaded_at: datetime
    imported_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

# --- SearchHistory Schemas ---
class SearchHistoryBase(BaseModel):
    query: str
    result_count: int

class SearchHistoryResponse(SearchHistoryBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# --- AuditLog Schemas ---
class AuditLogBase(BaseModel):
    action: str
    details: Optional[str] = None
    ip_address: Optional[str] = None

class AuditLogResponse(AuditLogBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
