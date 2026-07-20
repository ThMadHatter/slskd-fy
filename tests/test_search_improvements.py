import os
import pytest
from datetime import timedelta
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

# Force settings to use test database
os.environ["DATABASE_URL"] = "sqlite:///./test_auth.db"
from app.config import settings
settings.DATABASE_URL = "sqlite:///./test_auth.db"

from app.main import app
from app.database import Base, get_db, engine, SessionLocal
from app.auth import COOKIE_NAME, CSRF_COOKIE_NAME, hash_password
from app.models import User
from app.routers.pages import SearchDebugTracker
from app.services.search_ranking_service import SearchRankingService
from app.services.artist_service import ArtistService
from app.services.musicbrainz_service import MusicBrainzService

TestingSessionLocal = SessionLocal

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def setup_db():
    # Clean overrides to prevent test leakage
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db

    # Setup database tables
    Base.metadata.create_all(bind=engine)

    # Create test admin user
    db = TestingSessionLocal()
    db.query(User).delete()
    hashed = hash_password("adminpassword")
    admin = User(username="adminuser", password_hash=hashed, is_admin=True)
    db.add(admin)
    db.commit()
    db.close()

    yield

    # Teardown
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    c = TestClient(app)
    # Login to set session cookie
    resp = c.post("/login", data={"username": "adminuser", "password": "adminpassword"}, follow_redirects=False)
    cookie_val = resp.cookies.get(COOKIE_NAME)
    c.cookies.set(COOKIE_NAME, cookie_val)

    # Pre-set CSRF cookie
    c.cookies.set(CSRF_COOKIE_NAME, "test_csrf_token")
    return c

def test_query_builder_strategies():
    """
    Assert that Mode A, B, and C return the exact, expected query syntax.
    """
    # Mode A (Default)
    queries_a = SearchRankingService.generate_queries("Kendrick Lamar", "Not Like Us", mode="A")
    assert "Kendrick Lamar Not Like Us" in queries_a

    # Mode B (Quotes)
    queries_b = SearchRankingService.generate_queries("Kendrick Lamar", "Not Like Us", mode="B")
    assert queries_b == ['"Kendrick Lamar" "Not Like Us"']

    # Mode C (Prefixes)
    queries_c = SearchRankingService.generate_queries("Kendrick Lamar", "Not Like Us", mode="C")
    assert queries_c == ["artist:Kendrick Lamar track:Not Like Us"]

@pytest.mark.asyncio
async def test_musicbrainz_prefix_wildcard():
    """
    Verify search_artists uses Lucene prefix wildcards e.g. artist:(kend*)
    """
    db = TestingSessionLocal()
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "artists": [
                {
                    "id": "mbid-1",
                    "name": "Kendrick Lamar",
                    "type": "Person",
                    "country": "US",
                    "disambiguation": "Rapper"
                }
            ]
        }
        mock_get.return_value = mock_resp

        # Search for partial term
        res = await MusicBrainzService.search_artists("kend", db)
        assert len(res) == 1
        assert res[0]["name"] == "Kendrick Lamar"

        # Verify query parameters built correctly
        args, kwargs = mock_get.call_args
        params = kwargs.get("params")
        if not params and len(args) > 1:
            params = args[1]
        assert params.get("query") == "artist:(kend*)"
    db.close()

@pytest.mark.asyncio
async def test_artist_autocomplete_scoring_and_discards():
    """
    Assert that ArtistService correctly scores, ranks, and discards artists below threshold 40.
    """
    db = TestingSessionLocal()

    # Mock MusicBrainz results
    mock_mb_results = [
        {"id": "exact", "name": "Kendrick"},               # Score 100 (Exact Match)
        {"id": "starts", "name": "Kendrick Lamar"},        # Score 80 (Starts With Match)
        {"id": "word", "name": "Anna Kendrick"},          # Score 60 (Word Prefix Match)
        {"id": "contains", "name": "The Kendrick Band"},   # Score 60 (Word Prefix Match / Starts With)
        {"id": "weak", "name": "K-Dot"},                   # Score 10 (Weak/Unrelated Match)
    ]

    with patch("app.services.musicbrainz_service.MusicBrainzService.search_artists", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_mb_results

        results = await ArtistService.autocomplete("Kendrick", db)

        # Weak match ("K-Dot", Score 10) should be discarded since threshold is 40
        assert len(results) == 4
        assert results[0]["id"] == "exact"
        assert results[0]["score"] == 100
        assert results[1]["id"] == "starts"
        assert results[1]["score"] == 80

        # Verify discard logs output doesn't crash the pipeline
        ids = [r["id"] for r in results]
        assert "weak" not in ids

    db.close()

@pytest.mark.asyncio
async def test_quote_preservation_and_debug_tracker(client):
    """
    Test search results execution with Mode B to ensure double quotes are preserved
    and not stripped, and check if SearchDebugTracker records diagnostics correctly.
    """
    # Mock slskd searches
    with patch("app.services.slskd.SlskdClient.search", new_callable=AsyncMock) as mock_search, \
         patch("app.services.slskd.SlskdClient.get_search_responses", new_callable=AsyncMock) as mock_responses:

         mock_search.return_value = {"id": "search-guid-123"}
         mock_responses.return_value = [
             {
                 "username": "PeerUser",
                 "files": [
                     {
                         "filename": "Kendrick Lamar - Not Like Us.flac",
                         "size": 25000000,
                         "bitRate": 1411,
                         "sampleRate": 44100
                     }
                 ]
             }
         ]

         # Execute search with Mode B (Quotes)
         response = client.post(
             "/search/results",
             data={
                 "artist": "Kendrick Lamar",
                 "track": "Not Like Us",
                 "search_mode": "B",
                 "sort_by": "quality"
             },
             headers={"X-CSRF-Token": "test_csrf_token"}
         )

         assert response.status_code == 200

         # Assert quotes are preserved in query executed
         args, _ = mock_search.call_args
         executed_query = args[0]
         assert executed_query == '"Kendrick Lamar" "Not Like Us"'

         # Verify SearchDebugTracker fields (Task 5)
         assert SearchDebugTracker.last_artist == "Kendrick Lamar"
         assert SearchDebugTracker.last_track == "Not Like Us"
         assert SearchDebugTracker.last_search_mode == "B"
         assert SearchDebugTracker.last_generated_query == '"Kendrick Lamar" "Not Like Us"'
         assert SearchDebugTracker.last_slskd_search_id == "search-guid-123"

def test_admin_search_debug_page(client):
    """
    Verify /admin/search-debug endpoint loads successfully and renders correctly.
    """
    SearchDebugTracker.last_artist = "Kendrick Lamar"
    SearchDebugTracker.last_generated_query = '"Kendrick Lamar" "Not Like Us"'

    response = client.get("/admin/search-debug")
    assert response.status_code == 200
    assert "Search Diagnostics" in response.text
    assert 'Kendrick Lamar' in response.text
    assert 'Not Like Us' in response.text
    assert 'Run Query Benchmark' in response.text

def test_admin_benchmark_endpoint(client):
    """
    Verify /admin/search-debug/benchmark endpoint executes benchmark queries
    and successfully outputs comparison tables and conclusions.
    """
    response = client.post(
        "/admin/search-debug/benchmark",
        headers={"X-CSRF-Token": "test_csrf_token"}
    )
    assert response.status_code == 200
    assert "Slskd Query Strategy Performance Benchmark" in response.text or "Benchmark Analysis" in response.text
    assert "Kendrick Lamar Not Like Us" in response.text
    assert "100/100" in response.text
    assert "Recommendation" in response.text
