import os
import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

# Force settings timeout for tests
os.environ["GHOST_PEER_TIMEOUT_SEC"] = "1"

from app.database import Base, SessionLocal, engine
from app.models import DownloadHistory, Wishlist, CacheEntry
from app.services.musicbrainz_service import MusicBrainzService
from app.services.downloads_poller import poll_downloads, STALL_TRACKER
from app.services import downloads_poller as downloads_poller_module

TestingSessionLocal = SessionLocal

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.query(DownloadHistory).delete()
    db.query(Wishlist).delete()
    db.query(CacheEntry).delete()
    db.commit()
    db.close()
    yield
    db = TestingSessionLocal()
    db.query(DownloadHistory).delete()
    db.query(Wishlist).delete()
    db.query(CacheEntry).delete()
    db.commit()
    db.close()


# ----------------- Circuit Breaker Tests [DAT-002] -----------------

@pytest.mark.asyncio
async def test_musicbrainz_circuit_breaker_trip():
    """
    [DAT-002] Simulates MusicBrainz consecutive failures to ensure the Circuit Breaker trips OPEN
    and gracefully degrades subsequent requests without hitting the network.
    """
    # Reset circuit breaker state before testing
    MusicBrainzService.CIRCUIT_OPEN = False
    MusicBrainzService.FAILURE_COUNT = 0

    db = TestingSessionLocal()

    # Mock outbound httpx client returning 500 errors
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_get.return_value = mock_resp

        # Trigger 3 failures on different queries to bypass cache hits [DAT-002]
        for i in range(3):
            res = await MusicBrainzService.search_artists(f"Kendrick_{i}", db)
            assert res == []

        # Circuit breaker should now be OPEN
        assert MusicBrainzService.CIRCUIT_OPEN is True
        assert MusicBrainzService.FAILURE_COUNT == 3

        # Next call should bypass httpx entirely (mock_get call count remains 3)
        mock_get.reset_mock()
        res_open = await MusicBrainzService.search_artists("Kendrick_Open", db)
        assert res_open == []
        mock_get.assert_not_called()

    # Test circuit breaker half-open reset timeout recovery
    MusicBrainzService.LAST_FAILURE_TIME = 0.0 # Force ancient failure time
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"artists": []}
        mock_get.return_value = mock_resp

        # Call should trigger half-open retry
        res_reset = await MusicBrainzService.search_artists("Kendrick_Reset", db)
        assert res_reset == []
        # Since call succeeded, circuit breaker resets to CLOSED
        assert MusicBrainzService.CIRCUIT_OPEN is False
        assert MusicBrainzService.FAILURE_COUNT == 0

    db.close()


# ----------------- Ghost Peer Timeout Tests [RSL-002] -----------------

original_sleep = asyncio.sleep

@pytest.mark.asyncio
async def test_ghost_peer_timeout_and_seamless_fallback():
    """
    [RSL-002] Simulates a stalled slskd transfer to verify that the downloads poller
    autonomously cancels it and enqueues the next best candidate from the peer list.
    """
    STALL_TRACKER.clear()
    downloads_poller_module.GHOST_PEER_TIMEOUT_SEC = 1

    db = TestingSessionLocal()

    # 1. Setup active download entry
    download = DownloadHistory(
        search_query="Kendrick Lamar - Not Like Us",
        artist="Kendrick Lamar",
        track="Not Like Us",
        album="Single",
        filename="Daft Punk - Not Like Us (Ghost).mp3",
        source_user="GhostUser",
        format="mp3",
        bitrate=128,
        size_bytes=5000000,
        status="downloading",
        downloaded_at=datetime.utcnow()
    )
    db.add(download)
    db.commit()
    download_id = download.id

    # 2. Mock slskd client behaviors
    mock_get_downloads = AsyncMock(return_value=[{
        "filename": "Daft Punk - Not Like Us (Ghost).mp3",
        "username": "GhostUser",
        "bytes_transferred": 0,
        "size": 5000000,
        "state": "Downloading",
        "id": "ghost-id-123"
    }])
    mock_cancel_download = AsyncMock(return_value=True)

    mock_search = AsyncMock(return_value={"id": "new-search-id"})
    mock_get_responses = AsyncMock(return_value=[
        {
            "username": "GhostUser",
            "files": [{"filename": "Track.mp3", "size": 5000000}]
        },
        {
            "username": "NextBestUser",
            "files": [{
                "filename": "Kendrick Lamar - Not Like Us.flac",
                "size": 35000000,
                "bitRate": 1020,
                "sampleRate": 44100
            }]
        }
    ])
    mock_enqueue_download = AsyncMock(return_value=True)

    # SessionLocal Factory mock to return fresh test sessions
    mock_session_factory = MagicMock(side_effect=lambda: TestingSessionLocal())

    # We use an Event to pause and resume the infinite loop step-by-step
    step_event = asyncio.Event()

    async def mock_sleep(sec):
        await step_event.wait()
        await original_sleep(0.001)

    with patch("app.services.downloads_poller.SessionLocal", mock_session_factory), \
         patch("app.services.slskd.SlskdClient.get_downloads", mock_get_downloads), \
         patch("app.services.slskd.SlskdClient.cancel_download", mock_cancel_download), \
         patch("app.services.slskd.SlskdClient.search", mock_search), \
         patch("app.services.slskd.SlskdClient.get_search_responses", mock_get_responses), \
         patch("app.services.slskd.SlskdClient.enqueue_download", mock_enqueue_download):

        with patch("app.services.downloads_poller.asyncio.sleep", mock_sleep):
            # Start background poller task
            poller_task = asyncio.create_task(poll_downloads())

            # 1. Execute first loop iteration
            step_event.set()
            await original_sleep(0.05)
            step_event.clear()

            # First loop iteration should have registered the download id in the STALL_TRACKER
            assert download_id in STALL_TRACKER
            assert STALL_TRACKER[download_id]["bytes"] == 0

            # Manually simulate clock advancement by updating registered timestamp
            STALL_TRACKER[download_id]["time"] = datetime.utcnow() - timedelta(seconds=5)

            # 2. Execute second loop iteration to trigger Ghost Peer fallback
            step_event.set()
            await original_sleep(0.05)
            step_event.clear()

            # Cancel task
            poller_task.cancel()

    # 3. Assertions
    db_assert = TestingSessionLocal()
    old_dl = db_assert.query(DownloadHistory).filter(DownloadHistory.id == download_id).first()
    assert old_dl.status == "stalled"

    new_dl = db_assert.query(DownloadHistory).filter(
        DownloadHistory.artist == "Kendrick Lamar",
        DownloadHistory.source_user == "NextBestUser"
    ).first()
    assert new_dl is not None
    assert new_dl.status == "downloading"
    assert new_dl.format == "flac"

    db_assert.close()
    db.close()
