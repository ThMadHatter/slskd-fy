import os
import tempfile
import pytest
import yaml
from app.services.beets_config_service import BeetsConfigService, DEFAULT_BEETS_YAML


def test_validate_yaml_syntax_valid():
    valid_yaml = "directory: /music\nlibrary: /config/library.db\nimport:\n  quiet: yes\n"
    is_valid, err, line, col = BeetsConfigService.validate_yaml_syntax(valid_yaml)
    assert is_valid is True
    assert err is None
    assert line is None
    assert col is None


def test_validate_yaml_syntax_invalid():
    invalid_yaml = "directory: /music\n  invalid_indent: [unclosed_bracket\nlibrary: test"
    is_valid, err, line, col = BeetsConfigService.validate_yaml_syntax(invalid_yaml)
    assert is_valid is False
    assert err is not None
    assert "Syntax error" in err or "parsing error" in err
    assert line is not None


def test_extract_plugins_list():
    yaml_text = """
plugins: >
  fromfilename
  musicbrainz
  chroma
"""
    plugins = BeetsConfigService.extract_plugins_list(yaml_text)
    assert plugins == ["fromfilename", "musicbrainz", "chroma"]

    yaml_list = "plugins:\n  - fromfilename\n  - musicbrainz\n"
    plugins_list = BeetsConfigService.extract_plugins_list(yaml_list)
    assert plugins_list == ["fromfilename", "musicbrainz"]


def test_compute_effective_config():
    user_yaml = {"directory": "/my_music", "import": {"quiet": False, "move": False}}
    effective = BeetsConfigService.compute_effective_config(user_yaml)

    assert effective["directory"] == "/my_music"
    # Runtime overrides force quiet=True
    assert effective["import"]["quiet"] is True
    assert effective["import"]["incremental"] is True


def test_save_config_atomic_and_isolation(tmp_path):
    config_file = tmp_path / "test_beets_config.yaml"
    valid_content = "directory: /tmp/music\nlibrary: /tmp/lib.db\n"

    success, err, path_saved = BeetsConfigService.save_config_atomic(valid_content, str(config_file))
    assert success is True
    assert err is None
    assert os.path.exists(config_file)

    with open(config_file, "r", encoding="utf-8") as f:
        read_data = f.read()
    assert read_data == valid_content

    # Attempt to save invalid YAML
    invalid_content = "directory: /tmp\n  bad_syntax: ["
    success_inv, err_inv, _ = BeetsConfigService.save_config_atomic(invalid_content, str(config_file))
    assert success_inv is False
    assert err_inv is not None

    # Verify original file content was not overwritten on error
    with open(config_file, "r", encoding="utf-8") as f:
        read_data_after = f.read()
    assert read_data_after == valid_content
