import pytest
import asyncio
from typing import List, Dict, Any
from unittest.mock import AsyncMock, MagicMock

from app.contracts.schemas import SearchQuery, SlskdResult
from app.services.search_ranking_service import SearchRankingService
from app.services.filename_parser import parse_filename
from app.services.beets_service import BeetsServiceClient
from app.services.fallback_search_executor import FallbackSearchExecutor


# --- Unit Tests ---

def test_query_generation():
    """
    Tests that progressive query generation creates correct permutations.
    """
    artist = "Kendrick Lamar"
    track = "Not Like Us"
    queries = SearchRankingService.generate_queries_progressive(artist, track)

    assert len(queries) > 0
    # Tier 1 query
    assert "Kendrick Lamar Not Like Us" in queries
    # Tier 2 artist broad query
    assert "Kendrick Lamar" in queries
    # Tier 3 track broad query
    assert "Not Like Us" in queries


def test_filename_parsing():
    """
    Tests filename parsing capabilities on typical Soulseek filename patterns.
    """
    # Pattern 1: Artist - Track
    parsed1 = parse_filename("Kendrick Lamar - Not Like Us.mp3")
    assert parsed1["artist"] == "Kendrick Lamar"
    assert parsed1["track"] == "Not Like Us"
    assert parsed1["format"] == "mp3"


def test_hard_rejections():
    """
    Verifies that sample packs, stems, drum kits, etc. are immediately discarded.
    """
    assert SearchRankingService.should_reject_result("Kendrick Lamar - Not Like Us stems.flac", "flac") is True
    assert SearchRankingService.should_reject_result("Hip Hop Samplepack Vol 1.wav", "wav") is True
    assert SearchRankingService.should_reject_result("Classic TR-808 Drumkit.wav", "wav") is True
    assert SearchRankingService.should_reject_result("Producer Pack - Stems & Multi-tracks.zip", "zip") is True


def test_penalty_scoring_stage():
    """
    Validates penalty deductions:
    - Remix (-20)
    - Mashup (-25)
    - Bootleg (-25)
    - DJ edit (-30)
    - Acapella (-50)
    - Instrumental (-50)
    """
    query = SearchQuery(artist="Kendrick Lamar", track="Not Like Us")

    # Candidate 1: Remix
    cand_remix = SlskdResult(
        filename="Kendrick Lamar - Not Like Us (Remix).mp3",
        size=10000000,
        username="peer",
        format="mp3",
        bitrate=320,
        sample_rate=44100,
        queue_length=0
    )
    score_details_remix = SearchRankingService.score_candidate(cand_remix, query)
    assert score_details_remix["remix_penalty"] == 20

    # Candidate 2: Mashup
    cand_mashup = SlskdResult(
        filename="Kendrick Lamar - Not Like Us (Mashup).mp3",
        size=10000000,
        username="peer",
        format="mp3",
        bitrate=320,
        sample_rate=44100,
        queue_length=0
    )
    score_details_mashup = SearchRankingService.score_candidate(cand_mashup, query)
    assert score_details_mashup["mashup_penalty"] == 25

    # Candidate 3: DJ Edit
    cand_edit = SlskdResult(
        filename="Kendrick Lamar - Not Like Us (Transition Edit).mp3",
        size=10000000,
        username="peer",
        format="mp3",
        bitrate=320,
        sample_rate=44100,
        queue_length=0
    )
    score_details_edit = SearchRankingService.score_candidate(cand_edit, query)
    assert score_details_edit["dj_edit_penalty"] == 30

    # Candidate 4: Acapella
    cand_acapella = SlskdResult(
        filename="Kendrick Lamar - Not Like Us (Acapella).mp3",
        size=10000000,
        username="peer",
        format="mp3",
        bitrate=320,
        sample_rate=44100,
        queue_length=0
    )
    score_details_acapella = SearchRankingService.score_candidate(cand_acapella, query)
    assert score_details_acapella["acapella_penalty"] == 50


