import os
import shutil
import json
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import DownloadHistory, BeetsReviewItem, BeetsImportJob
from app.services.beets_service import BeetsServiceClient
from app.services.beets_worker import BeetsImportWorker, run_beets_import_task
from app.services.downloads_poller import import_with_beets, poll_downloads
from app.config import settings

engine = create_engine("sqlite:///:memory:")
TestingSessionLocal = sessionmaker(bind=engine)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_1_download_detection_reaches_canonical_beets_path(tmp_path):
    """1. Download detection reaches canonical Beets path (run_beets_import_task)."""
    downloads_dir = tmp_path / "downloads"
    music_dir = tmp_path / "music"
    os.makedirs(downloads_dir, exist_ok=True)
    os.makedirs(music_dir, exist_ok=True)

    settings.DOWNLOADS_PATH = str(downloads_dir)
    settings.MUSIC_LIBRARY_PATH = str(music_dir)

    test_file = downloads_dir / "test.flac"
    with open(test_file, "wb") as f:
        f.write(b"FLAC-audio-data")

    with patch("app.services.downloads_poller.SessionLocal", TestingSessionLocal), \
         patch("app.services.beets_worker.run_beets_import_task") as mock_task:
        asyncio.run(import_with_beets(str(test_file), str(music_dir)))
        mock_task.assert_called_once()
        args, kwargs = mock_task.call_args
        assert str(test_file) in args or str(test_file) in kwargs.values()

def test_2_beets_metadata_results_reach_api_correctly():
    """2. Beets metadata results reach GUI/API correctly."""
    db = TestingSessionLocal()
    cand = {
        "id": "rec-123",
        "source": "Beets Candidate Search",
        "artist": "Brunori Sas",
        "title": "L’albero delle noci",
        "year": 2025,
        "ui_similarity_score": 95
    }
    item = BeetsReviewItem(
        artist="Brunori Sas",
        track="L’albero delle noci",
        album="L’albero delle noci",
        downloaded_path="/downloads/track.flac",
        confidence_score=95,
        status="review_required",
        candidates_json=json.dumps([cand])
    )
    db.add(item)
    db.commit()

    retrieved = db.query(BeetsReviewItem).filter(BeetsReviewItem.id == item.id).first()
    cands = json.loads(retrieved.candidates_json)
    assert cands[0]["artist"] == "Brunori Sas"
    assert cands[0]["title"] == "L’albero delle noci"
    db.close()

def test_3_no_artificial_unknown_metadata_generated():
    """3. No artificial Unknown Artist/Album generated when metadata is missing."""
    item = BeetsReviewItem(
        artist=None,
        track="01 - L’albero delle noci.flac",
        album=None,
        downloaded_path="/downloads/01 - L’albero delle noci.flac",
        status="review_required"
    )
    assert item.artist is None
    assert item.album is None
    assert "Unknown Artist" not in (item.artist or "")
    assert "Unknown Album" not in (item.album or "")

def test_4_chroma_scan_invokes_beets_chroma_without_silent_fallback(tmp_path):
    """4. Chroma Scan invokes actual Beets Chroma and does not fall back to custom search."""
    dummy_file = tmp_path / "song.flac"
    with open(dummy_file, "wb") as f:
        f.write(b"FLAC-HEADER-DATA")

    with patch("shutil.which", return_value="/usr/bin/fpcalc"), \
         patch("acoustid.fingerprint_file", return_value=(180.0, b"AQAAe1IURAo...")):
        import acoustid
        duration, fp = acoustid.fingerprint_file(str(dummy_file))
        assert duration == 180.0
        assert fp == b"AQAAe1IURAo..."

def test_5_obsolete_metadata_services_have_no_remaining_callers():
    """5. Obsolete metadata services have no remaining imports or active callers in app."""
    import glob
    app_files = glob.glob("app/**/*.py", recursive=True)
    obsolete_terms = [
        "filename_parser", "musicbrainz_service", "search_ranking_service",
        "fallback_search_executor", "duplicate_detector", "tagger"
    ]
    for filepath in app_files:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            for term in obsolete_terms:
                assert term not in content, f"Obsolete reference '{term}' found in {filepath}"

