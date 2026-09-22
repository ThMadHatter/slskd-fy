import os
import sys
import uuid
import json
import logging
import threading
from typing import Optional, Dict, Any, Set
from datetime import datetime

import beets.plugins
from beets.plugins import BeetsPlugin
from beets.importer import ImportSession, Action
from beets.library import Library

from app.database import SessionLocal
from app.models import BeetsImportJob, BeetsReviewItem
from app.services.beets_config_service import BeetsConfigService
from app.services.beets_collector import ConflictCollector

logger = logging.getLogger("track_portal.beets_worker")

# Thread safety lock & set of active import paths to prevent duplicate concurrent imports
_ACTIVE_IMPORT_LOCK = threading.Lock()
_ACTIVE_IMPORT_PATHS: Set[str] = set()


class TrackPortalBeetsPlugin(BeetsPlugin):
    """
    Internal Beets plugin registered dynamically to capture import task choices and events.
    """

    def __init__(self, job_id: str, callback=None):
        super().__init__()
        self.job_id = job_id
        self.callback = callback
        self.register_listener("import_task_choice", self.on_import_task_choice)
        self.register_listener("import_task_apply", self.on_import_task_apply)

    def on_import_task_choice(self, session, task):
        """
        Intercepts task decision during import session.
        If task choice is SKIP, ASIS, or sub-threshold, registers a conflict DTO.
        """
        try:
            choice = getattr(task, "choice_flag", None)
            rec = getattr(task, "rec", None)

            # Check if task requires human review (e.g. Action.SKIP or low confidence)
            is_conflict = (
                choice == Action.SKIP
                or (hasattr(rec, "name") and rec.name in ("RECOMMEND", "LOW", "NONE"))
                or choice is None
            )

            if is_conflict:
                dto = ConflictCollector.extract_conflict_dto(task, session=session, job_id=self.job_id)
                if self.callback:
                    self.callback(dto)
        except Exception as e:
            logger.error(f"Error in TrackPortalBeetsPlugin.on_import_task_choice: {e}")

    def on_import_task_apply(self, session, task):
        """
        Triggered when a task is successfully imported and applied.
        """
        logger.debug(f"Task applied successfully for job '{self.job_id}': {task}")