def test_positive_scoring_and_ranking():
    """
    Validates positive weighting rules:
    - Exact artist match (+40)
    - Exact track match (+30)
    - Artist in folders (+10)
    - Album in folders (+10)
    - FLAC (+15)
    - Lossless (+15)
    - High bitrate MP3 (+10)
    - Clean filename (+5)
    """
    query = SearchQuery(artist="Kendrick Lamar", track="Not Like Us")

    # Perfect Original FLAC candidate on structured directory:
    # Match Artist (+40) + Match Track (+30) + Artist folder (+10) + Album folder (+10) + FLAC (+15) + Lossless (+15) + Clean Name (+5) = 125 (Capped at 100)
    cand_perfect = SlskdResult(
        filename="Music/Kendrick Lamar/Not Like Us/01 - Not Like Us.flac",
        size=35000000,
        username="audiophile",
        format="flac",
        bitrate=1020,
        sample_rate=44100,
        queue_length=0
    )
    score_details = SearchRankingService.score_candidate(cand_perfect, query)
    assert score_details["artist_score"] == 40
    assert score_details["track_score"] == 30
    assert score_details["artist_folder_bonus"] == 10
    assert score_details["album_folder_bonus"] == 10
    assert score_details["flac_bonus"] == 15
    assert score_details["lossless_bonus"] == 15
    assert score_details["clean_filename_bonus"] == 5
    assert score_details["final_score"] == 100


# --- Integration Tests ---

@pytest.mark.asyncio
async def test_beets_client_search_mocked(monkeypatch):
    """
    Integrates and tests the BeetsServiceClient querying with a mocked server response (JSON list).
    """
    client = BeetsServiceClient(api_url="http://mocked-beets:8337")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "id": 1,
            "artist": "Kendrick Lamar",
            "title": "Not Like Us",
            "album": "Not Like Us - Single",
            "year": 2024
        }
    ]

    async def mock_get(*args, **kwargs):
        return mock_response

    # Mock the httpx client's get request
    import httpx
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    results = await client.search_items('artist:"Kendrick Lamar" title:"Not Like Us"')
    assert len(results) == 1
    assert results[0]["artist"] == "Kendrick Lamar"
    assert results[0]["title"] == "Not Like Us"


# --- End-To-End Orchestration & Real-World Validation Simulation ---

@pytest.mark.asyncio
async def test_search_orchestration_e2e():
    """
    Simulates a real-world end-to-end search pipeline workflow:
    - User searches for Artist: "Kendrick Lamar", Track: "Not Like Us"
    - Strict query is simulated to return 0 results
    - Fallback queries return results (one FLAC original, one high bitrate MP3, one remix)
    - Remix penalty is applied and it drops to the bottom of the list.
    """
    mock_slskd = MagicMock()

    async def mock_search(query_str: str, **kwargs):
        return {"id": f"search_id_{query_str.replace(' ', '_')}"}

    async def mock_get_search_responses(search_id: str):
        if search_id.endswith("_Kendrick_Lamar_Not_Like_Us") or search_id.endswith("_Kendrick_Lamar"):
            return []

        if "Not_Like_Us" in search_id:
            return [
                {
                    "username": "peer_1",
                    "queueLength": 0,
                    "files": [
                        {
                            "filename": "Unknown Artist - Not Like Us (Transition Edit).flac",
                            "size": 32000000,
                            "bitRate": 1050,
                            "sampleRate": 44100
                        },
                        {
                            "filename": "Kendrick Lamar - Not Like Us.flac",
                            "size": 33000000,
                            "bitRate": 1020,
                            "sampleRate": 44100
                        },
                        {
                            "filename": "Kendrick Lamar - Not Like Us (Extended Mix).mp3",
                            "size": 11000000,
                            "bitRate": 320,
                            "sampleRate": 44100
                        }
                    ]
                }
            ]
        return []

    mock_slskd.search = mock_search
    mock_slskd.get_search_responses = mock_get_search_responses
    mock_slskd.delete_search = AsyncMock()

    ranking_service = SearchRankingService()
    executor = FallbackSearchExecutor(
        slskd_client=mock_slskd,
        search_provider=ranking_service
    )

    # Directly mock the Beets REST API calls on the beets client
    executor.beets_client.search_items = AsyncMock(return_value=[
        {
            "id": 42,
            "artist": "Kendrick Lamar",
            "title": "Not Like Us",
            "album": "Not Like Us - Single",
            "year": 2024
        }
    ])

    query_obj = SearchQuery(artist="Kendrick Lamar", track="Not Like Us")
    results = await executor.execute_search(query_obj)

    assert len(results) == 3

    # The high confidence original FLAC candidate 'Kendrick Lamar - Not Like Us.flac' has NO penalties and flac bonuses. It must be #1!
    top_result = results[0]
    assert "Not Like Us.flac" in top_result.filename
    assert top_result.score == 100

    # The remix/edit candidates must appear lower in score
    remix_result = [r for r in results if "Extended Mix" in r.filename][0]
    # MP3 + Exact Artist (+40) + Exact Track (+30) + MP3 Bitrate (+10) + Clean Structure (+5) - Remix Penalty (-20) = 65
    assert remix_result.score == 65
