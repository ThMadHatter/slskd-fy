import os
import pytest

# Force settings to use test database BEFORE importing main or database
os.environ["DATABASE_URL"] = "sqlite:///./test_auth.db"
from app.config import settings
settings.DATABASE_URL = "sqlite:///./test_auth.db"

from fastapi.testclient import TestClient
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

@pytest.fixture(autouse=True)
def setup_db(tmp_path):
    # Reset login rate limiter
    LOGIN_ATTEMPTS.clear()

    # Enforce isolated dependency overrides for this test module
    app.dependency_overrides[get_db] = override_get_db

    # Setup temporary Singles and Library directories for tests
    singles_dir = tmp_path / "singles"
    music_dir = tmp_path / "music"
    os.makedirs(singles_dir, exist_ok=True)
    os.makedirs(music_dir, exist_ok=True)

    settings.SINGLES_PATH = str(singles_dir)
    settings.MUSIC_LIBRARY_PATH = str(music_dir)

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.query(User).delete()
    db.query(Wishlist).delete()
    db.query(DownloadHistory).delete()

    hashed = hash_password("adminpassword")
    user = User(username="adminuser", password_hash=hashed, is_admin=True)
    db.add(user)

    # Create the completed file on disk in temp singles_dir
    completed_file = singles_dir / "song.mp3"
    with open(completed_file, "w") as f:
        f.write("dummy-audio")

    h = DownloadHistory(
        id=1,
        search_query="Daft Punk", artist="Daft Punk", track="One More Time", album="Discovery",
        filename="song.mp3", source_user="user1", format="mp3", status="completed"
    )
    db.add(h)

    db.commit()
    db.close()
    yield
    # Clear overrides on teardown to avoid global leakage
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)

def get_auth_client():
    client = TestClient(app)
    resp = client.post("/login", data={"username": "adminuser", "password": "adminpassword"}, follow_redirects=False)
    cookie_val = resp.cookies.get(COOKIE_NAME)
    client.cookies.set(COOKIE_NAME, cookie_val)
    client.cookies.set(CSRF_COOKIE_NAME, "test_csrf_token")
    return client

def test_get_history_edit():
    client = get_auth_client()
    response = client.get("/metadata-queue?edit=1")
    assert response.status_code == 200
    assert "Edit" in response.text

@patch("app.services.tagger.write_tags")
@patch("app.services.navidrome.NavidromeClient.start_scan", new_callable=AsyncMock)
def test_history_edit_import_post(mock_scan, mock_write_tags):
    client = get_auth_client()
    mock_write_tags.return_value = True
    mock_scan.return_value = True

    response = client.post(
        "/metadata-queue/1/save",
        data={
            "title": "One More Time (New)",
            "artist": "Daft Punk",
            "album": "Discovery (New)",
            "album_artist": "Daft Punk",
            "track_number": "2",
            "year": "2001",
            "genre": "House",
            "comment": "Nice song"
        },
        headers={"X-CSRF-Token": "test_csrf_token"},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert "Metadata Queue" in response.text

@patch("app.services.slskd.SlskdClient.get_downloads", new_callable=AsyncMock)
@patch("app.services.slskd.SlskdClient.cancel_download", new_callable=AsyncMock)
def test_downloads_cancel_post(mock_cancel, mock_downloads):
    client = get_auth_client()
    mock_downloads.return_value = [
        {"filename": "song.mp3", "username": "user1", "id": "transfer-id-123"}
    ]
    mock_cancel.return_value = True

    response = client.post(
        "/downloads/1/cancel",
        headers={"X-CSRF-Token": "test_csrf_token"}
    )
    assert response.status_code == 200
