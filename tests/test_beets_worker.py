import os
import tempfile
import pytest
import json
from app.services.beets_collector import ConflictCollector
from app.services.beets_service import BeetsServiceClient


class MockBeetsTask:
    def __init__(self, path="/music/artist/track.flac", artist="Daft Punk", track="One More Time", album="Discovery"):
        self.path = path
        self.cur_artist = artist
        self.cur_track = track
        self.cur_album = album
        self.is_singleton = False
        self.candidates = [
            MockCandidate(cand_id="mb_discovery_1", artist="Daft Punk", album="Discovery", year=2001, distance=0.1)
        ]

    def to_import_path(self):
        return self.path


class MockCandidate:
    def __init__(self, cand_id, artist, album, year, distance):
        self.id = cand_id
        self.album_id = cand_id
        self.artist = artist
        self.album = album
        self.year = year
        self.distance = distance


def test_conflict_collector_dto_conversion():
    task = MockBeetsTask()
    dto = ConflictCollector.extract_conflict_dto(task, job_id="test_job_123")

    assert dto["conflict_id"] is not None
    assert dto["fingerprint"] is not None
    assert dto["job_id"] == "test_job_123"
    assert dto["artist"] == "Daft Punk"
    assert dto["track"] == "One More Time"
    assert dto["album"] == "Discovery"
    assert dto["confidence_score"] == 90 # (1.0 - 0.1) * 100
    assert len(dto["candidates"]) == 1
    assert dto["candidates"][0]["id"] == "mb_discovery_1"


def test_conflict_collector_fingerprint_idempotency():
    fp1 = ConflictCollector.calculate_fingerprint("/music/album", "Daft Punk", "One More Time")
    fp2 = ConflictCollector.calculate_fingerprint("/music/album/", "daft punk ", "ONE MORE TIME")
    assert fp1 == fp2


def test_beets_service_runtime_initialization(tmp_path):
    config_file = tmp_path / "beets_config.yaml"
    config_file.write_text("directory: /music\nplugins:\n  - fromfilename\n", encoding="utf-8")

    client = BeetsServiceClient()
    info = client.initialize_runtime(config_path=str(config_file))

    assert info["initialized"] is True
    assert info["config_valid"] is True
    assert "fromfilename" in info["configured_plugins"]
