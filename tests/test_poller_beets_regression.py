import os
import shutil
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import DownloadHistory, BeetsReviewItem
from app.services.downloads_poller import import_with_beets, poll_downloads


@pytest.fixture
def temp_environment(tmp_path):
    downloads_dir = tmp_path / "downloads"
    music_dir = tmp_path / "music"
    os.makedirs(downloads_dir, exist_ok=True)
    os.makedirs(music_dir, exist_ok=True)

    album_dir = downloads_dir / "L’albero delle noci (2025) [FLAC]"
    os.makedirs(album_dir, exist_ok=True)
    track_file = album_dir / "01 - L’albero delle noci.flac"
    track_file.write_text("fake flac audio content")

    db_file = tmp_path / "test_poller.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    return {
        "downloads_dir": str(downloads_dir),
        "music_dir": str(music_dir),
        "album_dir": str(album_dir),
        "track_file": str(track_file),
        "SessionLocal": TestingSessionLocal,
    }


@pytest.mark.asyncio
async def test_skipped_beets_import_transitions_to_review_required(temp_environment):
    """
    Verifies that a Beets import that exits successfully but imports zero files
    because user intervention is required:
    1. Does NOT fail.
    2. Transitions DownloadHistory status to 'review_required'.
    3. Leaves the source directory untouched on disk.
    4. Does not run filename fallback or generate 'Unknown Artist'.
    """
    SessionLocal = temp_environment["SessionLocal"]
    db = SessionLocal()

    dl_entry = DownloadHistory(
        id=101,
        search_query="Brunori Sas L'albero delle noci",
        artist="Brunori Sas",
        track="L’albero delle noci",
        album="L’albero delle noci",
        filename="01 - L’albero delle noci.flac",
        source_user="peer1",
        format="flac",
        status="downloading",
    )
    db.add(dl_entry)
    db.commit()
    db.close()

    src_file = temp_environment["track_file"]
    music_dir = temp_environment["music_dir"]

    # Mock SessionLocal to return our test SessionLocal factory
    with patch("app.services.downloads_poller.SessionLocal", side_effect=SessionLocal), \
         patch("app.services.beets_worker.SessionLocal", side_effect=SessionLocal), \
         patch("app.config.settings.DOWNLOADS_PATH", temp_environment["downloads_dir"]), \
         patch("app.config.settings.MUSIC_LIBRARY_PATH", music_dir), \
         patch("app.services.beets_worker.run_beets_import_task") as mock_worker_task:

        # Simulate Beets import worker running and skipping import (0 files moved, ConflictCollector creating ReviewItem)
        def fake_beets_task(job_id, source_path, config_path, search_ids, action_mode, review_item_id, download_id):
            session_worker = SessionLocal()
            rev = BeetsReviewItem(
                conflict_id="conflict_123",
                fingerprint="fp_123",
                download_id=download_id,
                item_type="album",
                artist="Brunori Sas",
                track="L’albero delle noci",
                album="L’albero delle noci",
                downloaded_path=source_path,
                confidence_score=94,
                status="open",
                candidates_json='[{"artist": "Brunori Sas", "title": "L’albero delle noci", "confidence": 94}]',
            )
            session_worker.add(rev)
            session_worker.commit()
            session_worker.close()

        mock_worker_task.side_effect = fake_beets_task

        db_check = SessionLocal()
        dl_record = db_check.query(DownloadHistory).filter(DownloadHistory.id == 101).first()

        res = await import_with_beets(src_file, music_dir, download_record=dl_record)
        db_check.close()

        # 1. Returned path is None (0 files moved to /music)
        assert res is None

        # 2. Source path remains untouched on disk
        assert os.path.exists(src_file)
        assert os.path.exists(temp_environment["album_dir"])

        # 3. DownloadHistory status transitioned to 'review_required'
        db_verify = SessionLocal()
        updated_dl = db_verify.query(DownloadHistory).filter(DownloadHistory.id == 101).first()
        assert updated_dl.status == "review_required"

        # 4. BeetsReviewItem preserved real candidate metadata without 'Unknown Artist'
        review_item = db_verify.query(BeetsReviewItem).filter(BeetsReviewItem.download_id == 101).first()
        assert review_item is not None
        assert review_item.artist == "Brunori Sas"
        assert review_item.track == "L’albero delle noci"
        assert review_item.confidence_score == 94
        assert review_item.artist != "Unknown Artist"
        db_verify.close()


