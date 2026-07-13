import os
import pytest
from fastapi.testclient import TestClient
from app.main import app

# Force settings to use test database BEFORE importing main or database
os.environ["DATABASE_URL"] = "sqlite:///./test_auth.db"

def test_healthcheck():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
