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
    score_dict = SearchRankingService.score_result(
        item,
        target_artist="Kendrick Lamar",
        target_track="Humble",
        target_album="Damn"
    )
    # Exact artist (50) + Exact track (30) + Exact album (10) + FLAC (20) + Size (5) = 115 -> capped at 100
    assert score_dict["final_score"] == 100
    assert score_dict["classification"] == "PRIMARY_ARTIST_MATCH"
    assert score_dict["artist_score"] == 50

def test_score_partial_mp3():
    item = {
        "filename": "01 - Kendrick Scott - Something.mp3",
        "format": "mp3",
        "bitrate": 320,
        "sample_rate": 44100,
        "size": 8 * 1024 * 1024
    }
    score_dict = SearchRankingService.score_result(
        item,
        target_artist="Kendrick Lamar",
        target_track="Humble"
    )
    # Partial artist (15) + No track (0) + MP3 320 (10) + Size (2) = 27
    assert score_dict["final_score"] == 27
    assert score_dict["classification"] == "PARTIAL_MATCH"
    assert score_dict["artist_score"] == 15

def test_score_featured_artist():
    item = {
        "filename": "Metro Boomin - Like That (feat. Kendrick Lamar).mp3",
        "format": "mp3",
        "bitrate": 320,
        "sample_rate": 44100,
        "size": 12 * 1024 * 1024
    }
    score_dict = SearchRankingService.score_result(
        item,
        target_artist="Kendrick Lamar",
        target_track="Like That"
    )
    # Featured Artist (35) + Exact track (30) + MP3 320 (10) + Size (5) = 80
    assert score_dict["final_score"] == 80
    assert score_dict["classification"] == "FEATURED_ARTIST_MATCH"
    assert score_dict["artist_score"] == 35

def test_score_stub_file():
    item = {
        "filename": "Kendrick Lamar - Not Like Us.flac",
        "format": "flac",
        "bitrate": 1000,
        "sample_rate": 44100,
        "size": 500 * 1024 # 500 KB (too small)
    }
    score_dict = SearchRankingService.score_result(item, "Kendrick Lamar", "Not Like Us")
    # Exact artist (50) + Exact track (30) + FLAC (20) + Size (0 because <=1MB) = 100
    assert score_dict["final_score"] == 100
    assert score_dict["classification"] == "PRIMARY_ARTIST_MATCH"

def test_should_reject_result():
    # Poster / Artwork rejection
    assert SearchRankingService.should_reject_result("cover.jpg", "jpg") is True
    assert SearchRankingService.should_reject_result("Kendrick Lamar - Poster - front.png", "png") is True
    # Non-music extension
    assert SearchRankingService.should_reject_result("track.txt", "txt") is True
    # Sample packs / drum kits
    assert SearchRankingService.should_reject_result("Drums Stem Loop Kit.wav", "wav") is True
    # Keygen / crack rejection
    assert SearchRankingService.should_reject_result("crack.exe", "exe") is True
    # Hex hashes/blobs
    assert SearchRankingService.should_reject_result("ab12cd34ef56ab12cd34ef56ab12cd34.mp3", "mp3") is True
    # Real song
    assert SearchRankingService.should_reject_result("01 - Kendrick Lamar - Not Like Us.flac", "flac") is False
