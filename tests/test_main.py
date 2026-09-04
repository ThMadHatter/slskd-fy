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
    assert "X-Request-ID" in response.headers

def test_json_logging_format(capsys):
    import json
    import logging
    from app.main import setup_app_logging, logger
    from app.config import settings

    orig_format = settings.LOG_FORMAT
    settings.LOG_FORMAT = "json"
    try:
        setup_app_logging()
        logger.info("Test JSON log message", extra={"correlation_id": "test-id-123"})

        captured = capsys.readouterr()
        assert "Test JSON log message" in captured.out
        assert "test-id-123" in captured.out
    finally:
        settings.LOG_FORMAT = orig_format
        setup_app_logging()
