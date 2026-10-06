import os
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

# Force settings timeout for tests
os.environ["GHOST_PEER_TIMEOUT_SEC"] = "1"

from app.database import Base, SessionLocal, engine
from app.models import DownloadHistory, Wishlist, CacheEntry
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

    mock_session_factory = MagicMock(side_effect=lambda: TestingSessionLocal())

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
            poller_task = asyncio.create_task(poll_downloads())

            step_event.set()
            await original_sleep(0.05)
            step_event.clear()

            assert download_id in STALL_TRACKER
            assert STALL_TRACKER[download_id]["bytes"] == 0

            STALL_TRACKER[download_id]["time"] = datetime.utcnow() - timedelta(seconds=5)

            step_event.set()
            await original_sleep(0.05)
            step_event.clear()

            poller_task.cancel()

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
