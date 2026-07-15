import pytest
from app.services.filename_parser import parse_filename

def test_parse_artist_track():
    res = parse_filename("Kendrick Lamar - Not Like Us.flac")
    assert res["artist"] == "Kendrick Lamar"
    assert res["track"] == "Not Like Us"
    assert res["format"] == "flac"

def test_parse_artist_album_track():
    res = parse_filename("Kendrick Lamar - Damn - Humble.mp3")
    assert res["artist"] == "Kendrick Lamar"
    assert res["album"] == "Damn"
    assert res["track"] == "Humble"
    assert res["format"] == "mp3"

def test_parse_bracket_noise():
    res = parse_filename("Artist - Track [FLAC] [320kbps] (Official Video) [Lossless].wav")
    assert res["artist"] == "Artist"
    assert res["track"] == "Track"
    assert res["format"] == "wav"

def test_parse_track_prefixes():
    res = parse_filename("01 - Artist - Track.m4a")
    assert res["artist"] == "Artist"
    assert res["track"] == "Track"
    assert res["track_number"] == 1
    assert res["format"] == "m4a"

def test_parse_multi_disc():
    res = parse_filename("CD1 - 03 - Artist - Album - Track.flac")
    assert res["artist"] == "Artist"
    assert res["album"] == "Album"
    assert res["track"] == "Track"
    assert res["disc_number"] == 1
    assert res["track_number"] == 3
    assert res["format"] == "flac"

def test_parse_scene_release():
    res = parse_filename("Kendrick_Lamar-Not_Like_Us-2024-GRP.flac")
    assert res["artist"] == "Kendrick Lamar"
    assert res["track"] == "Not Like Us"
    assert res["year"] == 2024
    assert res["format"] == "flac"

def test_parse_scene_release_no_year():
    res = parse_filename("Kendrick.Lamar-Not.Like.Us.mp3")
    assert res["artist"] == "Kendrick Lamar"
    assert res["track"] == "Not Like Us"
    assert res["format"] == "mp3"

def test_parse_raw_soulseek_path_structured():
    # Test path: @@jqxww\share\Electronic\Flying Lotus\You are dead!\05 - Never Catch Me feat Kendrick Lamar
    res = parse_filename(r"@@jqxww\share\Electronic\Flying Lotus\You are dead!\05 - Never Catch Me feat Kendrick Lamar.flac")
    assert res["artist"] == "Flying Lotus"
    assert res["album"] == "You are dead!"
    assert res["track"] == "Never Catch Me"
    assert "Kendrick Lamar" in res["featured_artists"]
    assert res["format"] == "flac"

def test_parse_acapella_and_remixes():
    res = parse_filename("Daft Punk - One More Time (Acapella Vocal Mix).mp3")
    assert res["artist"] == "Daft Punk"
    assert "One More Time" in res["track"]
    assert res["is_acapella"] is True
    assert res["is_remix"] is True

def test_parse_featured_artists():
    res = parse_filename("Humble (feat. Rihanna and SZA).flac")
    assert res["track"] == "Humble"
    assert "Rihanna" in res["featured_artists"]
    assert "SZA" in res["featured_artists"]
