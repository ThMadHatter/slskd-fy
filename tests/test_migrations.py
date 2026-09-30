import os
import tempfile
import uuid
import hashlib
import sqlite3
import pytest
from sqlalchemy import create_engine, text
from alembic.config import Config
from alembic import command


def test_migrations_fresh_and_existing_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        # Step 1: Simulate old schema prior to migration
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Create old alembic_version table at previous head a41f121fd3e1
        cur.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY);")
        cur.execute("INSERT INTO alembic_version VALUES ('a41f121fd3e1');")

        # Create old beets_review_items schema
        cur.execute("""
            CREATE TABLE beets_review_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                download_id INTEGER,
                artist VARCHAR NOT NULL,
                track VARCHAR NOT NULL,
                album VARCHAR,
                downloaded_path VARCHAR NOT NULL,
                confidence_score INTEGER DEFAULT 50,
                status VARCHAR DEFAULT 'review_required',
                candidates_json VARCHAR NOT NULL,
                selected_match_json VARCHAR,
                created_at DATETIME,
                updated_at DATETIME
            );
        """)

        # Insert test row into old schema
        cur.execute("""
            INSERT INTO beets_review_items (download_id, artist, track, album, downloaded_path, confidence_score, status, candidates_json)
            VALUES (101, 'Aphex Twin', 'Pulsewidth', 'SAW 85-92', '/downloads/aphex.flac', 60, 'review_required', '[]');
        """)
        conn.commit()
        conn.close()

        # Step 2: Run Alembic upgrade to head against this existing DB
        db_url = f"sqlite:///{db_path}"
        os.environ["DATABASE_URL"] = db_url
        from app.config import settings
        settings.DATABASE_URL = db_url

        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)
        command.upgrade(alembic_cfg, "head")

        # Step 3: Inspect database table info with PRAGMA table_info
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Check table columns
        cur.execute("PRAGMA table_info(beets_review_items);")
        cols = {row[1]: row for row in cur.fetchall()}

        expected_new_cols = [
            "conflict_id", "fingerprint", "job_id", "item_type",
            "differences_json", "recommendation_text", "error_message",
            "retry_count", "resolution_audit"
        ]
        for col in expected_new_cols:
            assert col in cols, f"Column {col} missing from migrated beets_review_items"

        # Check backfilled data row
        cur.execute("SELECT id, conflict_id, fingerprint, status, item_type, retry_count FROM beets_review_items WHERE id = 1;")
        row = cur.fetchone()
        assert row is not None
        assert row[0] == 1
        assert row[1] is not None and len(row[1]) == 36 # valid UUID
        assert row[2] is not None and len(row[2]) == 64 # sha256 hex
        assert row[3] == "open" # normalized from review_required
        assert row[4] == "album"
        assert row[5] == 0

        # Verify beets_import_jobs table was created
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='beets_import_jobs';")
        assert cur.fetchone() is not None

        conn.close()

        # Step 4: Test downgrade
        command.downgrade(alembic_cfg, "a41f121fd3e1")

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(beets_review_items);")
        cols_after_downgrade = {row[1]: row for row in cur.fetchall()}
        assert "conflict_id" not in cols_after_downgrade
        assert "fingerprint" not in cols_after_downgrade

        # Verify beets_import_jobs dropped
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='beets_import_jobs';")
        assert cur.fetchone() is None
        conn.close()

        # Step 5: Test upgrade again (Idempotency check)
        command.upgrade(alembic_cfg, "head")

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
