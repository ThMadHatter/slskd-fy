import os
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock, ANY
from fastapi.testclient import TestClient

# Force settings to use test database
os.environ["DATABASE_URL"] = "sqlite:///./test_auth.db"
from app.config import settings
settings.DATABASE_URL = "sqlite:///./test_auth.db"

from app.main import app
from app.database import Base, get_db, engine, SessionLocal
from app.auth import COOKIE_NAME, CSRF_COOKIE_NAME, hash_password
from app.models import User

TestingSessionLocal = SessionLocal

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def setup_db():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)

    # Create admin user
    db = TestingSessionLocal()
    db.query(User).delete()
    hashed = hash_password("adminpassword")
    admin = User(username="adminuser", password_hash=hashed, is_admin=True)
    db.add(admin)
    db.commit()
    db.close()

    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def auth_client():
    c = TestClient(app)
    # Login via API-first JSON auth endpoint to set session cookie
    resp = c.post(
        "/api/auth/login",
        json={"username": "adminuser", "password": "adminpassword"}
    )
    assert resp.status_code == 200
    cookie_val = resp.cookies.get(COOKIE_NAME)
    c.cookies.set(COOKIE_NAME, cookie_val)
    c.cookies.set(CSRF_COOKIE_NAME, "test_csrf_token")
    return c

@pytest.mark.asyncio
async def test_api_search_artist_enrichment_unbound_local_fix(auth_client):
    """
    Verifies that searching for 'Brunori' triggers dynamic artist name enrichment to 'Brunori Sas',
    does NOT crash with an UnboundLocalError, and correctly executes queries on slskd.
    """
    mock_artists = [
        {
            "id": "43e382aa-8d5e-4ac2-9378-ca34c9a0ce7b",
            "name": "Brunori Sas"
        }
    ]

    with patch("app.services.musicbrainz_service.MusicBrainzService.search_artists", new_callable=AsyncMock) as mock_search_artists, \
         patch("app.services.musicbrainz_service.MusicBrainzService.fetch_artist_releases", new_callable=AsyncMock) as mock_fetch_releases, \
         patch("app.services.slskd.SlskdClient.search", new_callable=AsyncMock) as mock_slskd_search, \
         patch("app.services.slskd.SlskdClient.get_search_responses", new_callable=AsyncMock) as mock_slskd_responses, \
         patch("app.services.slskd.SlskdClient.delete_search", new_callable=AsyncMock) as mock_slskd_delete:

        mock_search_artists.return_value = mock_artists
        mock_fetch_releases.return_value = []
        mock_slskd_search.return_value = {"id": "search-uuid-1"}
        mock_slskd_responses.return_value = [
            {
                "username": "PeerUser",
                "files": [
                    {
                        "filename": "Brunori Sas - La verita.mp3",
                        "size": 5000000,
                        "bitRate": 320
                    }
                ]
            }
        ]

        # Call /api/search with raw partial query 'Brunori'
        payload = {
            "artist": "Brunori",
            "track_or_album": "La verita",
            "mode": "A"
        }

        # Expect streaming response
        response = auth_client.post(
            "/api/search",
            json=payload,
            headers={"X-CSRF-Token": "test_csrf_token"}
        )

        assert response.status_code == 200

        # Read line-by-line JSON stream response
        content_lines = [line for line in response.iter_lines() if line]
        assert len(content_lines) > 0

        first_chunk = json.loads(content_lines[0])
        assert "results" in first_chunk
        assert len(first_chunk["results"]) > 0

        # Verify results parsed artist got enriched or matches expected
        retrieved_result = first_chunk["results"][0]
        assert "Brunori Sas" in retrieved_result["parsed_artist"]

        # Ensure search_artists was called with 'Brunori'
        mock_search_artists.assert_called_with("Brunori", ANY)

        # Ensure that progressive queries were generated using the enriched 'Brunori Sas' name
        # The generated queries should include 'Brunori Sas La verita' rather than 'Brunori La verita'
        args, _ = mock_slskd_search.call_args_list[0]
        assert "Brunori Sas" in args[0]
        assert "Brunori" in args[0]
