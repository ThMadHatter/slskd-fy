import os
import tempfile
import shutil
import logging
import yaml
from typing import Tuple, Optional, Dict, Any, List

logger = logging.getLogger("track_portal.beets_config_service")

DEFAULT_BEETS_YAML = """# App-dedicated Beets configuration for Track Portal

directory: /music
library: /config/beets/library.db

import:
  quiet: yes
  quiet_fallback: skip
  incremental: yes
  incremental_skip_later: yes
  write: yes
  move: yes
  resume: no
  timid: no

plugins: >
  fromfilename
  musicbrainz
  fetchart
  embedart
  scrub
  lastgenre
  chroma
  web
  duplicates
  info
  missing

musicbrainz:
  host: musicbrainz.org
  https: yes
  ratelimit: 1
  searchlimit: 5

match:
  strong_rec_thresh: 0.35

paths:
  default: $albumartist/$year - $album/$track - $title
  singleton: Non-Album/$artist - $title
  comp: Compilations/$album%aunique{}/$track - $title
"""

# Hard enforced runtime overrides required for headless/non-interactive integration
RUNTIME_OVERRIDES = {
    "import": {
        "quiet": True,
        "quiet_fallback": "skip",
        "incremental": True,
        "incremental_skip_later": True,
    }
}


class BeetsConfigService:
    """
    Service responsible for loading, validating, normalizing, and atomically saving
    app-dedicated Beets YAML configuration.

    Guarantees isolation from user's global ~/.config/beets/config.yaml.
    """

    @staticmethod
    def resolve_config_path(override_path: Optional[str] = None) -> str:
        """
        Determines the active config path. Prioritizes override_path,
        then volume mount /config/beets/config.yaml, then local defaults.
        """
        if override_path:
            return override_path

        candidates = [
            "/config/beets/config.yaml",
            "/config/beets_config.yaml",
            "/config/config.yaml",
            "/app/beets_config.yaml",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "beets_config.yaml"),
        ]

        for path in candidates:
            if os.path.isfile(path):
                return path

        # Default fallback target path
        default_dir = "/config/beets"
        if os.path.exists("/config"):
            os.makedirs(default_dir, exist_ok=True)
            return os.path.join(default_dir, "config.yaml")

        fallback_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(fallback_dir, "beets_config.yaml")

    @classmethod
    def load_raw_yaml(cls, config_path: Optional[str] = None) -> str:
        """
        Loads raw YAML text from the resolved configuration file.
        Returns default YAML template if file does not exist.
        """
        path = cls.resolve_config_path(config_path)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if content.strip():
                        return content
            except Exception as e:
                logger.error(f"Failed to read Beets config from '{path}': {e}")

        return DEFAULT_BEETS_YAML.strip()

    @staticmethod
    def validate_yaml_syntax(
        yaml_text: str,
    ) -> Tuple[bool, Optional[str], Optional[int], Optional[int]]:
        """
        Validates YAML syntax.
        Returns (is_valid, error_message, line_number, column_number).
        """
        if not yaml_text or not yaml_text.strip():
            return False, "YAML configuration content cannot be empty", 1, 1

        try:
            parsed = yaml.safe_load(yaml_text)
            if parsed is not None and not isinstance(parsed, dict):
                return False, "YAML root must be a dictionary/mapping object", 1, 1
            return True, None, None, None
        except yaml.MarkedYAMLError as err:
            line = err.problem_mark.line + 1 if err.problem_mark else None
            col = err.problem_mark.column + 1 if err.problem_mark else None
            problem = f"Syntax error: {err.problem}"
            if err.context:
                problem += f" ({err.context})"
            return False, problem, line, col
        except yaml.YAMLError as err:
            return False, f"YAML parsing error: {str(err)}", None, None

    @classmethod
    def validate_beets_structure(cls, yaml_text: str) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Validates syntax and verifies basic Beets structure requirements.
        Returns (is_valid, error_message, parsed_dict).
        """
        is_valid, err_msg, line, col = cls.validate_yaml_syntax(yaml_text)
        if not is_valid:
            full_msg = f"{err_msg} (line {line}, column {col})" if line else err_msg
            return False, full_msg, {}

        parsed = yaml.safe_load(yaml_text) or {}
        if not isinstance(parsed, dict):
            return False, "Top-level YAML configuration must be a key-value dictionary", {}

        # Validate section types if present
        if "import" in parsed and not isinstance(parsed["import"], dict):
            return False, "'import' section must be a key-value dictionary", {}

        if "paths" in parsed and not isinstance(parsed["paths"], dict):
            return False, "'paths' section must be a key-value dictionary", {}

        return True, None, parsed

    @classmethod
    def compute_effective_config(cls, parsed_yaml: Dict[str, Any]) -> Dict[str, Any]:
        """
        Computes effective runtime configuration by layering headless app runtime overrides
        over user specified YAML configuration.
        """
        effective = dict(parsed_yaml)

        # Merge import overrides
        user_import = effective.get("import", {})
        if not isinstance(user_import, dict):
            user_import = {}

        merged_import = dict(user_import)
        merged_import.update(RUNTIME_OVERRIDES["import"])
        effective["import"] = merged_import

        # Ensure directory and library defaults
        if "directory" not in effective:
            effective["directory"] = "/music"

        if "library" not in effective:
            effective["library"] = "/config/beets/library.db"

        return effective

    @classmethod
    def extract_plugins_list(cls, yaml_text: str) -> List[str]:
        """
        Parses configured plugin names from YAML text.
        Supports string (space/newline delimited) or list of strings.
        """
        is_valid, _, parsed = cls.validate_beets_structure(yaml_text)
        if not is_valid or not parsed:
            return []

        plugins_val = parsed.get("plugins")
        if not plugins_val:
            return []

        if isinstance(plugins_val, list):
            return [str(p).strip() for p in plugins_val if str(p).strip()]

        if isinstance(plugins_val, str):
            # Split by whitespace / newlines
            return [p.strip() for p in plugins_val.split() if p.strip()]

        return []

    @classmethod
    def save_config_atomic(
        cls, yaml_text: str, target_path: Optional[str] = None
    ) -> Tuple[bool, Optional[str], str]:
        """
        Validates YAML syntax and structure, writes to temporary file,
        creates backup, and replaces existing file atomically.

        Returns (success, error_message, path_saved).
        """
        is_valid, err_msg, _ = cls.validate_beets_structure(yaml_text)
        if not is_valid:
            return False, f"Validation failed: {err_msg}", ""

        path = cls.resolve_config_path(target_path)
        target_dir = os.path.dirname(os.path.abspath(path))
        os.makedirs(target_dir, exist_ok=True)

        backup_path = f"{path}.bak"
        temp_fd, temp_path = tempfile.mkstemp(dir=target_dir, prefix=".beets_config_", suffix=".tmp")

        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                f.write(yaml_text)
                f.flush()
                os.fsync(f.fileno())

            # Create backup if original exists
            if os.path.exists(path):
                shutil.copy2(path, backup_path)

            # Atomic replace
            os.replace(temp_path, path)
            logger.info(f"Successfully saved Beets configuration atomically to '{path}'")
            return True, None, path

        except Exception as e:
            logger.error(f"Error saving Beets configuration atomically to '{path}': {e}")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

            # Restore backup if replacement failed
            if os.path.exists(backup_path) and not os.path.exists(path):
                try:
                    shutil.copy2(backup_path, path)
                except Exception:
                    pass

            return False, f"File write error: {str(e)}", path