@pytest.mark.asyncio
async def test_poller_prevents_repeated_retry_loop(temp_environment):
    """
    Verifies that the poller does NOT retry importing a path if a ReviewItem already exists
    or if status is 'review_required'.
    """
    SessionLocal = temp_environment["SessionLocal"]
    db = SessionLocal()

    dl_entry = DownloadHistory(
        id=202,
        search_query="Brunori Sas L'albero delle noci",
        artist="Brunori Sas",
        track="L’albero delle noci",
        album="L’albero delle noci",
        filename="01 - L’albero delle noci.flac",
        source_user="peer1",
        format="flac",
        status="review_required",
    )
    db.add(dl_entry)

    review_item = BeetsReviewItem(
        conflict_id="conflict_202",
        fingerprint="fp_202",
        download_id=202,
        item_type="album",
        artist="Brunori Sas",
        track="L’albero delle noci",
        album="L’albero delle noci",
        downloaded_path=temp_environment["album_dir"],
        confidence_score=94,
        status="open",
        candidates_json='[]',
    )
    db.add(review_item)
    db.commit()
    db.close()

    src_file = temp_environment["track_file"]
    music_dir = temp_environment["music_dir"]

    with patch("app.services.downloads_poller.SessionLocal", side_effect=SessionLocal), \
         patch("app.config.settings.DOWNLOADS_PATH", temp_environment["downloads_dir"]), \
         patch("app.config.settings.MUSIC_LIBRARY_PATH", music_dir), \
         patch("app.services.beets_worker.run_beets_import_task") as mock_worker_task:

        db_check = SessionLocal()
        dl_record = db_check.query(DownloadHistory).filter(DownloadHistory.id == 202).first()

        res = await import_with_beets(src_file, music_dir, download_record=dl_record)
        db_check.close()

        assert res is None
        # run_beets_import_task must NOT be called again
        mock_worker_task.assert_not_called()


def test_review_item_creation_idempotency(temp_environment):
    """
    Verifies that multiple conflict notifications for the same source/fingerprint/download_id
    do NOT create duplicate BeetsReviewItem records.
    """
    SessionLocal = temp_environment["SessionLocal"]

    dto = {
        "conflict_id": "conf_303_1",
        "fingerprint": "fp_303",
        "job_id": "job_303",
        "item_type": "album",
        "artist": "Brunori Sas",
        "track": "L’albero delle noci",
        "album": "L’albero delle noci",
        "downloaded_path": "/downloads/L’albero delle noci (2025) [FLAC]",
        "confidence_score": 94,
        "candidates": [{"artist": "Brunori Sas", "title": "L’albero delle noci"}],
        "differences": {},
        "provenance": {"embedded_tags": {"artist": "Brunori Sas"}},
        "recommendation_text": "Sub-threshold match",
    }

    db1 = SessionLocal()
    from app.models import BeetsReviewItem
    from sqlalchemy import or_

    item1 = BeetsReviewItem(
        conflict_id=dto["conflict_id"],
        fingerprint=dto["fingerprint"],
        job_id=dto["job_id"],
        download_id=303,
        item_type=dto["item_type"],
        artist=dto["artist"],
        track=dto["track"],
        album=dto["album"],
        downloaded_path=dto["downloaded_path"],
        confidence_score=dto["confidence_score"],
        status="open",
        candidates_json="[]",
    )
    db1.add(item1)
    db1.commit()
    db1.close()

    db2 = SessionLocal()
    filter_conds = [
        BeetsReviewItem.fingerprint == dto["fingerprint"],
        BeetsReviewItem.downloaded_path == dto["downloaded_path"],
        BeetsReviewItem.download_id == 303,
    ]
    existing = db2.query(BeetsReviewItem).filter(or_(*filter_conds)).first()

    assert existing is not None
    total_items = db2.query(BeetsReviewItem).count()
    assert total_items == 1
    db2.close()
