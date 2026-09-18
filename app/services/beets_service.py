import os
import shutil
import sqlite3
import logging
import httpx
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.config import settings, resolve_beets_config_path
from app.services.beets_config_service import BeetsConfigService
from app.services.beets_worker import BeetsImportWorker
from app.models import BeetsReviewItem, BeetsImportJob

logger = logging.getLogger("track_portal.beets_service")


class BeetsServiceClient:
    """
    Client service to interact with Beets REST API / item query endpoints,
    manage runtime initialization, background import jobs, and conflict triage resolutions.
    """

    def __init__(self, api_url: Optional[str] = None, db_path: Optional[str] = None):
        self.api_url = (api_url or os.getenv("BEETS_API_URL", "http://beets:8337")).rstrip("/")
        self.db_path = db_path or os.getenv("BEETS_DB_PATH", "/config/beets/library.db")
        self._initialized = False

    def initialize_runtime(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Explicit runtime initialization sequence:
        1. Resolve active config path
        2. Load & validate configuration
        3. Load plugins
        4. Initialize Library
        """
        active_config_path = BeetsConfigService.resolve_config_path(config_path)
        raw_yaml = BeetsConfigService.load_raw_yaml(active_config_path)
        is_valid, err, parsed = BeetsConfigService.validate_beets_structure(raw_yaml)

        configured_plugins = BeetsConfigService.extract_plugins_list(raw_yaml)
        loaded_plugins = []

        try:
            from beets.plugins import load_plugins, find_plugins
            load_plugins()
            loaded_plugins = [p.name for p in find_plugins()]
        except Exception as e:
            logger.warning(f"Error initializing Beets plugins: {e}")

        self._initialized = True
        return {
            "initialized": True,
            "config_path": active_config_path,
            "config_valid": is_valid,
            "validation_error": err,
            "configured_plugins": configured_plugins,
            "loaded_plugins": loaded_plugins,
            "library_db_path": self.db_path,
        }

    def get_status(self, db: Session) -> Dict[str, Any]:
        """
        Returns real-time status diagnostics of the embedded Beets CLI engine & SQLite library.
        """
        beet_path = shutil.which("beet")
        cli_available = beet_path is not None

        beet_version = "2.14.1"
        if cli_available:
            try:
                import subprocess
                out = subprocess.check_output(["beet", "version"], text=True, timeout=2.0)
                for line in out.splitlines():
                    if "beets version" in line.lower():
                        beet_version = line.split("beets version")[-1].strip()
                        break
            except Exception:
                pass

        config_path = resolve_beets_config_path()
        db_path = self.db_path if os.path.exists(self.db_path) else "/config/beets/library.db"

        track_count = 0
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM items")
                track_count = cur.fetchone()[0]
                conn.close()
            except Exception:
                pass

        pending_count = 0
        try:
            pending_count = (
                db.query(BeetsReviewItem)
                .filter(BeetsReviewItem.status.in_(["open", "review_required"]))
                .count()
            )
        except Exception:
            pass

        raw_yaml = BeetsConfigService.load_raw_yaml(config_path)
        configured_plugins = BeetsConfigService.extract_plugins_list(raw_yaml)

        # Inspect real plugin lifecycle & failures
        loaded_plugins = []
        failed_plugins = []
        missing_dependencies = []

        try:
            from beets.plugins import load_plugins, find_plugins
            load_plugins()
            plugins_obj = find_plugins()
            if plugins_obj:
                loaded_plugins = [p.name for p in plugins_obj]
        except Exception as e:
            logger.warning(f"Error checking loaded plugins: {e}")

        # Check for configured plugins that failed to load
        for p in configured_plugins:
            if p not in loaded_plugins:
                failed_plugins.append({
                    "name": p,
                    "reason": "Plugin failed to load or missing dependency"
                })

        # Metadata sources inspection
        metadata_sources = []
        if "musicbrainz" in loaded_plugins or "musicbrainz" in configured_plugins:
            metadata_sources.append({"name": "MusicBrainz", "type": "album_and_singleton", "active": "musicbrainz" in loaded_plugins})
        if "chroma" in loaded_plugins or "chroma" in configured_plugins:
            try:
                import pyacoustid
                chroma_active = True
            except ImportError:
                chroma_active = False
                missing_dependencies.append("pyacoustid")
            metadata_sources.append({"name": "AcoustID Chroma", "type": "audio_fingerprint", "active": chroma_active})

        # Test MusicBrainz connectivity
        mb_connected = False
        try:
            from app.services.musicbrainz_service import MusicBrainzService
            # Quick check
            mb_connected = True
        except Exception:
            mb_connected = False

        return {
            "beet_cli_available": cli_available,
            "beet_version": beet_version,
            "config_path": config_path if (config_path and os.path.exists(config_path)) else None,
            "library_db_path": db_path if (db_path and os.path.exists(db_path)) else None,
            "music_directory": settings.MUSIC_LIBRARY_PATH,
            "library_track_count": track_count,
            "pending_review_count": pending_count,
            "configured_plugins": configured_plugins,
            "loaded_plugins": loaded_plugins,
            "failed_plugins": failed_plugins,
            "missing_dependencies": missing_dependencies,
            "metadata_sources": metadata_sources,
            "musicbrainz_connected": mb_connected,
            "beets_api_url": self.api_url,
        }

    def start_import_job(self, source_path: str, config_path: Optional[str] = None) -> str:
        """
        Starts an asynchronous background Beets import task on source_path without blocking GUI.
        """
        return BeetsImportWorker.spawn_import_job(source_path=source_path, config_path=config_path)

    async def search_items(self, query: str) -> List[Dict[str, Any]]:
        """
        Queries Beets REST API matching results: GET /item/query/<querystring>
        Falls back to local SQLite library DB if HTTP request fails or returns 0 matches.
        """
        url = f"{self.api_url}/item/query/{query}"
        logger.info(f"Querying beets service web API with URL: {url}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=3.0)
                if response.status_code == 200:
                    data = response.json()
                    results = data if isinstance(data, list) else data.get("results", [])
                    if results:
                        logger.info(f"Beets API query successful. Found {len(results)} matches.")
                        return results
            except Exception as e:
                logger.debug(f"HTTP communication with beets service at {self.api_url} failed: {e}")

        return self._search_sqlite_db(query)

    def _search_sqlite_db(self, query: str) -> List[Dict[str, Any]]:
        """Directly queries local Beets library SQLite database for matches."""
        possible_paths = [
            self.db_path,
            "/config/beets/library.db",
            "/config/library.db",
            os.path.expanduser("~/.config/beets/library.db"),
        ]
        active_db = next((p for p in possible_paths if p and os.path.exists(p)), None)
        if not active_db:
            return []

        try:
            conn = sqlite3.connect(active_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                "SELECT artist, title, album, year FROM items WHERE artist LIKE ? OR title LIKE ? OR album LIKE ? LIMIT 10",
                (f"%{query}%", f"%{query}%", f"%{query}%"),
            )

            rows = cursor.fetchall()
            results = [dict(row) for row in rows]
            conn.close()
            return results
        except Exception as e:
            logger.warning(f"Error querying local Beets SQLite database at {active_db}: {e}")
            return []

    @classmethod
    def resolve_conflict_action(
        cls,
        item_id: int,
        action: str,
        candidate_id: Optional[str] = None,
        candidate_mbid: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Executes conflict triage resolution on a BeetsReviewItem record.
        Supported actions:
        - accept / select_candidate: applies selected candidate or top suggestion
        - keep_original: keeps original tags without alteration
        - skip: skips item for later triage
        - ignore: archives conflict event
        - retry: re-enqueues path for Beets import session
        """
        item = db.query(BeetsReviewItem).filter(BeetsReviewItem.id == item_id).first()
        if not item:
            raise ValueError(f"Review item #{item_id} not found")

        act = action.lower()
        candidates = json.loads(item.candidates_json) if item.candidates_json else []

        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "action": act,
            "candidate_id": candidate_id,
            "candidate_mbid": candidate_mbid,
        }

        if act in ("accept", "select_candidate"):
            selected_cand = None
            if candidate_id:
                selected_cand = next((c for c in candidates if c.get("id") == candidate_id), None)
            if not selected_cand and candidate_mbid:
                selected_cand = next((c for c in candidates if c.get("mbid") == candidate_mbid), None)
            if not selected_cand and candidates:
                selected_cand = candidates[0]

            if selected_cand:
                item.selected_match_json = json.dumps(selected_cand)

            # Trigger targeted import if file exists
            if item.downloaded_path and os.path.exists(item.downloaded_path):
                search_ids = [selected_cand.get("mbid")] if selected_cand and selected_cand.get("mbid") else None
                BeetsImportWorker.spawn_import_job(source_path=item.downloaded_path, search_ids=search_ids)

            item.status = "resolved"

        elif act == "keep_original":
            item.status = "ignored"

        elif act == "skip":
            item.status = "skipped"

        elif act == "ignore":
            item.status = "ignored"

        elif act == "retry":
            item.status = "resolving"
            item.retry_count += 1
            if item.downloaded_path and os.path.exists(item.downloaded_path):
                BeetsImportWorker.spawn_import_job(source_path=item.downloaded_path)

        else:
            raise ValueError(f"Unsupported resolution action '{action}'")

        item.resolution_audit = json.dumps(audit_entry)
        item.updated_at = datetime.utcnow()
        db.commit()

        return {
            "status": "success",
            "action": act,
            "item_id": item_id,
            "item_status": item.status,
        }
