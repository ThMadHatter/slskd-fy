import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_access_token, COOKIE_NAME, hash_password
from app.database import Base, engine, SessionLocal
from app.models import User


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        admin = User(username="admin", password_hash=hash_password("admin123"), is_admin=True)
        db.add(admin)
        db.commit()
    db.close()


@pytest.fixture
def auth_client():
    client = TestClient(app)
    token = create_access_token({"sub": "admin"})
    client.cookies.set(COOKIE_NAME, token)
    return client


def test_get_beets_config_endpoint(auth_client):
    response = auth_client.get("/api/beets/config")
    assert response.status_code == 200
    data = response.json()
    assert "yaml_text" in data
    assert "is_valid" in data
    assert "configured_plugins" in data


def test_validate_beets_config_endpoint(auth_client):
    valid_payload = {"yaml_text": "directory: /music\nimport:\n  quiet: yes\n"}
    response = auth_client.post("/api/beets/config/validate", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True

    invalid_payload = {"yaml_text": "directory: /music\n  unclosed: [bad"}
    response_inv = auth_client.post("/api/beets/config/validate", json=invalid_payload)
    assert response_inv.status_code == 200
    data_inv = response_inv.json()
    assert data_inv["valid"] is False


def test_save_beets_config_endpoint(auth_client, tmp_path, monkeypatch):
    target_config = tmp_path / "beets_config.yaml"
    from app.services.beets_config_service import BeetsConfigService
    monkeypatch.setattr(BeetsConfigService, "resolve_config_path", lambda override_path=None: str(target_config))

    valid_payload = {"yaml_text": "directory: /tmp/music\nlibrary: /tmp/library.db\n"}
    response = auth_client.post("/api/beets/config", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["runtime_restart_required"] is True


def test_get_beets_status_endpoint(auth_client):
    response = auth_client.get("/api/beets/status")
    assert response.status_code == 200
    data = response.json()
    assert "beet_cli_available" in data
    assert "library_track_count" in data


def test_beets_import_and_jobs_endpoints(auth_client, tmp_path):
    import_dir = tmp_path / "downloads"
    import_dir.mkdir()

    response = auth_client.post("/api/beets/import", json={"source_path": str(import_dir)})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "job_id" in data

    job_id = data["job_id"]
    jobs_response = auth_client.get("/api/beets/jobs")
    assert jobs_response.status_code == 200
    jobs_list = jobs_response.json()
    assert any(j["job_id"] == job_id for j in jobs_list)

    job_detail = auth_client.get(f"/api/beets/jobs/{job_id}")
    assert job_detail.status_code == 200
    assert job_detail.json()["job_id"] == job_id
