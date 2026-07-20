import datetime
import logging
import secrets
from typing import Optional, Dict, List
from fastapi import Request, HTTPException, Depends, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import jwt
import bcrypt
from app.config import settings
from app.database import get_db
from app.models import User, AuditLog

logger = logging.getLogger("track_portal.auth")

COOKIE_NAME = "track_portal_session"
CSRF_COOKIE_NAME = "csrf_token"

# Simple in-memory rate limiter for login
LOGIN_ATTEMPTS: Dict[str, List[datetime.datetime]] = {}

def check_login_rate_limit(ip_address: str) -> bool:
    """
    Enforces rate limit on login attempts: max 5 attempts per minute per IP.
    """
    now = datetime.datetime.utcnow()
    # Clean old attempts (> 60 seconds)
    attempts = [t for t in LOGIN_ATTEMPTS.get(ip_address, []) if (now - t).total_seconds() < 60]
    LOGIN_ATTEMPTS[ip_address] = attempts
    if len(attempts) >= 5:
        return True
    attempts.append(now)
    return False

def hash_password(password: str) -> str:
    """Hashes a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    """Verifies a password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None) -> str:
    """Creates a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.utcnow() + expires_delta
    else:
        expire = datetime.datetime.utcnow() + datetime.timedelta(hours=12)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

def decode_access_token(token: str) -> Optional[dict]:
    """Decodes a JWT access token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.PyJWTError:
        return None

def log_audit_action(db: Session, action: str, details: str, ip_address: Optional[str] = None):
    """Writes an entry to the AuditLog database table."""
    try:
        log = AuditLog(
            action=action,
            details=details,
            ip_address=ip_address,
            created_at=datetime.datetime.utcnow()
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to write audit log for action '{action}': {e}")

def init_admin_user(db: Session):
    """
    Checks if there are any users in the DB. If not, creates an initial admin user
    using ADMIN_USERNAME and ADMIN_PASSWORD env variables.
    """
    logger.info("Startup step 3a: Querying User count in database...")
    try:
        user_count = db.query(User).count()
        logger.info(f"Startup step 3b: User count is {user_count}")
        if user_count == 0:
            username = settings.ADMIN_USERNAME or "admin"
            password = settings.ADMIN_PASSWORD

            if not password:
                password = secrets.token_urlsafe(12)
                logger.critical("*" * 60)
                logger.critical(f"NO ADMIN PASSWORD CONFIGURED. GENERATED RANDOM: {password}")
                logger.critical("*" * 60)

            hashed = hash_password(password)
            admin = User(
                username=username,
                password_hash=hashed,
                is_admin=True,
                created_at=datetime.datetime.utcnow()
            )
            db.add(admin)
            db.commit()

            # Log audit action
            log_audit_action(db, "ADMIN_INIT", f"Initial admin user '{username}' initialized.")
            logger.info(f"Initialized database with single admin user: '{username}'")
    except Exception as e:
        logger.error(f"Failed to auto-initialize admin user: {e}")

async def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """
    FastAPI dependency to retrieve the currently logged-in user from the session cookie.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )

    username = payload["sub"]
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    return user

async def get_optional_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Retrieves current user if authenticated, else returns None."""
    try:
        return await get_current_user(request, db)
    except HTTPException:
        return None

def generate_csrf_token() -> str:
    """Generates a secure random CSRF token."""
    return secrets.token_hex(32)

def verify_csrf_token(request: Request):
    """
    Middleware/dependency to verify CSRF token for mutable operations (POST, PUT, DELETE).
    """
    if request.method in ["GET", "HEAD", "OPTIONS"]:
        return

    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
    csrf_header = request.headers.get("X-CSRF-Token")

    if not csrf_cookie:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF cookie missing"
        )

    provided_token = csrf_header or request.query_params.get("csrf_token")

    if not provided_token or not secrets.compare_digest(csrf_cookie, provided_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF verification failed"
        )
