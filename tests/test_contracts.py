import pytest
from pydantic import ValidationError
from typing import List, Dict, Any

from app.contracts.schemas import SearchQuery, SlskdResult, TelemetryData
from app.contracts.services import SlskdClientContract, TelemetryContract

# ----------------- Mock Implementations -----------------

class MockSlskdClient(SlskdClientContract):
    def __init__(self):
        self.searches = {}
        self.downloads = []

    async def search(self, query: str, timeout_sec: int = 15, wait_until_complete: bool = False) -> Dict[str, Any]:
        search_id = f"search_{len(self.searches)}"
        self.searches[search_id] = query
        return {"id": search_id}

    async def get_search_responses(self, search_id: str) -> List[Dict[str, Any]]:
        if search_id in self.searches:
            return [{"username": "peer1", "files": []}]
        return []

    async def enqueue_download(self, username: str, filename: str, size: int) -> bool:
        self.downloads.append((username, filename, size))
        return True

    async def get_downloads(self, include_removed: bool = False) -> List[Dict[str, Any]]:
        return self.downloads

    async def cancel_download(self, username: str, id_: str) -> bool:
        return True


class MockTelemetry(TelemetryContract):
    def __init__(self):
        self.metrics = []

    def record_search_metrics(self, data: TelemetryData) -> None:
        self.metrics.append(data)

    def get_aggregate_stats(self) -> Dict[str, Any]:
        if not self.metrics:
            return {"avg_search_duration": 0.0}
        total = sum(m.search_duration for m in self.metrics)
        return {"avg_search_duration": total / len(self.metrics)}


# ----------------- Unit Tests -----------------

def test_search_query_valid():
    q = SearchQuery(artist="Daft Punk", track="One More Time", mode="A")
    assert q.artist == "Daft Punk"
    assert q.track == "One More Time"
    assert q.mode == "A"

    q2 = SearchQuery(artist="Daft Punk", track="One More Time", mode=" b ")
    assert q2.mode == "B"


def test_search_query_invalid():
    with pytest.raises(ValidationError):
        SearchQuery(artist="", track="")

    with pytest.raises(ValidationError):
        SearchQuery(artist="   ", track="  ")

    with pytest.raises(ValidationError):
        SearchQuery(artist="Daft Punk", track="One More Time", mode="D")


def test_slskd_result_valid():
    res = SlskdResult(
        filename="Daft Punk/Discovery/Daft Punk - One More Time.flac",
        size=35000000,
        username="cool_peer",
        format="flac",
        bitrate=1020,
        sample_rate=44100,
        queue_length=1
    )
    assert res.format == "flac"
    assert res.bitrate == 1020

    res2 = SlskdResult(
        filename="Daft Punk - One More Time.mp3",
        size=10000000,
        username="peer",
        format=".MP3"
    )
    assert res2.format == "mp3"


def test_slskd_result_invalid():
    with pytest.raises(ValidationError):
        SlskdResult(filename="test.mp3", size=-1, username="user", format="mp3")

    with pytest.raises(ValidationError):
        SlskdResult(filename="test.mp3", size=100, username="", format="mp3")

    with pytest.raises(ValidationError):
        SlskdResult(filename="test.txt", size=100, username="user", format="txt")


def test_telemetry_data_valid():
    t = TelemetryData(
        autocomplete_latency=0.015,
        search_duration=1.24,
        ranking_duration=0.005,
        mb_requests=3,
        mb_enrich_time=0.45
    )
    assert t.mb_requests == 3
    assert t.search_duration == 1.24


def test_telemetry_data_invalid():
    with pytest.raises(ValidationError):
        TelemetryData(
            autocomplete_latency=0.015,
            search_duration=1.24,
            ranking_duration=0.005,
            mb_requests=-1,
            mb_enrich_time=0.45
        )


@pytest.mark.asyncio
async def test_mock_slskd_client():
    client = MockSlskdClient()
    search_res = await client.search("Daft Punk One More Time")
    assert "id" in search_res
    search_id = search_res["id"]

    responses = await client.get_search_responses(search_id)
    assert len(responses) == 1
    assert responses[0]["username"] == "peer1"

    success = await client.enqueue_download("peer1", "track.flac", 300000)
    assert success is True
    assert len(client.downloads) == 1


def test_mock_telemetry():
    tel = MockTelemetry()
    assert tel.get_aggregate_stats() == {"avg_search_duration": 0.0}

    tel.record_search_metrics(TelemetryData(
        autocomplete_latency=0.01,
        search_duration=1.0,
        ranking_duration=0.01,
        mb_requests=2,
        mb_enrich_time=0.2
    ))
    tel.record_search_metrics(TelemetryData(
        autocomplete_latency=0.02,
        search_duration=2.0,
        ranking_duration=0.02,
        mb_requests=4,
        mb_enrich_time=0.4
    ))

    stats = tel.get_aggregate_stats()
    assert stats["avg_search_duration"] == 1.5
