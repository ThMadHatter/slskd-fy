import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, patch
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
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)

def get_auth_client():
    client = TestClient(app)
    resp = client.post("/login", data={"username": "adminuser", "password": "adminpassword"}, follow_redirects=False)
    cookie_val = resp.cookies.get(COOKIE_NAME)
    client.cookies.set(COOKIE_NAME, cookie_val)
    client.cookies.set(CSRF_COOKIE_NAME, "test_csrf_token")
    return client

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
    assert "items_count" in data

def test_beets_scan_library_endpoint():
    client = get_auth_client()
    response = client.post("/api/beets/scan-library")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "success"
