import pytest
from app.services.beets_collector import clean_query_hint, ConflictCollector
from app.services.beets_service import BeetsServiceClient


def test_clean_query_hint():
    raw_1 = "2025 - Brunori Sas - L'Albero Delle Noci (2025) [Flac 24-44]"
    assert clean_query_hint(raw_1) == "Brunori Sas - L'Albero Delle Noci"

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


def resolve_display_metadata(item_artist, item_album, item_track, candidates=None, selected_candidate_id=None):
    """
    Python reference helper mirroring frontend getDisplayMetadata logic.
    """
    def is_invalid(val):
        if not val:
            return True
        norm = str(val).strip().lower()
        return norm in ("", "unknown", "unknown artist", "unknown album", "unknown track", "n/a")

    cands = candidates or []
    best = None
    if selected_candidate_id and cands:
        best = next((c for c in cands if c.get("id") == selected_candidate_id), None)
    if not best and cands:
        best = sorted(cands, key=lambda x: x.get("ui_similarity_score", x.get("confidence", 0)), reverse=True)[0]

    cand_artist = best.get("artist") if best else None
    cand_album = (best.get("album") or best.get("title")) if best else None
    cand_track = best.get("title") if best else None

    display_artist = cand_artist if not is_invalid(cand_artist) else (item_artist if not is_invalid(item_artist) else "Unknown Artist")
    display_album = cand_album if not is_invalid(cand_album) else (item_album if not is_invalid(item_album) else "Unknown Album")
    display_track = cand_track if not is_invalid(cand_track) else (item_track if not is_invalid(item_track) else "Unknown Track")

    return {
        "display_artist": display_artist,
        "display_album": display_album,
        "display_track": display_track,
        "source_artist": item_artist,
        "source_album": item_album,
        "source_track": item_track,
    }


def test_display_metadata_scenarios():
    # Scenario 1: Unknown source + valid Beets candidate
    res1 = resolve_display_metadata("Unknown Artist", "L’albero delle noci (2025)", "01 - L’albero delle noci.flac", [
        {"id": "cand-1", "artist": "Brunori Sas", "album": "L’albero delle noci", "title": "L’albero delle noci", "confidence": 94}
    ])
    assert res1["display_artist"] == "Brunori Sas"
    assert res1["display_album"] == "L’albero delle noci"
    assert res1["source_artist"] == "Unknown Artist"  # Provenance untouched

    # Scenario 2: Real source artist
    res2 = resolve_display_metadata("Daft Punk", "Discovery", "One More Time", [
        {"id": "cand-2", "artist": "Daft Punk", "album": "Discovery", "title": "One More Time", "confidence": 100}
    ])
    assert res2["display_artist"] == "Daft Punk"
    assert res2["display_album"] == "Discovery"

    # Scenario 3: No candidate
    res3 = resolve_display_metadata("Unknown Artist", "Unknown Album", "Track 01", [])
    assert res3["display_artist"] == "Unknown Artist"
    assert res3["display_album"] == "Unknown Album"

    # Scenario 4: Candidate without artist
    res4 = resolve_display_metadata("Unknown Artist", "Unknown Album", "Track 01", [
        {"id": "cand-4", "artist": None, "album": None, "title": "Track 01", "confidence": 50}
    ])
    assert res4["display_artist"] == "Unknown Artist"

    # Scenario 5: Provenance remains unchanged
    cand5 = {"id": "cand-5", "artist": "Brunori Sas", "album": "L’albero delle noci", "title": "L’albero delle noci", "confidence": 94}
    res5 = resolve_display_metadata("Unknown Artist", "L’albero delle noci", "01 - L’albero delle noci.flac", [cand5])
    assert res5["source_artist"] == "Unknown Artist"
    assert res5["display_artist"] == "Brunori Sas"

    # Scenario 6: Album display fallback behavior
    res6 = resolve_display_metadata("Unknown Artist", "Unknown Album", "01 - L’albero delle noci.flac", [
        {"id": "cand-6", "artist": "Brunori Sas", "album": "L’albero delle noci", "title": "L’albero delle noci", "confidence": 94}
    ])
    assert res6["display_album"] == "L’albero delle noci"
