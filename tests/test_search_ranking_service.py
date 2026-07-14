import pytest
from app.services.search_ranking_service import SearchRankingService

def test_generate_queries():
    queries = SearchRankingService.generate_queries("Kendrick Lamar", "Not Like Us", "Damn")
    assert "Kendrick Lamar Not Like Us" in queries
    assert '"Kendrick Lamar" "Not Like Us"' in queries
    assert "Kendrick Lamar Damn Not Like Us" in queries

def test_score_exact_match():
    # Exact match for everything plus high codec/bitrate properties
    item = {
        "filename": "Kendrick Lamar - Damn - Humble.flac",
        "format": "flac",
        "bitrate": 1050,
        "sample_rate": 44100,
        "size": 35 * 1024 * 1024
    }
    score = SearchRankingService.score_result(
        item,
        target_artist="Kendrick Lamar",
        target_track="Humble",
        target_album="Damn"
    )
    # Exact artist (30) + Exact track (30) + Exact album (10) + Codec (15) + Bitrate (10) + Sample (3) + Size (5) = 103 -> capped at 100
    assert score == 100

def test_score_partial_mp3():
    item = {
        "filename": "01 - Kendrick Scott - Something.mp3",
        "format": "mp3",
        "bitrate": 320,
        "sample_rate": 44100,
        "size": 8 * 1024 * 1024
    }
    score = SearchRankingService.score_result(
        item,
        target_artist="Kendrick Lamar",
        target_track="Humble"
    )
    # Codec mp3 (8) + Bitrate 320 (8) + Sample 44.1 (3) + Size (5) = 24
    assert score == 24

def test_score_stub_file():
    item = {
        "filename": "Kendrick Lamar - Not Like Us.flac",
        "format": "flac",
        "bitrate": 1000,
        "sample_rate": 44100,
        "size": 500 * 1024 # 500 KB (too small)
    }
    score = SearchRankingService.score_result(item, "Kendrick Lamar", "Not Like Us")
    # Exact artist (30) + Exact track (30) + Codec (15) + Bitrate (10) + Sample (3) + Size (0 because <=1MB) = 88
    assert score == 88

def test_score_various_formats_and_rates():
    # Test m4a codec, high sample rate, medium bitrate
    item1 = {
        "filename": "Artist - Track.m4a",
        "format": "m4a",
        "bitrate": 256,
        "sample_rate": 96000,
        "size": 12 * 1024 * 1024
    }
    score1 = SearchRankingService.score_result(item1, "Artist", "Track")
    # Exact artist (30) + Exact track (30) + m4a codec (10) + bitrate 256 (6) + sample_rate 96k (5) + size (5) = 86
    assert score1 == 86

    # Test unknown bitrate/sample rate fallback for lossless
    item2 = {
        "filename": "Artist - Track.flac",
        "format": "flac",
        "bitrate": 0,
        "sample_rate": 0,
        "size": 25 * 1024 * 1024
    }
    score2 = SearchRankingService.score_result(item2, "Artist", "Track")
    # Exact artist (30) + Exact track (30) + flac codec (15) + fallback bitrate (10) + fallback sample (3) + size (5) = 93
    assert score2 == 93

    # Test other formats and low bitrates
    item3 = {
        "filename": "Artist - Track.ogg",
        "format": "ogg",
        "bitrate": 128,
        "sample_rate": 22050,
        "size": 4 * 1024 * 1024
    }
    score3 = SearchRankingService.score_result(item3, "Artist", "Track")
    # Exact artist (30) + Exact track (30) + other codec (5) + bitrate 128 (2) + sample 22k (2) + size (5) = 74
    assert score3 == 74
