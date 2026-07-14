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
