import os
import pytest

# Force settings to use test database BEFORE importing main or database
os.environ["DATABASE_URL"] = "sqlite:///./test_auth.db"
from app.config import settings
settings.DATABASE_URL = "sqlite:///./test_auth.db"

from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from app.main import app
from app.database import Base, get_db, engine, SessionLocal
from datetime import timedelta
from app.auth import COOKIE_NAME, create_access_token
from app.models import User

TestingSessionLocal = SessionLocal

@pytest.fixture
def client():
    # Clean dependencies before test to avoid leakage
    app.dependency_overrides.clear()

    # Setup test database and override get_db
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Setup a mock admin user in the test db
    db = TestingSessionLocal()
    db.query(User).delete()
    admin = User(username="admin", password_hash="dummy_hash", is_admin=True)
    db.add(admin)
    db.commit()
    db.close()

    expires = timedelta(hours=1)
    token = create_access_token({"sub": "admin"}, expires_delta=expires)

    with TestClient(app) as c:
        c.cookies.set(COOKIE_NAME, token)
        yield c

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)

@pytest.mark.asyncio
async def test_api_autocomplete_artist_endpoint(client):
    with patch("app.services.artist_service.ArtistService.autocomplete", new_callable=AsyncMock) as mock_auto:
        mock_auto.return_value = [
            {"id": "mbid-1", "name": "Kendrick Lamar", "type": "Person", "country": "US", "disambiguation": "Rapper"}
        ]

        response = client.get("/api/autocomplete/artist?q=kendri")
        assert response.status_code == 200
        assert "Kendrick Lamar" in response.text
        assert "Rapper" in response.text

@pytest.mark.asyncio
async def test_api_autocomplete_track_endpoint(client):
    with patch("app.services.track_service.TrackService.autocomplete", new_callable=AsyncMock) as mock_auto:
        mock_auto.return_value = [
            {"id": "rec-1", "title": "Not Like Us", "album": "Single", "year": 2024, "cover_url": "http://img"}
        ]

        response = client.get("/api/autocomplete/track?artist_name=Kendrick+Lamar&q=not+like")
        assert response.status_code == 200
        assert "Not Like Us" in response.text
        assert "Single" in response.text
