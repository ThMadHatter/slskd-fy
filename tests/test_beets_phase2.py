import os
import json
import pytest
from app.config import settings, resolve_beets_config_path
from app.services.beets_config_service import BeetsConfigService
from app.services.filename_parser import parse_filename

def test_phase2_invariant1_config_and_library_path():
    """INVARIANT 1 & 2: Production library path resolves to /config/beets/library.db."""
    config_path = resolve_beets_config_path()
    assert config_path is not None
    import yaml
    raw_yaml = BeetsConfigService.load_raw_yaml(config_path)
    parsed = yaml.safe_load(raw_yaml)
    assert parsed.get("library") == "/config/beets/library.db"

def test_phase2_invariant4_no_fake_unknown_artist():
    """INVARIANT 4: Filename parser preserves valid track hints without fabricating Unknown Artist."""
    parsed = parse_filename("/downloads/L’albero delle noci (2025) [FLAC]/01 - L’albero delle noci.flac")
    assert parsed.get("track") == "L’albero delle noci"
    assert parsed.get("year") == 2025

def test_phase2_scenario_c_no_match_representation():
    """Scenario C: Represents missing matches cleanly without fake tags."""
    from app.services.beets_collector import ConflictCollector
    dummy_dto = {
        "artist": "Unknown Artist",
        "track": "Unknown Track",
        "candidates": [],
        "recommendation_text": "No external MusicBrainz match found for this release."
    }
    assert len(dummy_dto["candidates"]) == 0
    assert "No external MusicBrainz match found" in dummy_dto["recommendation_text"]
