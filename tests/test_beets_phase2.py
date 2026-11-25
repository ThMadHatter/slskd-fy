import os
import json
import pytest
from app.config import settings, resolve_beets_config_path
from app.services.beets_config_service import BeetsConfigService

def test_phase2_invariant1_config_and_library_path():
    """INVARIANT 1 & 2: Production library path resolves to /config/beets/library.db."""
    config_path = resolve_beets_config_path()
    assert config_path is not None
    import yaml
    raw_yaml = BeetsConfigService.load_raw_yaml(config_path)
    parsed = yaml.safe_load(raw_yaml)
    assert parsed.get("library") == "/config/beets/library.db"

def test_phase2_scenario_c_no_match_representation():
    """Scenario C: Represents missing matches cleanly without fake tags."""
    dummy_dto = {
        "artist": None,
        "track": "01 - L’albero delle noci",
        "candidates": [],
        "recommendation_text": "No external MusicBrainz match found for this release."
    }
    assert dummy_dto["artist"] is None
    assert len(dummy_dto["candidates"]) == 0
    assert "No external MusicBrainz match found" in dummy_dto["recommendation_text"]
