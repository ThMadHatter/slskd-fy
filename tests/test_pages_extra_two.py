import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from unittest.mock import AsyncMock, patch, MagicMock
from app.config import settings
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
    LOGIN_ATTEMPTS.clear()
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
    db.query(Favorites).delete()

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

    w = Wishlist(id=2, artist="Daft Punk", track="One More Time", status="pending")
    db.add(w)

    f_item = Favorites(id=3, artist="Daft Punk", track="One More Time", album="Discovery", source="user1")
    db.add(f_item)

    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)

def get_auth_client():
    client = TestClient(app)
    resp = client.post("/login", data={"username": "adminuser", "password": "adminpassword"}, follow_redirects=False)
    cookie_val = resp.cookies.get(COOKIE_NAME)
    client.cookies.set(COOKIE_NAME, cookie_val)
    client.cookies.set(CSRF_COOKIE_NAME, "test_csrf_token")
    return client

def test_delete_wishlist_item():
    client = get_auth_client()
    response = client.post(
        "/wishlist/2/delete",
        headers={"X-CSRF-Token": "test_csrf_token"},
        follow_redirects=True
    )
    assert response.status_code == 200
    db = TestingSessionLocal()
    assert db.query(Wishlist).count() == 0
    db.close()

def test_delete_favorite_item():
    client = get_auth_client()
    response = client.post(
        "/favorites/3/delete",
        headers={"X-CSRF-Token": "test_csrf_token"},
        follow_redirects=True
    )
    assert response.status_code == 200
    db = TestingSessionLocal()
    assert db.query(Favorites).count() == 0
    db.close()

@patch("app.services.navidrome.NavidromeClient.start_scan", new_callable=AsyncMock)
def test_import_track_post(mock_scan):
    client = get_auth_client()
    mock_scan.return_value = True

    response = client.post(
        "/metadata-queue/1/import",
        headers={"X-CSRF-Token": "test_csrf_token"},
        follow_redirects=True
    )
    assert response.status_code == 200

    # Confirm status in DB changed to 'imported'
    db = TestingSessionLocal()
    log = db.query(DownloadHistory).filter(DownloadHistory.id == 1).first()
    assert log.status == "imported"
    db.close()