def run_beets_import_task(
    job_id: str,
    source_path: str,
    config_path: Optional[str] = None,
    search_ids: Optional[list] = None,
):
    """
    Worker function executed in a background thread.
    Executes Beets ImportSession outside the main GUI/asyncio thread.
    """
    norm_source_path = os.path.normpath(os.path.abspath(source_path))

    # Thread safety check for duplicate active paths
    with _ACTIVE_IMPORT_LOCK:
        if norm_source_path in _ACTIVE_IMPORT_PATHS:
            logger.warning(f"Import task for path '{norm_source_path}' is already running. Skipping duplicate job.")
            db = SessionLocal()
            job = db.query(BeetsImportJob).filter(BeetsImportJob.job_id == job_id).first()
            if job:
                job.status = "failed"
                job.error_message = "Duplicate active import job for same path"
                db.commit()
            db.close()
            return
        _ACTIVE_IMPORT_PATHS.add(norm_source_path)

    db = SessionLocal()
    job = db.query(BeetsImportJob).filter(BeetsImportJob.job_id == job_id).first()
    if not job:
        job = BeetsImportJob(
            job_id=job_id,
            source_path=norm_source_path,
            status="running",
            created_at=datetime.utcnow(),
        )
        db.add(job)
        db.commit()
    else:
        job.status = "running"
        db.commit()

    captured_conflicts = []

    def on_conflict_dto(dto: Dict[str, Any]):
        captured_conflicts.append(dto)
        # Persist conflict in database
        try:
            db_inner = SessionLocal()
            existing = (
                db_inner.query(BeetsReviewItem)
                .filter(BeetsReviewItem.fingerprint == dto["fingerprint"])
                .first()
            )

            if not existing:
                item = BeetsReviewItem(
                    conflict_id=dto["conflict_id"],
                    fingerprint=dto["fingerprint"],
                    job_id=dto["job_id"],
                    item_type=dto["item_type"],
                    artist=dto["artist"],
                    track=dto["track"],
                    album=dto["album"],
                    downloaded_path=dto["downloaded_path"],
                    confidence_score=dto["confidence_score"],
                    status="open",
                    candidates_json=json.dumps(dto["candidates"]),
                    differences_json=json.dumps(dto.get("differences", {})),
                    provenance_json=json.dumps(dto["provenance"]) if dto.get("provenance") else None,
                    recommendation_text=dto.get("recommendation_text", ""),
                    created_at=datetime.utcnow(),
                )
                db_inner.add(item)
                db_inner.commit()
                logger.info(f"Persisted new conflict event #{dto['conflict_id']} for path '{dto['downloaded_path']}'")
            db_inner.close()
        except Exception as err:
            logger.error(f"Failed to persist conflict DTO: {err}")

    try:
        # Load dedicated config
        resolved_config = BeetsConfigService.resolve_config_path(config_path)
        logger.info(f"Worker starting Beets import job '{job_id}' on path '{norm_source_path}' using config '{resolved_config}'")

        # Load plugins
        beets.plugins.load_plugins()

        # Instantiate Library
        lib_path = "/config/beets/library.db"
        lib = Library(lib_path)

        # Register plugin listener for this session
        plugin = TrackPortalBeetsPlugin(job_id=job_id, callback=on_conflict_dto)

        class NonInteractiveImportSession(ImportSession):
            """
            Subclass of ImportSession for headless execution.
            Overrides choose_match to return Action.SKIP when manual intervention is required,
            preventing NotImplementedError from being raised.
            """
            def choose_match(self, task):
                return Action.SKIP

        # Instantiate NonInteractiveImportSession
        session = NonInteractiveImportSession(
            lib=lib,
            loghandler=None,
            paths=[norm_source_path],
            query=None,
        )

        if search_ids:
            session.search_ids = search_ids

        # Run import session
        session.run()

        # Refresh job state in database
        job = db.query(BeetsImportJob).filter(BeetsImportJob.job_id == job_id).first()
        if job:
            job.conflicts_count = len(captured_conflicts)
            if len(captured_conflicts) > 0:
                job.status = "completed_with_conflicts"
            else:
                job.status = "completed"
            job.updated_at = datetime.utcnow()
            db.commit()

        logger.info(f"Import job '{job_id}' completed with {len(captured_conflicts)} conflicts.")

    except Exception as e:
        logger.exception(f"Error during execution of Beets import job '{job_id}': {e}")
        job = db.query(BeetsImportJob).filter(BeetsImportJob.job_id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(e)
            job.updated_at = datetime.utcnow()
            db.commit()

    finally:
        db.close()
        with _ACTIVE_IMPORT_LOCK:
            _ACTIVE_IMPORT_PATHS.discard(norm_source_path)


class BeetsImportWorker:
    """
    Manager for spawning background Beets import tasks without blocking main thread.
    """

    @classmethod
    def spawn_import_job(
        cls, source_path: str, config_path: Optional[str] = None, search_ids: Optional[list] = None
    ) -> str:
        """
        Creates a new BeetsImportJob and starts background worker thread.
        Returns job_id.
        """
        job_id = str(uuid.uuid4())
        norm_path = os.path.normpath(os.path.abspath(source_path))

        db = SessionLocal()
        job = BeetsImportJob(
            job_id=job_id,
            source_path=norm_path,
            status="queued",
            created_at=datetime.utcnow(),
        )
        db.add(job)
        db.commit()
        db.close()

        thread = threading.Thread(
            target=run_beets_import_task,
            args=(job_id, norm_path, config_path, search_ids),
            daemon=True,
            name=f"BeetsWorkerThread-{job_id[:8]}",
        )
        thread.start()
        logger.info(f"Spawned BeetsWorkerThread for job_id '{job_id}' on path '{norm_path}'")
        return job_id
