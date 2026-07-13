import os
import pytest
from unittest.mock import MagicMock, patch
from app.services.tagger import read_tags, write_tags

@patch("os.path.exists")
def test_read_tags_file_not_found(mock_exists):
    mock_exists.return_value = False
    tags = read_tags("nonexistent.mp3")
    assert tags["title"] == ""
    assert tags["artist"] == ""

@patch("os.path.exists")
@patch("app.services.tagger.FLAC")
def test_read_tags_flac_success(mock_flac, mock_exists):
    mock_exists.return_value = True

    # Setup mock FLAC object
    mock_audio = MagicMock()
    mock_audio.get.side_effect = lambda key, default: [f"mock_{key}"] if key != "pictures" else []
    mock_audio.pictures = []
    mock_flac.return_value = mock_audio

    tags = read_tags("test.flac")
    assert tags["title"] == "mock_title"
    assert tags["artist"] == "mock_artist"
    assert tags["has_cover"] is False

@patch("os.path.exists")
@patch("app.services.tagger.MP3")
def test_read_tags_mp3_success(mock_mp3, mock_exists):
    mock_exists.return_value = True

    mock_audio = MagicMock()
    mock_audio.tags = {
        "TIT2": "mock_title",
        "TPE1": "mock_artist",
        "TALB": "mock_album"
    }
    mock_mp3.return_value = mock_audio

    tags = read_tags("test.mp3")
    assert tags["title"] == "mock_title"
    assert tags["artist"] == "mock_artist"
    assert tags["has_cover"] is False

@patch("os.path.exists")
@patch("app.services.tagger.FLAC")
def test_write_tags_flac_success(mock_flac, mock_exists):
    mock_exists.return_value = True
    mock_audio = MagicMock()
    mock_flac.return_value = mock_audio

    success = write_tags(
        filepath="test.flac",
        title="New Title",
        artist="New Artist",
        album="New Album",
        year="2024",
        genre="Synthwave"
    )

    assert success is True
    mock_audio.__setitem__.assert_any_call("title", "New Title")
    mock_audio.__setitem__.assert_any_call("artist", "New Artist")
    mock_audio.__setitem__.assert_any_call("album", "New Album")
    mock_audio.__setitem__.assert_any_call("date", "2024")
    mock_audio.__setitem__.assert_any_call("genre", "Synthwave")
    mock_audio.save.assert_called_once()

@patch("os.path.exists")
@patch("app.services.tagger.MP3")
def test_write_tags_mp3_success(mock_mp3, mock_exists):
    mock_exists.return_value = True
    mock_audio = MagicMock()
    mock_tags = MagicMock()
    mock_audio.tags = mock_tags
    mock_mp3.return_value = mock_audio

    success = write_tags(
        filepath="test.mp3",
        title="New Title",
        artist="New Artist",
        album="New Album"
    )
    assert success is True
    mock_tags.__setitem__.assert_called()

@patch("os.path.exists")
@patch("app.services.tagger.MP4")
def test_write_tags_m4a_success(mock_m4a, mock_exists):
    mock_exists.return_value = True
    mock_audio = MagicMock()
    mock_m4a.return_value = mock_audio

    success = write_tags(
        filepath="test.m4a",
        title="New Title",
        artist="New Artist",
        album="New Album"
    )
    assert success is True
    mock_audio.__setitem__.assert_any_call("\xa9nam", ["New Title"])
    mock_audio.__setitem__.assert_any_call("\xa9ART", ["New Artist"])
    mock_audio.__setitem__.assert_any_call("\xa9alb", ["New Album"])
    mock_audio.save.assert_called_once()

@patch("os.path.exists")
@patch("app.services.tagger.OggVorbis")
def test_write_tags_ogg_success(mock_ogg, mock_exists):
    mock_exists.return_value = True
    mock_audio = MagicMock()
    mock_ogg.return_value = mock_audio

    success = write_tags(
        filepath="test.ogg",
        title="New Title",
        artist="New Artist",
        album="New Album"
    )
    assert success is True
    mock_audio.__setitem__.assert_any_call("title", "New Title")
    mock_audio.__setitem__.assert_any_call("artist", "New Artist")
    mock_audio.__setitem__.assert_any_call("album", "New Album")
    mock_audio.save.assert_called_once()
