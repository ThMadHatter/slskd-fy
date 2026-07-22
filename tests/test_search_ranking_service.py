import pytest
from pydantic import ValidationError
from typing import List, Dict, Any

from app.contracts.schemas import SearchQuery, SlskdResult
from app.services.search_ranking_service import SearchRankingService
from app.services.fallback_search_executor import FallbackSearchExecutor
from tests.test_contracts import MockSlskdClient
from app.dependencies import get_slskd_client, get_search_provider, get_search_executor
from app.services.slskd import SlskdClient

def test_generate_queries():
    # Backward compatible call path test
    queries = SearchRankingService().generate_queries("Kendrick Lamar", "Not Like Us")
    assert '"Kendrick Lamar" Not Like Us' in queries
    assert 'Kendrick Lamar Not Like Us' in queries

    # Contract-based (Pydantic) call path test
    query = SearchQuery(artist="Kendrick Lamar", track="Not Like Us", mode="B")
    queries_b = SearchRankingService().generate_queries(query)
    assert queries_b == ['"Kendrick Lamar" "Not Like Us"']


def test_score_exact_match():
    # Exact match for everything plus high codec/bitrate properties
    # Backward compatible call path test
    item = {
        "filename": "Kendrick Lamar - Damn - Humble.flac",
        "format": "flac",
        "bitrate": 1050,
        "sample_rate": 44100,
        "size": 35 * 1024 * 1024
    }
    score_dict = SearchRankingService().score_result(
        item,
        target_artist="Kendrick Lamar",
        target_track="Humble",
        target_album="Damn"
    )
    # Exact artist (50) + Exact track (30) + Exact album (10) + FLAC (20) + Size (5) = 115 -> capped at 100
    assert score_dict["final_score"] == 100
    assert score_dict["classification"] == "PRIMARY_ARTIST_MATCH"
    assert score_dict["artist_score"] == 50

    # Contract-based (Pydantic) call path test
    res = SlskdResult(
        filename="Kendrick Lamar - Damn - Humble.flac",
        size=35 * 1024 * 1024,
        username="peer",
        format="flac",
        bitrate=1050,
        sample_rate=44100
    )
    query = SearchQuery(artist="Kendrick Lamar", track="Humble", album="Damn")
    score_dict_contract = SearchRankingService().score_result(res, query)
    assert score_dict_contract["final_score"] == 100
    assert score_dict_contract["classification"] == "PRIMARY_ARTIST_MATCH"


