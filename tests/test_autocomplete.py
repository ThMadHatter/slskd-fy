import pytest
import json
from unittest.mock import patch, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import DownloadHistory
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

    entry = DownloadHistory(
        search_query="test", artist="Kendrick Lamar", track="Humble", album="Damn",
        filename="1.mp3", source_user="user1", format="mp3", status="completed"
    )
    db.add(entry)
    db.commit()

    with patch("app.services.beets_service.BeetsServiceClient.search_items", new_callable=AsyncMock) as mock_beets:
        mock_beets.return_value = []

        res = await ArtistService.autocomplete("Kendrick", db)
        assert len(res) == 1
        assert res[0]["name"] == "Kendrick Lamar"
        assert res[0]["disambiguation"] == "Download History"

    db.close()

@pytest.mark.asyncio
async def test_track_autocomplete_fallback_to_history():
    db = TestingSessionLocal()

    entry = DownloadHistory(
        search_query="test", artist="Kendrick Lamar", track="Not Like Us", album="Single",
        filename="1.mp3", source_user="user1", format="mp3", status="completed"
    )
    db.add(entry)
    db.commit()

    with patch("app.services.beets_service.BeetsServiceClient.search_items", new_callable=AsyncMock) as mock_beets:
        mock_beets.return_value = []

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
