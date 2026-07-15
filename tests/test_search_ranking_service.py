import pytest
from app.services.search_ranking_service import SearchRankingService

def test_generate_queries():
    queries = SearchRankingService.generate_queries("Kendrick Lamar", "Not Like Us")
    assert '"Kendrick Lamar" Not Like Us' in queries
    assert 'Kendrick Lamar Not Like Us' in queries

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
    # Exact artist (50) + Exact track (30) + Exact album (10) + FLAC (20) + Size (5) = 115 -> capped at 100
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
    # Partial artist (10) + No track (0) + MP3 320 (10) + Size (2) = 22
    assert score == 22

def test_score_stub_file():
    item = {
        "filename": "Kendrick Lamar - Not Like Us.flac",
        "format": "flac",
        "bitrate": 1000,
        "sample_rate": 44100,
        "size": 500 * 1024 # 500 KB (too small)
    }
    score = SearchRankingService.score_result(item, "Kendrick Lamar", "Not Like Us")
    # Exact artist (50) + Exact track (30) + FLAC (20) + Size (0 because <=1MB) = 100
    assert score == 100
