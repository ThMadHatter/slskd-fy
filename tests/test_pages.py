import os
import pytest

# Force settings to use test database BEFORE importing main or database
os.environ["DATABASE_URL"] = "sqlite:///./test_auth.db"
from app.config import settings
settings.DATABASE_URL = "sqlite:///./test_auth.db"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, patch, MagicMock
from app.database import Base, get_db, engine
from app.main import app
from app.models import User, Wishlist, Favorites, DownloadHistory
from app.auth import hash_password, COOKIE_NAME, CSRF_COOKIE_NAME, LOGIN_ATTEMPTS

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    # Reset login rate limiter
    LOGIN_ATTEMPTS.clear()

    # Setup temporary Singles and Library directories for tests
    singles_dir = tmp_path / "singles"
    music_dir = tmp_path / "music"
    downloads_dir = tmp_path / "downloads"
    os.makedirs(singles_dir, exist_ok=True)
    os.makedirs(music_dir, exist_ok=True)
    os.makedirs(downloads_dir, exist_ok=True)

    settings.SINGLES_PATH = str(singles_dir)
    settings.MUSIC_LIBRARY_PATH = str(music_dir)
    settings.DOWNLOADS_PATH = str(downloads_dir)

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.query(User).delete()
    db.query(Wishlist).delete()
    db.query(Favorites).delete()
    db.query(DownloadHistory).delete()

    # Add test user
    hashed = hash_password("adminpassword")
    user = User(username="adminuser", password_hash=hashed, is_admin=True)
    db.add(user)

    # Add dummy wishlist, favorites, and history entries
    w = Wishlist(artist="Daft Punk", track="One More Time", album="Discovery", status="pending")
    db.add(w)

    fav = Favorites(artist="Daft Punk", track="Harder Better", album="Discovery", source="user1")
    db.add(fav)

    h = DownloadHistory(
        search_query="Daft Punk", artist="Daft Punk", track="One More Time", album="Discovery",
        filename="song.mp3", source_user="user1", format="mp3", status="completed"
    )
    db.add(h)

    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)

def get_auth_client():
    client = TestClient(app)
    # Perform login to set cookie
    resp = client.post("/login", data={"username": "adminuser", "password": "adminpassword"}, follow_redirects=False)
    cookie_val = resp.cookies.get(COOKIE_NAME)
    client.cookies.set(COOKIE_NAME, cookie_val)

    # Also pre-set CSRF cookies for mutable calls
    client.cookies.set(CSRF_COOKIE_NAME, "test_csrf_token")
    return client

def test_get_dashboard():
    client = get_auth_client()
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "Dashboard" in response.text

def test_get_search_page():
    client = get_auth_client()
    response = client.get("/search")
    assert response.status_code == 200
    assert "Search" in response.text

def test_get_downloads_page():
    client = get_auth_client()
    response = client.get("/downloads")
    assert response.status_code == 200
    assert "Downloads" in response.text

def test_get_wishlist_page():
    client = get_auth_client()
    response = client.get("/wishlist")
    assert response.status_code == 200
    assert "Wishlist" in response.text

def test_get_favorites_page():
    client = get_auth_client()
    response = client.get("/favorites")
    assert response.status_code == 200
    assert "Favorites" in response.text

def test_get_history_page():
    client = get_auth_client()
    response = client.get("/history")
    assert response.status_code == 200
    assert "History" in response.text

def test_get_admin_page():
    client = get_auth_client()
    response = client.get("/admin")
    assert response.status_code == 200
    assert "Administration" in response.text

def test_create_wishlist_item():
    client = get_auth_client()
    response = client.post(
        "/wishlist/create",
        data={"artist": "Justice", "track": "Genesis", "album": "Cross", "notes": "High quality"},
        headers={"X-CSRF-Token": "test_csrf_token"},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert "Justice" in response.text

def test_delete_favorites():
    client = get_auth_client()
    db = TestingSessionLocal()
    fav = db.query(Favorites).first()
    fav_id = fav.id
    db.close()

    response = client.post(
        f"/favorites/{fav_id}/delete",
        headers={"X-CSRF-Token": "test_csrf_token"},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert "Harder Better" not in response.text

def test_toggle_favorites():
    client = get_auth_client()
    response = client.post(
        "/favorites/toggle",
        data={"artist": "NewArtist", "track": "NewTrack", "album": "NewAlbum", "source": "user2"},
        headers={"X-CSRF-Token": "test_csrf_token"},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert "NewArtist" in response.text

@patch("app.services.slskd.SlskdClient.search", new_callable=AsyncMock)
@patch("app.services.slskd.SlskdClient.get_search_responses", new_callable=AsyncMock)
def test_search_results_post(mock_responses, mock_search):
    client = get_auth_client()

    mock_search.return_value = {"id": "search-uuid-123"}
    mock_responses.return_value = [
        {
            "username": "user1",
            "queueLength": 0,
            "files": [{"filename": "Daft Punk - Instant Crush.mp3", "size": 5000000, "bitRate": 320}]
        }
    ]

    response = client.post(
        "/search/results",
        data={"artist": "Daft Punk", "track": "Instant Crush", "sort_by": "quality"},
        headers={"X-CSRF-Token": "test_csrf_token"}
    )
    assert response.status_code == 200
    assert "Instant Crush" in response.text

@patch("app.services.slskd.SlskdClient.enqueue_download", new_callable=AsyncMock)
def test_downloads_create_post(mock_enqueue):
    client = get_auth_client()
    mock_enqueue.return_value = True

    response = client.post(
        "/downloads/create",
        data={
            "artist": "Daft Punk",
            "track": "Instant Crush",
            "filename": "Daft Punk - Instant Crush.mp3",
            "size": 5000000,
            "username": "user1",
            "format": "mp3",
            "bitrate": 320
        },
        headers={"X-CSRF-Token": "test_csrf_token"}
    )
    assert response.status_code == 200
    assert "Downloading" in response.text

def test_admin_change_password_success():
    client = get_auth_client()
    response = client.post(
        "/admin/change-password",
        data={
            "current_password": "adminpassword",
            "new_password": "newsecurepassword123",
            "confirm_password": "newsecurepassword123"
        },
        headers={"X-CSRF-Token": "test_csrf_token"}
    )
    assert response.status_code == 200
    assert "Password changed successfully" in response.text

def test_admin_change_password_mismatch():
    client = get_auth_client()
    response = client.post(
        "/admin/change-password",
        data={
            "current_password": "adminpassword",
            "new_password": "newsecurepassword123",
            "confirm_password": "different_password"
        },
        headers={"X-CSRF-Token": "test_csrf_token"}
    )
    assert response.status_code == 200
    assert "New passwords do not match" in response.text

@patch("app.services.slskd.SlskdClient.get_downloads", new_callable=AsyncMock)
def test_downloads_list(mock_downloads):
    client = get_auth_client()
    mock_downloads.return_value = []

    response = client.get("/downloads/list")
    assert response.status_code == 200

@patch("app.services.navidrome.NavidromeClient.start_scan", new_callable=AsyncMock)
def test_navidrome_rescan_post(mock_scan):
    client = get_auth_client()
    mock_scan.return_value = True

    response = client.post(
        "/navidrome/rescan",
        headers={"X-CSRF-Token": "test_csrf_token"}
    )
    assert response.status_code == 200
    assert "triggered" in response.text
