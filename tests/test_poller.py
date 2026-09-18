import os
import shutil
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import DownloadHistory, Wishlist
from app.services.downloads_poller import find_file_recursively, clean_empty_directories, poll_downloads

@pytest.fixture
def temp_dirs(tmp_path):
    download_dir = tmp_path / "downloads"
    singles_dir = tmp_path / "singles"
    os.makedirs(download_dir)
    os.makedirs(singles_dir)
    return download_dir, singles_dir

def test_find_file_recursively(temp_dirs):
    download_dir, singles_dir = temp_dirs
    sub_dir = download_dir / "user1" / "album"
    os.makedirs(sub_dir)
    dummy_file = sub_dir / "artist - song.mp3"
    with open(dummy_file, "w") as f:
        f.write("dummy-data")

    found = find_file_recursively(str(download_dir), "artist - song.mp3")
    assert found is not None
    assert "artist - song.mp3" in found

def test_clean_empty_directories(temp_dirs):
    download_dir, singles_dir = temp_dirs
    empty_sub = download_dir / "empty_user" / "empty_album"
    os.makedirs(empty_sub)

    clean_empty_directories(str(download_dir))
    assert not os.path.exists(empty_sub)

@pytest.mark.asyncio
@patch("app.services.downloads_poller.SessionLocal")
@patch("app.services.downloads_poller.SlskdClient.get_downloads", new_callable=AsyncMock)
@patch("asyncio.sleep", side_effect=ValueError("stop loop"))
async def test_poll_downloads_loop_completed(mock_sleep, mock_get_downloads, mock_session_local, temp_dirs):
    download_dir, singles_dir = temp_dirs

    from app.config import settings
    settings.DOWNLOADS_PATH = str(download_dir)
    settings.SINGLES_PATH = str(singles_dir)
    settings.MUSIC_LIBRARY_PATH = str(singles_dir)

    mock_db = MagicMock()
    mock_session_local.return_value = mock_db

    dl_entry = DownloadHistory(
        id=1,
        artist="Daft Punk",
        track="One More Time",
        filename="song.mp3",
        source_user="user1",
        status="downloading",
        size_bytes=5000000
    )
    mock_db.query().filter().all.return_value = [dl_entry]

    wishlist_item = Wishlist(artist="Daft Punk", track="One More Time", status="searching")
    mock_db.query().filter().first.return_value = wishlist_item

    mock_get_downloads.return_value = [
        {
            "filename": "Daft Punk - One More Time.mp3",
            "username": "user1",
            "state": "Completed, Succeeded",
            "bytes_transferred": 5000000,
            "size": 5000000
        }
    ]

    os.makedirs(os.path.join(download_dir, "user1"), exist_ok=True)
    completed_file = os.path.join(download_dir, "user1", "song.mp3")
    with open(completed_file, "w") as f:
        f.write("audio-content")

    with pytest.raises(ValueError, match="stop loop"):
        await poll_downloads()

    moved_file = os.path.join(singles_dir, "song.mp3")
    assert os.path.exists(moved_file)
    assert dl_entry.status == "completed"
    assert wishlist_item.status == "downloaded"
    mock_db.commit.assert_called()

@pytest.mark.asyncio
@patch("app.services.downloads_poller.SessionLocal")
@patch("app.services.downloads_poller.SlskdClient.get_downloads", new_callable=AsyncMock)
@patch("asyncio.sleep", side_effect=ValueError("stop loop"))
async def test_poll_downloads_loop_failed(mock_sleep, mock_get_downloads, mock_session_local, temp_dirs):
    download_dir, singles_dir = temp_dirs

    from app.config import settings
    settings.DOWNLOADS_PATH = str(download_dir)
    settings.SINGLES_PATH = str(singles_dir)
    settings.MUSIC_LIBRARY_PATH = str(singles_dir)

    mock_db = MagicMock()
    mock_session_local.return_value = mock_db

    dl_entry = DownloadHistory(
        id=1,
        artist="Daft Punk",
        track="One More Time",
        filename="song.mp3",
        source_user="user1",
        status="downloading",
        size_bytes=5000000
    )
    mock_db.query().filter().all.return_value = [dl_entry]

    wishlist_item = Wishlist(artist="Daft Punk", track="One More Time", status="searching")
    mock_db.query().filter().first.return_value = wishlist_item

    mock_get_downloads.return_value = [
        {
            "filename": "song.mp3",
            "username": "user1",
            "state": "Cancelled",
            "bytes_transferred": 0,
            "size": 5000000
        }
    ]

    with pytest.raises(ValueError, match="stop loop"):
        await poll_downloads()

    assert dl_entry.status == "failed"
    assert wishlist_item.status == "failed"
    mock_db.commit.assert_called()

@pytest.mark.asyncio
@patch("app.services.downloads_poller.SessionLocal")
@patch("app.services.downloads_poller.SlskdClient.get_downloads", new_callable=AsyncMock)
@patch("asyncio.sleep", side_effect=ValueError("stop loop"))
async def test_poll_downloads_loop_with_directories(mock_sleep, mock_get_downloads, mock_session_local, temp_dirs):
    download_dir, singles_dir = temp_dirs

    from app.config import settings
    settings.DOWNLOADS_PATH = str(download_dir)
    settings.SINGLES_PATH = str(singles_dir)
    settings.MUSIC_LIBRARY_PATH = str(singles_dir)

    mock_db = MagicMock()
    mock_session_local.return_value = mock_db

    dl_entry = DownloadHistory(
        id=1,
        artist="Daft Punk",
        track="One More Time",
        filename="song.mp3",
        source_user="user1",
        status="downloading"
    )
    mock_db.query().filter().all.return_value = [dl_entry]

    mock_get_downloads.return_value = {
        "directories": [
            {
                "directory": "user1/album",
                "files": [
                    {
                        "filename": "song.mp3",
                        "username": "user1",
                        "state": "Completed, Succeeded"
                    }
                ]
            }
        ]
    }

    os.makedirs(os.path.join(download_dir, "user1"), exist_ok=True)
    completed_file = os.path.join(download_dir, "user1", "song.mp3")
    with open(completed_file, "w") as f:
        f.write("audio-content")

    with pytest.raises(ValueError, match="stop loop"):
        await poll_downloads()

    moved_file = os.path.join(singles_dir, "song.mp3")
    assert os.path.exists(moved_file)
