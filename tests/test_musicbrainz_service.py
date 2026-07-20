import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.services.musicbrainz_service import MusicBrainzService

engine = create_engine("sqlite:///:memory:")
TestingSessionLocal = sessionmaker(bind=engine)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.mark.asyncio
async def test_search_artists_success():
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

        res = await MusicBrainzService.search_artists("Kendrick", db)
        assert len(res) == 1
        assert res[0]["id"] == "mbid-1"
        assert res[0]["name"] == "Kendrick Lamar"

    db.close()

@pytest.mark.asyncio
async def test_search_recordings_success():
    db = TestingSessionLocal()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "recordings": [
                {
                    "id": "rec-1",
                    "title": "Not Like Us",
                    "releases": [
                        {
                            "id": "rel-1",
                            "title": "Not Like Us Single",
                            "date": "2024-05-04"
                        }
                    ]
                }
            ]
        }
        mock_get.return_value = mock_resp

        res = await MusicBrainzService.search_recordings("Kendrick Lamar", "mbid-1", "Not Like Us", db)
        assert len(res) == 1
        assert res[0]["id"] == "rec-1"
        assert res[0]["title"] == "Not Like Us"
        assert res[0]["album"] == "Not Like Us Single"
        assert res[0]["year"] == 2024

    db.close()
