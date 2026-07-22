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
    # Strict / exact queries
    assert "Kendrick Lamar Not Like Us" in queries
    assert '"Kendrick Lamar" Not Like Us' in queries
    assert '"Kendrick Lamar" "Not Like Us"' in queries
    # Fallback track query
    assert "Not Like Us" in queries
    # Fallback artist query
    assert "Kendrick Lamar" in queries
    # First word of artist
    assert "Kendrick" in queries
    # Partials of track
    assert "Not Like" in queries
    assert "Not" in queries


def test_filename_parsing():
    """
    Tests filename parsing capabilities on typical Soulseek filename patterns.
    """
    # Pattern 1: Artist - Track
    parsed1 = parse_filename("Kendrick Lamar - Not Like Us.mp3")
    assert parsed1["artist"] == "Kendrick Lamar"
    assert parsed1["track"] == "Not Like Us"
    assert parsed1["format"] == "mp3"

    # Pattern 2: Deep path structure with disc/track prefix
    parsed2 = parse_filename("Music/Kendrick Lamar/Not Like Us/CD1 - 02 - Kendrick Lamar - Not Like Us [FLAC].flac")
    assert parsed2["artist"] == "Kendrick Lamar"
    assert parsed2["track"] == "Not Like Us"
    assert parsed2["format"] == "flac"


def test_candidate_scoring_and_ranking():
    """
    Tests that highest quality matches (lossless, exact matches, beets confidence)
    correctly score highest.
    """
    query = SearchQuery(artist="Kendrick Lamar", track="Not Like Us")

    # Candidate A: Exact artist and track match, FLAC format, high bitrate, beets verified
    cand_a = SlskdResult(
        filename="Kendrick Lamar - Not Like Us [FLAC].flac",
        size=35000000,
        username="hifi_share",
        format="flac",
        bitrate=1020,
        sample_rate=44100,
        queue_length=0
    )
    score_a = SearchRankingService.score_candidate(cand_a, query, beets_confidence=True)["final_score"]

    # Candidate B: MP3 192kbps, parsed artist/track matches but no beets confidence
    cand_b = SlskdResult(
        filename="Kendrick Lamar - Not Like Us (192kbps).mp3",
        size=5000000,
        username="mp3_share",
        format="mp3",
        bitrate=192,
        sample_rate=44100,
        queue_length=2
    )
    score_b = SearchRankingService.score_candidate(cand_b, query, beets_confidence=False)["final_score"]

    # Candidate C: Unrelated file matching only the word 'Not' or 'Kendrick'
    cand_c = SlskdResult(
        filename="Kendrick - Swimming Pools.mp3",
        size=8000000,
        username="other_share",
        format="mp3",
        bitrate=320,
        sample_rate=44100,
        queue_length=0
    )
    score_c = SearchRankingService.score_candidate(cand_c, query, beets_confidence=False)["final_score"]

    assert score_a > score_b
    assert score_b > score_c
    assert score_a == 100  # High confidence FLAC with Beets should hit perfect/cap 100 score


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
    assert results[0]["album"] == "Not Like Us - Single"


# --- End-To-End Orchestration & Real-World Validation Simulation ---

@pytest.mark.asyncio
async def test_search_orchestration_e2e():
    """
    Simulates a real-world end-to-end search pipeline workflow:
    - User searches for Artist: "Kendrick Lamar", Track: "Not Like Us"
    - Strict query (like '"Kendrick Lamar" "Not Like Us"') is simulated to return 0 results
    - Fallback queries return results
    - Pipeline merges and deduplicates results
    - Beets enrichment identifies likely matches and applies clean metadata
    - High confidence results rise to the top of the sorted output list
    """
    # 1. Setup mocked Slskd Client responses representing a multi-stage fallback scenario
    mock_slskd = MagicMock()

    # Define mock search response structure depending on the progressive query string
    async def mock_search(query_str: str, **kwargs):
        return {"id": f"search_id_{query_str.replace(' ', '_')}"}

    async def mock_get_search_responses(search_id: str):
        # Strict search ID returns 0 files
        if "Kendrick_Lamar_\"Not_Like_Us\"" in search_id or "Kendrick_Lamar_Not_Like_Us" in search_id:
            return []

        # Fallback queries return files!
        if "Not_Like_Us" in search_id:
            return [
                {
                    "username": "share_peer_1",
                    "queueLength": 0,
                    "files": [
                        {
                            "filename": "Unknown Artist - Not Like Us (Good Quality).flac",
                            "size": 32000000,
                            "bitRate": 1050,
                            "sampleRate": 44100
                        },
                        {
                            "filename": "Kendrick Lamar - Not Like Us [320].mp3",
                            "size": 11000000,
                            "bitRate": 320,
                            "sampleRate": 44100
                        }
                    ]
                },
                {
                    "username": "share_peer_2",
                    "queueLength": 5,
                    "files": [
                        # Duplicate of Kendrick Lamar file from another user
                        {
                            "filename": "Kendrick Lamar - Not Like Us [320].mp3",
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

    # 3. Instantiate orchestrator FallbackSearchExecutor with mocked clients
    ranking_service = SearchRankingService()
    executor = FallbackSearchExecutor(
        slskd_client=mock_slskd,
        search_provider=ranking_service
    )

    # Directly mock the Beets REST API calls on the beets client (returning raw list)
    executor.beets_client.search_items = AsyncMock(return_value=[
        {
            "id": 42,
            "artist": "Kendrick Lamar",
            "title": "Not Like Us",
            "album": "Not Like Us - Single",
            "year": 2024
        }
    ])

    # 4. Trigger the end-to-end search query pipeline
    query_obj = SearchQuery(artist="Kendrick Lamar", track="Not Like Us")
    results = await executor.execute_search(query_obj)

    # Print results to stdout
    print("\n--- RESULTS ---")
    for r in results:
        print(f"Filename: {r.filename}, Format: {r.format}, Score: {r.score}, Beets: {r.beets_confidence}, Parsed Artist: {r.parsed_artist}")
    print("----------------\n")

    # 5. Assertions validating pipeline success criteria:
    # - Search should successfully fallback and return merged results
    assert len(results) > 0

    # - Results should be deduplicated (only unique username + filename tuples)
    filenames = [r.filename for r in results]
    unique_filenames = set(filenames)
    # The duplicate Kendrick Lamar file had the exact same filename and size, but different username, so they are kept as unique peer options
    assert len(results) == 3

    # - Beets enrichment was applied to improve/normalize poorly tagged metadata
    # The "Unknown Artist - Not Like Us (Good Quality).flac" file should be resolved and enriched by Beets to "Kendrick Lamar"
    enriched_flac_result = [r for r in results if "Unknown Artist" in r.filename][0]
    assert enriched_flac_result.parsed_artist == "Kendrick Lamar"
    assert enriched_flac_result.parsed_album == "Not Like Us - Single"
    assert enriched_flac_result.beets_confidence is True

    # - High confidence FLAC lossless file verified by beets rises to the absolute top of ranking list
    top_result = results[0]
    assert top_result.format == "flac"
    assert top_result.parsed_artist == "Kendrick Lamar"
    assert top_result.beets_confidence is True
    assert top_result.score == 100
