import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app
from app.models import User
from app.auth import hash_password, COOKIE_NAME
from app.otp import generate_totp_secret, get_hotp_token, verify_totp
import time

# Use a test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_two_factor.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def setup_test_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    db.query(User).delete()

    # Initialize basic test user
    hashed = hash_password("test_pass")
    user = User(username="test_user", password_hash=hashed, is_admin=True)
    db.add(user)
    db.commit()
    db.close()

    yield
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)

def test_login_flow_without_2fa():
    client = TestClient(app)
    response = client.post("/api/auth/login", json={"username": "test_user", "password": "test_pass"})
    assert response.status_code == 200
    data = response.json()
    assert data["two_factor_required"] is False
    assert data["username"] == "test_user"
    assert COOKIE_NAME in response.cookies

def test_login_flow_invalid_credentials():
    client = TestClient(app)
    response = client.post("/api/auth/login", json={"username": "test_user", "password": "wrong_password"})
    assert response.status_code == 401

def test_2fa_setup_and_enable():
    client = TestClient(app)
    # Auth login to get session cookie
    login_resp = client.post("/api/auth/login", json={"username": "test_user", "password": "test_pass"})
    session_cookie = login_resp.cookies.get(COOKIE_NAME)
    client.cookies.set(COOKIE_NAME, session_cookie)

    # Trigger 2FA Setup
    setup_resp = client.post("/api/auth/2fa/setup")
    assert setup_resp.status_code == 200
    setup_data = setup_resp.json()
    secret = setup_data["secret"]
    assert secret is not None
    assert "otpauth_url" in setup_data

    # Get current step token for enabling
    current_step = int(time.time() / 30)
    token_code = str(get_hotp_token(secret, current_step)).zfill(6)

    # Enable 2FA
    enable_resp = client.post("/api/auth/2fa/enable", json={"secret": secret, "code": token_code})
    assert enable_resp.status_code == 200

    # Verify user now has 2FA enabled in DB
    db = TestingSessionLocal()
    user = db.query(User).filter(User.username == "test_user").first()
    assert user.two_factor_enabled is True
    assert user.two_factor_secret == secret
    db.close()

def test_login_flow_with_2fa_enabled():
    # 1. Enable 2FA first
    db = TestingSessionLocal()
    user = db.query(User).filter(User.username == "test_user").first()
    secret = generate_totp_secret()
    user.two_factor_secret = secret
    user.two_factor_enabled = True
    db.commit()
    db.close()

    client = TestClient(app)
    # 2. Step 1: Login with credentials
    login_resp = client.post("/api/auth/login", json={"username": "test_user", "password": "test_pass"})
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert login_data["two_factor_required"] is True
    temp_token = login_data["temp_token"]
    assert temp_token is not None

    # 3. Step 2: Verify with incorrect 2FA token
    verify_failed = client.post("/api/auth/2fa/verify", json={"temp_token": temp_token, "code": "000000"})
    assert verify_failed.status_code == 401

    # 4. Step 2: Verify with correct 2FA token
    current_step = int(time.time() / 30)
    correct_code = str(get_hotp_token(secret, current_step)).zfill(6)
    verify_success = client.post("/api/auth/2fa/verify", json={"temp_token": temp_token, "code": correct_code})
    assert verify_success.status_code == 200
    assert COOKIE_NAME in verify_success.cookies

def test_user_limit_max_2():
    client = TestClient(app)
    login_resp = client.post("/api/auth/login", json={"username": "test_user", "password": "test_pass"})
    session_cookie = login_resp.cookies.get(COOKIE_NAME)
    client.cookies.set(COOKIE_NAME, session_cookie)

    # Create user 2 (success)
    u2_resp = client.post("/api/users", json={"username": "user2", "password": "user2_pass", "is_admin": False})
    assert u2_resp.status_code == 200

    # Try to create user 3 (should fail due to max 2 limit)
    u3_resp = client.post("/api/users", json={"username": "user3", "password": "user3_pass", "is_admin": False})
    assert u3_resp.status_code == 400
    assert u3_resp.json()["detail"] == "Max user limit of 2 reached. Cannot create more users."
