import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import DownloadHistory, CacheEntry, CacheMetric
from app.services.artist_service import ArtistService
from app.services.track_service import TrackService

engine = create_engine("sqlite:///:memory:")
TestingSessionLocal = sessionmaker(bind=engine)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.mark.asyncio
async def test_artist_autocomplete_too_short():
    db = TestingSessionLocal()
    res = await ArtistService.autocomplete("a", db)
    assert res == []
    db.close()

@pytest.mark.asyncio
async def test_artist_autocomplete_fallback_to_history():
    db = TestingSessionLocal()

    # Add a track in DownloadHistory to test fallback lookup
    entry = DownloadHistory(
        search_query="test", artist="Kendrick Lamar", track="Humble", album="Damn",
        filename="1.mp3", source_user="user1", format="mp3", status="completed"
    )
    db.add(entry)
    db.commit()

    # Mock MusicBrainz to fail/return empty to trigger fallback
    with patch("app.services.musicbrainz_service.MusicBrainzService.search_artists", new_callable=AsyncMock) as mock_mb:
        mock_mb.return_value = []

        res = await ArtistService.autocomplete("Kendrick", db)
        assert len(res) == 1
        assert res[0]["name"] == "Kendrick Lamar"
        assert res[0]["disambiguation"] == "Download History"

    db.close()

@pytest.mark.asyncio
async def test_artist_autocomplete_cache_entry_hit():
    db = TestingSessionLocal()

    # Create cached artists
    cached_value = [
        {"id": "mbid-1", "name": "Kendrick Lamar", "type": "Person", "country": "US", "disambiguation": "Rapper"}
    ]
    expires_at = datetime.utcnow() + timedelta(days=1)
    entry = CacheEntry(
        key="mb:artist_search:kendrick",
        value=json.dumps(cached_value),
        entity_type="artist",
        expires_at=expires_at
    )
    db.add(entry)
    db.commit()

    # Mock MusicBrainz search to return empty so we see fallback or we fetch from cache via search
    with patch("app.services.musicbrainz_service.MusicBrainzService.search_artists", new_callable=AsyncMock) as mock_mb:
        mock_mb.return_value = []

        res = await ArtistService.autocomplete("Kendrick", db)
        # Should find from CacheEntry query contains kendrick
        assert len(res) == 1
        assert res[0]["name"] == "Kendrick Lamar"

    db.close()

@pytest.mark.asyncio
async def test_track_autocomplete_fallback_to_history():
    db = TestingSessionLocal()

    # Add a track in DownloadHistory to test fallback lookup
    entry = DownloadHistory(
        search_query="test", artist="Kendrick Lamar", track="Not Like Us", album="Single",
        filename="1.mp3", source_user="user1", format="mp3", status="completed"
    )
    db.add(entry)
    db.commit()

    # Mock MusicBrainz to return empty to trigger fallback
    with patch("app.services.musicbrainz_service.MusicBrainzService.search_recordings", new_callable=AsyncMock) as mock_mb:
        mock_mb.return_value = []

        res = await TrackService.autocomplete("Kendrick Lamar", None, "Not Like Us", db)
        assert len(res) == 1
        assert res[0]["title"] == "Not Like Us"
        assert res[0]["album"] == "Single"

    db.close()

@pytest.mark.asyncio
async def test_track_autocomplete_empty_artist():
    db = TestingSessionLocal()
    res = await TrackService.autocomplete("", None, "Humble", db)
    assert res == []
    db.close()

@pytest.mark.asyncio
async def test_track_autocomplete_cache_hit():
    db = TestingSessionLocal()

    cached_tracks = [
        {"id": "rec-1", "title": "Humble", "album": "Damn", "year": 2017, "cover_url": "http://img"}
    ]
    entry = CacheEntry(
        key="mb:rec_search:kendrick lamar:none:humble",
        value=json.dumps(cached_tracks),
        entity_type="track",
        expires_at=datetime.utcnow() + timedelta(days=1)
    )
    db.add(entry)
    db.commit()

    with patch("app.services.musicbrainz_service.MusicBrainzService.search_recordings", new_callable=AsyncMock) as mock_mb:
        mock_mb.return_value = []

        res = await TrackService.autocomplete("Kendrick Lamar", None, "Humble", db)
        assert len(res) == 1
        assert res[0]["title"] == "Humble"
        assert res[0]["album"] == "Damn"

    db.close()
