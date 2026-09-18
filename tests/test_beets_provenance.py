import pytest
from app.services.beets_collector import clean_query_hint, ConflictCollector
from app.services.beets_service import BeetsServiceClient


def test_clean_query_hint():
    raw_1 = "Artist - Album (2025) [Flac 24-44] AtM"
    assert clean_query_hint(raw_1) == "Artist - Album (2025)"

    raw_2 = "Artist - Album [WEB FLAC]"
    assert clean_query_hint(raw_2) == "Artist - Album"

    raw_3 = "Artist - Album (Deluxe Edition)"
    assert clean_query_hint(raw_3) == "Artist - Album (Deluxe Edition)"

    raw_4 = "Artist - Album [24bit-96kHz]"
    assert clean_query_hint(raw_4) == "Artist - Album"


class DummyItem:
    def __init__(self, artist, title, album, year, format_="FLAC"):
        self.artist = artist
        self.title = title
        self.album = album
        self.year = year
        self.format = format_
        self.bitrate = 1411000
        self.samplerate = 44100


class DummyCandidate:
    def __init__(self, artist, album, year, release_id, track_id=None, distance=0.1):
        self.artist = artist
        self.album = album
        self.title = album
        self.year = year
        self.id = release_id
        self.album_id = release_id
        self.track_id = track_id
        self.release_id = release_id
        self.releasegroup_id = f"rg_{release_id}"
        self.country = "US"
        self.label = "Warp Records"
        self.catalognum = "WARP123"
        self.media = "CD"
        self.distance = distance


class DummyTask:
    def __init__(self, is_singleton=False, candidates=None):
        self.is_singleton = is_singleton
        self.paths = ["/music/Aphex Twin - Selected Ambient Works (2025) [Flac 24-44] AtM/01 Pulsewidth.flac"]
        self.items = [DummyItem("Aphex Twin", "Pulsewidth", "Selected Ambient Works 85-92", 1992)]
        self.candidates = candidates or []

    def to_import_path(self):
        return self.paths[0]


def test_conflict_collector_provenance_and_dto():
    cand = DummyCandidate("Aphex Twin", "Selected Ambient Works 85-92", 1992, "mbid-rel-123", distance=0.1)
    task = DummyTask(is_singleton=False, candidates=[cand])

    dto = ConflictCollector.extract_conflict_dto(task, job_id="job-999")

    assert dto["item_type"] == "album"
    assert dto["artist"] == "Aphex Twin"
    assert dto["track"] == "Pulsewidth"
    assert dto["album"] == "Selected Ambient Works 85-92"
    assert "provenance" in dto
    assert dto["provenance"]["embedded_tags"]["artist"] == "Aphex Twin"
    assert dto["provenance"]["technical_props"]["format"] == "FLAC"

    assert len(dto["candidates"]) == 1
    top = dto["candidates"][0]
    assert top["source"] == "MusicBrainz"
    assert top["release_id"] == "mbid-rel-123"
    assert top["ui_similarity_score"] == 90
    assert "Strong match candidate found" in dto["recommendation_text"]


def test_conflict_collector_empty_candidates():
    task = DummyTask(is_singleton=True, candidates=[])
    dto = ConflictCollector.extract_conflict_dto(task, job_id="job-000")

    assert dto["item_type"] == "singleton"
    assert len(dto["candidates"]) == 0
    assert "No external MusicBrainz match found" in dto["recommendation_text"]
