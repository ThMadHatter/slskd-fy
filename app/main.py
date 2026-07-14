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
from app.auth import (
    COOKIE_NAME, decode_access_token, verify_csrf_token, init_admin_user, get_optional_user
)
from app.routers import pages
from app.services.downloads_poller import start_background_poller

# Configure Logging
logger = logging.getLogger("track_portal")
logger.setLevel(logging.INFO)

# Intercept and attach to Uvicorn's logging handlers so logs print inside container console
uvicorn_error_logger = logging.getLogger("uvicorn.error")
if uvicorn_error_logger.handlers:
    logger.handlers = uvicorn_error_logger.handlers
    logger.propagate = False
else:
    # Fallback to standard console stream handler
    sh = logging.StreamHandler()
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
    run_migrations()

    # Initialize Admin user if none exists
    db = SessionLocal()
    init_admin_user(db)
    db.close()

    # Start the background downloads poller
    start_background_poller()

    yield
    # Shutdown actions
    logger.info("Shutting down Track Portal...")

app = FastAPI(
    title="Track Portal",
    description="Spotify-like track discovery and download portal for Soulseek",
    version="1.0.0",
    lifespan=lifespan
)

# Setup Jinja2 Templates
templates = Jinja2Templates(directory="app/templates")

# Mount Static Files (creating the directory if it does not exist)
os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Middleware to load authenticated user and enforce CSRF checks
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # Retrieve user from cookie
    db = SessionLocal()
    token = request.cookies.get(COOKIE_NAME)
    user = None
    if token:
        payload = decode_access_token(token)
        if payload and "sub" in payload:
            from app.models import User
            user = db.query(User).filter(User.username == payload["sub"]).first()

    request.state.user = user
    db.close()

    # Enforce authentication for private routes
    # Exempt login and static routes
    path = request.url.path
    if path not in ["/login", "/health"] and not path.startswith("/static"):
        if not user:
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

        # Enforce CSRF protection for mutable endpoints
        if request.method in ["POST", "PUT", "DELETE"]:
            try:
                verify_csrf_token(request)
            except HTTPException as exc:
                return HTMLResponse(
                    content=f"<div class='p-4 text-center text-rose-400 font-bold'>{exc.detail}</div>",
                    status_code=exc.status_code
                )

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