def test_score_partial_mp3():
    item = {
        "filename": "01 - Kendrick Scott - Something.mp3",
        "format": "mp3",
        "bitrate": 320,
        "sample_rate": 44100,
        "size": 8 * 1024 * 1024
    }
    score_dict = SearchRankingService().score_result(
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
    score_dict = SearchRankingService().score_result(
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
    score_dict = SearchRankingService().score_result(item, "Kendrick Lamar", "Not Like Us")
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


# ----------------- FallbackSearchExecutor Tests -----------------

class FallbackMockSlskdClient(MockSlskdClient):
    def __init__(self, mode_responses: Dict[str, List[Dict[str, Any]]]):
        super().__init__()
        self.mode_responses = mode_responses

    async def search(self, query: str) -> Dict[str, Any]:
        self.last_query = query
        # Determine mode from query formatting
        mode = "A"
        if '"' in query:
            mode = "B"
        elif "artist:" in query:
            mode = "C"

        search_id = f"search_{mode}"
        self.searches[search_id] = query
        return {"id": search_id}

    async def get_search_responses(self, search_id: str) -> List[Dict[str, Any]]:
        mode = search_id.replace("search_", "")
        return self.mode_responses.get(mode, [])


@pytest.mark.asyncio
async def test_fallback_executor_strict_success():
    import os
    from unittest.mock import patch
    # Under STRICT strategy, we only run Artist + Track queries and merge/return results
    mode_responses = {
        "B": [{
            "username": "peerB",
            "files": [{
                "filename": "Artist - Track.flac",
                "size": 30000000,
                "bitRate": 1000,
                "sampleRate": 44100
            }]
        }],
        "A": []
    }

    slskd = FallbackMockSlskdClient(mode_responses)
    provider = SearchRankingService()
    executor = FallbackSearchExecutor(slskd_client=slskd, search_provider=provider)

    query = SearchQuery(artist="Artist", track="Track")
    with patch.dict(os.environ, {"SEARCH_STRATEGY": "STRICT"}):
        results = await executor.execute_search(query)

    assert len(results) == 1
    assert results[0].username == "peerB"
    assert results[0].filename == "Artist - Track.flac"


@pytest.mark.asyncio
async def test_fallback_executor_strict_fails_balanced_success():
    import os
    from unittest.mock import patch
    # Under BALANCED strategy, if STRICT queries return 0 files, it falls back to broader ones
    mode_responses = {
        "B": [],
        "A": [{
            "username": "peerA",
            "files": [{
                "filename": "Artist - Track.flac",
                "size": 30000000,
                "bitRate": 1000,
                "sampleRate": 44100
            }]
        }]
    }

    slskd = FallbackMockSlskdClient(mode_responses)
    provider = SearchRankingService()
    executor = FallbackSearchExecutor(slskd_client=slskd, search_provider=provider)

    query = SearchQuery(artist="Artist", track="Track")
    with patch.dict(os.environ, {"SEARCH_STRATEGY": "BALANCED"}):
        results = await executor.execute_search(query)

    assert len(results) == 1
    assert results[0].username == "peerA"


@pytest.mark.asyncio
async def test_fallback_executor_graceful_degradation_on_exception():
    # If a query throws an error, the executor recovers gracefully and falls back to next mode [RSL-003]
    class FaultySlskdClient(MockSlskdClient):
        async def search(self, query: str) -> Dict[str, Any]:
            if '"' in query: # STRICT queries throw exception
                raise RuntimeError("Slskd timed out")
            return {"id": "search_A"}

        async def get_search_responses(self, search_id: str) -> List[Dict[str, Any]]:
            return [{
                "username": "peerA",
                "files": [{
                    "filename": "Artist - Track.flac",
                    "size": 30000000,
                    "bitRate": 1000,
                    "sampleRate": 44100
                }]
            }]

    slskd = FaultySlskdClient()
    provider = SearchRankingService()
    executor = FallbackSearchExecutor(slskd_client=slskd, search_provider=provider)

    query = SearchQuery(artist="Artist", track="Track")
    results = await executor.execute_search(query)

    assert len(results) == 1
    assert results[0].username == "peerA"


# ----------------- Dependencies DI Tests -----------------

def test_dependencies_di_container():
    """
    [CDA-003] Validates the Factory / dependency container setup.
    """
    client_inst = get_slskd_client()
    assert isinstance(client_inst, SlskdClient)

    provider_inst = get_search_provider()
    assert isinstance(provider_inst, SearchRankingService)

    executor_inst = get_search_executor()
    assert isinstance(executor_inst, FallbackSearchExecutor)
    assert executor_inst.search_provider is provider_inst or isinstance(executor_inst.search_provider, SearchRankingService)


# ----------------- Additional Tests for Double Quote Sanitization and 5-Second Fallback -----------------

def test_quote_sanitization():
    # Ensure double quotes are stripped from search inputs
    queries = SearchRankingService().generate_queries("Kendrick \"Lamar\"", "Not \"Like\" Us")
    assert '"Kendrick Lamar" "Not Like Us"' in SearchRankingService().generate_queries(
        SearchQuery(artist="Kendrick \"Lamar\"", track="Not \"Like\" Us", mode="B")
    )
    for q in queries:
        assert '\"Lamar\"' not in q
        assert '\"Like\"' not in q


@pytest.mark.asyncio
async def test_fallback_executor_polls_5_seconds_and_transitions():
    from unittest.mock import patch, AsyncMock
    # If Mode B has 0 results, we poll for 5 seconds (5 calls to sleep, 5 calls to get_search_responses)
    mode_responses = {
        "B": [], # 0 files
        "A": [{
            "username": f"peerA_{i}",
            "files": [{
                "filename": "Artist - Track.mp3",
                "size": 8000000,
                "bitRate": 320,
                "sampleRate": 44100
            }]
        } for i in range(8)]
    }

    slskd = FallbackMockSlskdClient(mode_responses)
    original_get_responses = slskd.get_search_responses
    call_count = 0
    async def spy_get_responses(search_id: str):
        nonlocal call_count
        if "B" in search_id:
            call_count += 1
        return await original_get_responses(search_id)

    slskd.get_search_responses = spy_get_responses

    provider = SearchRankingService()
    executor = FallbackSearchExecutor(slskd_client=slskd, search_provider=provider)

    query = SearchQuery(artist="Artist", track="Track")

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        results = await executor.execute_search(query)

        # Mode B (quoted queries) should have failed after 5 poll iterations each
        assert call_count == 10
        # And should have called asyncio.sleep exactly 13 times due to progressive BALANCED merging
        assert mock_sleep.call_count == 13

        # Fallback should have transitioned and found A
        assert len(results) == 8
        assert results[0].username == "peerA_0"
