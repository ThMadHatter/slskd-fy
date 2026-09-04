import os
import pytest
from io import BytesIO
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, patch, MagicMock
from app.config import settings
from app.database import Base, get_db, engine
from app.main import app
from app.models import User, DownloadHistory
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
    LOGIN_ATTEMPTS.clear()

    # Enforce isolated dependency overrides for this test module
    app.dependency_overrides[get_db] = override_get_db
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
    db.query(DownloadHistory).delete()

    hashed = hash_password("adminpassword")
    user = User(username="adminuser", password_hash=hashed, is_admin=True)
    db.add(user)

    # Create file
    completed_file = singles_dir / "song.mp3"
    with open(completed_file, "w") as f:
        f.write("dummy-audio")

    h = DownloadHistory(
        id=1,
        search_query="Daft Punk", artist="Daft Punk", track="One More Time", album="Discovery",
        filename="song.mp3", source_user="user1", format="mp3", status="downloading", size_bytes=1000000
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

@patch("app.services.slskd.SlskdClient.get_downloads", new_callable=AsyncMock)
def test_downloads_list_active_mapping(mock_get_downloads):
    client = get_auth_client()

    # Mocking active download with progress
    mock_get_downloads.return_value = [
        {
            "filename": "song.mp3",
            "username": "user1",
            "bytes_transferred": 500000,
            "size": 1000000,
            "average_speed": 102400, # 100 KB/s
            "state": "Downloading"
        }
    ]

    response = client.get("/downloads/list")
    assert response.status_code == 200
    assert "song.mp3" in response.text

@patch("app.routers.pages.write_tags")
def test_metadata_save_with_cover(mock_write_tags):
    client = get_auth_client()
    mock_write_tags.return_value = True

    # Create fake image file in memory
    fake_image = BytesIO(b"fake-image-bytes")
    fake_image.name = "cover.jpg"

    response = client.post(
        "/metadata-queue/1/save",
        data={
            "title": "One More Time (New)",
            "artist": "Daft Punk",
            "album": "Discovery (New)",
            "album_artist": "Daft Punk",
            "track_number": "1",
            "year": "2001",
            "genre": "House",
            "comment": "Nice song"
        },
        files={"cover_art": ("cover.jpg", fake_image, "image/jpeg")},
        headers={"X-CSRF-Token": "test_csrf_token"},
        follow_redirects=True
    )
    assert response.status_code == 200  # Followed redirect successfully
    mock_write_tags.assert_called_once()

def test_beets_status_endpoint():
    client = get_auth_client()
    response = client.get("/api/beets/status")
    assert response.status_code == 200
    data = response.json()
    assert "beet_cli_available" in data
    assert "beet_version" in data
    assert "library_track_count" in data

def test_beets_seed_test_items_endpoint():
    client = get_auth_client()
    response = client.post("/api/beets/seed-test-items")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "success"
    assert data.get("items_count") == 3

@patch("asyncio.create_subprocess_exec", new_callable=AsyncMock)
def test_beets_scan_library_endpoint(mock_subprocess):
    client = get_auth_client()

    mock_proc = AsyncMock()
    mock_proc.communicate.return_value = (b"Scanning /music...\nDone", b"")
    mock_subprocess.return_value = mock_proc

    response = client.post("/api/beets/scan-library")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "success"