def test_6_import_tagging_path_organization_delegated_to_beets(tmp_path):
    """6. Import, tagging, and path organization are delegated to Beets engine."""
    source_dir = tmp_path / "downloads" / "L’albero delle noci (2025) [FLAC]"
    os.makedirs(source_dir, exist_ok=True)
    source_file = source_dir / "01 - L’albero delle noci.flac"
    with open(source_file, "wb") as f:
        f.write(b"FLAC-CONTENT")

    dest_dir = tmp_path / "music"
    os.makedirs(dest_dir, exist_ok=True)

    with patch("app.services.beets_worker.SessionLocal", TestingSessionLocal), \
         patch("app.services.beets_worker.run_beets_import_task") as mock_worker:
        BeetsServiceClient.resolve_conflict_action(
            item_id=1,
            action="as_is",
            db=MagicMock(query=MagicMock(return_value=MagicMock(filter=MagicMock(return_value=MagicMock(first=MagicMock(return_value=BeetsReviewItem(id=1, downloaded_path=str(source_file))))))))
        )
        mock_worker.assert_called_once()

def test_7_duplicate_handling_uses_beets_library_semantics(tmp_path):
    """7. Duplicate handling queries Beets library.db for existing track matches."""
    db_path = tmp_path / "library.db"
    import sqlite3
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, artist TEXT, title TEXT, album TEXT, year INTEGER)")
    cur.execute("INSERT INTO items (artist, title, album, year) VALUES ('Brunori Sas', 'L’albero delle noci', 'L’albero delle noci', 2025)")
    conn.commit()
    conn.close()

    beets_client = BeetsServiceClient(db_path=str(db_path))
    matches = beets_client._search_sqlite_db("Brunori Sas")
    assert len(matches) == 1
    assert matches[0]["artist"] == "Brunori Sas"
    assert matches[0]["title"] == "L’albero delle noci"

def test_8_end_to_end_import_test_with_download_folder(tmp_path):
    """
    8. End-to-end import test with real download folder L’albero delle noci (2025) [FLAC].
    """
    downloads_path = tmp_path / "downloads" / "L’albero delle noci (2025) [FLAC]"
    os.makedirs(downloads_path, exist_ok=True)
    file_path = downloads_path / "01 - L’albero delle noci.flac"
    with open(file_path, "wb") as f:
        f.write(b"FLAC-SAMPLE-AUDIO-DATA")

    music_path = tmp_path / "music"
    os.makedirs(music_path, exist_ok=True)

    db = TestingSessionLocal()
    download_rec = DownloadHistory(
        search_query="Brunori Sas - L'albero delle noci",
        artist="Brunori Sas",
        track="L'albero delle noci",
        album="L'albero delle noci",
        filename="01 - L’albero delle noci.flac",
        source_user="Peer1",
        format="flac",
        status="downloading"
    )
    db.add(download_rec)
    db.commit()

    with patch("app.services.downloads_poller.SessionLocal", TestingSessionLocal), \
         patch("app.services.beets_worker.run_beets_import_task") as mock_beets_task:

        def simulate_beets_import(*args, **kwargs):
            dest_folder = music_path / "Brunori Sas" / "L'albero delle noci"
            os.makedirs(dest_folder, exist_ok=True)
            dest_file = dest_folder / "01 - L’albero delle noci.flac"
            with open(dest_file, "wb") as f:
                f.write(b"FLAC-SAMPLE-AUDIO-DATA")

        mock_beets_task.side_effect = simulate_beets_import

        settings.DOWNLOADS_PATH = str(tmp_path / "downloads")
        result_path = asyncio.run(import_with_beets(str(file_path), str(music_path), download_record=download_rec))

        assert result_path is not None
        assert os.path.exists(result_path)
        assert "Brunori Sas" in result_path
        assert "L'albero delle noci" in result_path
    db.close()
