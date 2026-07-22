import os
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

def setup_app_logging():
    """
    Set up Track Portal logging. Executed inside lifespan startup
    to ensure Uvicorn does not overwrite our handlers.
    """
    logger.setLevel(logging.INFO)
    logger.handlers = []  # Clear to avoid duplicates

    uvicorn_logger = logging.getLogger("uvicorn.error")
    if uvicorn_logger.handlers:
        for h in uvicorn_logger.handlers:
            logger.addHandler(h)
    else:
        # Fallback console handler
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(sh)
    logger.propagate = False

# Programmatically run Alembic migrations on startup
def run_migrations():
    logger.info("Running database migrations via Alembic...")
    try:
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed successfully!")
    except Exception as e:
        logger.error(f"Error running database migrations: {e}")

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

# Middleware to support request.state properties (like CSRF tokens)
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    request.state.user = None
    response = await call_next(request)
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
