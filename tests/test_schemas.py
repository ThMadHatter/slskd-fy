import pytest
from datetime import datetime
from app.schemas import (
    UserCreate, UserResponse, WishlistCreate, WishlistUpdate, WishlistResponse,
    FavoriteCreate, FavoriteResponse, DownloadHistoryCreate, DownloadHistoryResponse,
    SearchHistoryBase, SearchHistoryResponse
)

def test_user_schemas():
    user = UserCreate(username="admin", password="password")
    assert user.username == "admin"

    resp = UserResponse(id=1, username="admin", is_admin=True, created_at=datetime.utcnow())
    assert resp.id == 1

def test_wishlist_schemas():
    wish = WishlistCreate(artist="Daft Punk", track="Get Lucky", album="RAM", notes="Vinyl rip")
    assert wish.artist == "Daft Punk"

    update = WishlistUpdate(status="downloaded")
    assert update.status == "downloaded"

    resp = WishlistResponse(
        id=1, artist="Daft Punk", track="Get Lucky", album="RAM", notes="Vinyl",
        status="downloaded", created_at=datetime.utcnow()
    )
    assert resp.status == "downloaded"

def test_favorite_schemas():
    fav = FavoriteCreate(artist="Daft Punk", track="Get Lucky", album="RAM", source="user1")
    assert fav.artist == "Daft Punk"

    resp = FavoriteResponse(
        id=1, artist="Daft Punk", track="Get Lucky", album="RAM", source="user1",
        created_at=datetime.utcnow()
    )
    assert resp.id == 1

def test_download_history_schemas():
    dl = DownloadHistoryCreate(
        search_query="Daft Punk", artist="Daft Punk", track="Get Lucky", album="RAM",
        filename="song.mp3", source_user="user1", format="mp3", status="downloading"
    )
    assert dl.status == "downloading"

    resp = DownloadHistoryResponse(
        id=1, search_query="Daft Punk", artist="Daft Punk", track="Get Lucky", album="RAM",
        filename="song.mp3", source_user="user1", format="mp3", status="completed",
        downloaded_at=datetime.utcnow()
    )
    assert resp.id == 1

def test_search_history_schemas():
    base = SearchHistoryBase(query="Daft Punk", result_count=10)
    assert base.query == "Daft Punk"

    resp = SearchHistoryResponse(id=1, query="Daft Punk", result_count=10, created_at=datetime.utcnow())
    assert resp.id == 1
