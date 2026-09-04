import os
import pytest

# Force settings to use test database BEFORE importing main or database
os.environ["DATABASE_URL"] = "sqlite:///./test_auth.db"
from app.config import settings
settings.DATABASE_URL = "sqlite:///./test_auth.db"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db, engine
from app.main import app
from app.models import User, AuditLog
from app.auth import hash_password, COOKIE_NAME, init_admin_user, log_audit_action

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    # Clean tables
    db.query(User).delete()
    db.query(AuditLog).delete()

    # Add test admin user
    hashed = hash_password("testpassword123")
    user = User(username="testadmin", password_hash=hashed, is_admin=True)
    db.add(user)
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)

def test_password_hashing():
    from app.auth import hash_password, verify_password
    pwd = "secretpassword"
    hashed = hash_password(pwd)
    assert verify_password(pwd, hashed) is True
    assert not verify_password("wrong", hashed)

def test_login_flow():
    client = TestClient(app)
    response = client.post(
        "/login",
        data={"username": "testadmin", "password": "testpassword123"},
        follow_redirects=False
    )
    assert response.status_code == 303
    assert COOKIE_NAME in response.cookies

def test_login_invalid_password():
    client = TestClient(app)
    response = client.post(
        "/login",
        data={"username": "testadmin", "password": "wrongpassword"},
        follow_redirects=False
    )
    assert response.status_code == 200
    assert COOKIE_NAME not in response.cookies

def test_logout_flow():
    client = TestClient(app)
    # Login first
    login_resp = client.post(
        "/login",
        data={"username": "testadmin", "password": "testpassword123"},
        follow_redirects=False
    )
    cookie_val = login_resp.cookies.get(COOKIE_NAME)

    # Set cookie in client
    client.cookies.set(COOKIE_NAME, cookie_val)
    response = client.get("/logout", follow_redirects=False)

    # Session cookie should be deleted / empty
    cookie = response.cookies.get(COOKIE_NAME)
    assert cookie is None or cookie == ""

def test_init_admin_user_db_empty(caplog):
    import logging
    db = TestingSessionLocal()
    db.query(User).delete()
    db.commit()

    with caplog.at_level(logging.WARNING):
        init_admin_user(db)

    admin = db.query(User).filter(User.username == settings.ADMIN_USERNAME).first()
    assert admin is not None
    assert admin.is_admin is True
    # Ensure generated random password is NOT present in any log record
    messages = [record.message for record in caplog.records]
    assert any("NO ADMIN PASSWORD CONFIGURED. Generated a secure random initial password" in msg for msg in messages)
    assert not any("GENERATED RANDOM:" in msg for msg in messages)
    db.close()

def test_log_audit_action():
    db = TestingSessionLocal()
    log_audit_action(db, "TEST_ACTION", "Details about test action", "127.0.0.1")

    log = db.query(AuditLog).filter(AuditLog.action == "TEST_ACTION").first()
    assert log is not None
    assert log.details == "Details about test action"
    assert log.ip_address == "127.0.0.1"
    db.close()
