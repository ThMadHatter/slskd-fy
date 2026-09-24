import os
import json
import uuid
import time
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from alembic.config import Config
from alembic import command

from app.config import settings
from app.database import SessionLocal, get_db
from app.auth import COOKIE_NAME, decode_access_token, verify_csrf_token, init_admin_user, get_optional_user
from app.routers import pages
from app.services.downloads_poller import start_background_poller

import sys

logger = logging.getLogger("track_portal")

class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for machine-parseable log ingest."""
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage()
        }
        if hasattr(record, "correlation_id"):
            log_obj["correlation_id"] = record.correlation_id
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)

def setup_app_logging():
    """
    Set up Track Portal logging using settings.LOG_LEVEL and settings.LOG_FORMAT.
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)
    logger.handlers = []  # Clear to avoid duplicates

    sh = logging.StreamHandler(sys.stdout)
    if settings.LOG_FORMAT.lower() == "json":
        sh.setFormatter(JSONFormatter())
    else:
        sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

    logger.addHandler(sh)
    logger.propagate = False

# Programmatically run Alembic migrations on startup with defensive schema auto-healing
def run_migrations() -> str:
    logger.info(f"Effective DATABASE_URL: {settings.DATABASE_URL}")
    logger.info("Running database migrations via Alembic...")
    logs = []

    def log_msg(msg: str):
        logger.info(msg)
        logs.append(msg)

    try:
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")

        # Safely log current migration revision
        from alembic.migration import MigrationContext
        from sqlalchemy import create_engine, inspect, text
        engine = create_engine(settings.DATABASE_URL)

        with engine.connect() as conn:
            context = MigrationContext.configure(conn)
            current_rev = context.get_current_revision()
            log_msg(f"Alembic migration execution completed. Current revision: {current_rev}")

            # Defensive schema auto-healing for beets_review_items & beets_import_jobs
            inspector = inspect(conn)
            tables = inspector.get_table_names()

            if "beets_import_jobs" not in tables:
                log_msg("Auto-healing schema: creating missing 'beets_import_jobs' table...")
                conn.execute(text("""
                    CREATE TABLE beets_import_jobs (
                        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                        job_id VARCHAR NOT NULL UNIQUE,
                        source_path VARCHAR NOT NULL,
                        status VARCHAR NOT NULL DEFAULT 'queued',
                        total_items INTEGER NOT NULL DEFAULT 0,
                        imported_items INTEGER NOT NULL DEFAULT 0,
                        conflicts_count INTEGER NOT NULL DEFAULT 0,
                        error_message VARCHAR,
                        created_at DATETIME,
                        updated_at DATETIME
                    )
                """))
                conn.commit()

            if "beets_review_items" in tables:
                existing_cols = {c["name"] for c in inspector.get_columns("beets_review_items")}
                missing_columns = {
                    "conflict_id": "VARCHAR",
                    "fingerprint": "VARCHAR",
                    "job_id": "VARCHAR",
                    "item_type": "VARCHAR DEFAULT 'album'",
                    "differences_json": "VARCHAR",
                    "provenance_json": "VARCHAR",
                    "recommendation_text": "VARCHAR",
                    "error_message": "VARCHAR",
                    "retry_count": "INTEGER DEFAULT 0",
                    "resolution_audit": "VARCHAR",
                }

                for col_name, col_type in missing_columns.items():
                    if col_name not in existing_cols:
                        log_msg(f"Auto-healing schema: adding missing column 'beets_review_items.{col_name}'...")
                        conn.execute(text(f"ALTER TABLE beets_review_items ADD COLUMN {col_name} {col_type}"))
                        conn.commit()

            log_msg("Database schema verification and auto-healing completed successfully.")
    except Exception as e:
        err_msg = f"Error during database migration execution: {e}"
        logger.error(err_msg, exc_info=True)
        logs.append(err_msg)

    return "\n".join(logs)

# Async context manager for startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info("Startup step 1: Setting up application logging...")
    setup_app_logging()
    logger.info("Startup step 1 complete")

    logger.info("Startup step 2: Running database migrations...")
    run_migrations()
    logger.info("Startup step 2 complete")

    logger.info("Startup step 3: Initializing admin user if none exists...")
    db = SessionLocal()
    init_admin_user(db)
    db.close()
    logger.info("Startup step 3 complete")

    logger.info("Startup step 4: Starting background downloads poller...")
    start_background_poller()
    logger.info("Startup step 4 complete")

    logger.info("Startup step 5: Lifespan startup fully complete!")
    yield
    # Shutdown actions
    logger.info("Shutting down Track Portal...")

app = FastAPI(
    title="Track Portal",
    description="Decoupled high-fidelity track search and download portal for Soulseek",
    version="2.0.0",
    lifespan=lifespan
)

# Setup Jinja2 Templates
templates = Jinja2Templates(directory="app/templates")

# Mount Static Files (creating the directory if it does not exist)
os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Mount Next.js static files exported path
os.makedirs("app/static/_next", exist_ok=True)
app.mount("/_next", StaticFiles(directory="app/static/_next"), name="next_static")

# Middleware to support request correlation IDs and state
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    correlation_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.correlation_id = correlation_id
    request.state.user = None

    start_time = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start_time) * 1000, 2)

    response.headers["X-Request-ID"] = correlation_id
    logger.info(
        f"HTTP {request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)",
        extra={"correlation_id": correlation_id}
    )
    return response

# Include page routes
app.include_router(pages.router)

from sqlalchemy import text

# Healthcheck Endpoint
@app.get("/health", status_code=status.HTTP_200_OK)
def healthcheck(db: Session = Depends(get_db)):
    try:
        # Check SQLite db connectivity
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Healthcheck database error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unhealthy: {e}"
        )
