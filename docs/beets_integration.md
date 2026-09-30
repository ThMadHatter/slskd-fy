# Beets GUI Integration & Conflict Resolution

This document details the complete Beets integration in Track Portal.

## Overview
Beets is integrated into Track Portal for non-blocking background music library import, metadata tagging, and interactive conflict resolution via the web interface.

## Installation & Environment
Beets is packaged directly within the container (`beets>=2.14.1`).

### File Paths
- **Isolated YAML Configuration:** `/config/beets/config.yaml` (or app fallback `/app/app/beets_config.yaml`).
- **SQLite Library Database:** `/config/beets/library.db`.
- **Target Music Library:** `/music`.
- **Downloads Directory:** `/downloads`.

## Features

### 1. Settings > Beets Engine (YAML)
- Monospaced YAML configuration editor.
- Atomic configuration saving (`tempfile` + `os.replace` + backup rollback).
- Strict syntax and schema validation (`yaml.MarkedYAMLError` reporting line & column).
- Runtime plugin execution diagnostics panel showing configured vs. loaded vs. failed plugins.
- **Force Reload Plugins:** Dynamically reloads in-memory Beets plugin modules without restarting the web server and captures execution logs in an interactive drawer.

### 2. Background Imports & Non-blocking Processing
- Background import sessions executed via `BeetsImportWorker` in isolated threads.
- Thread-safe tracking of active import jobs (`queued`, `running`, `completed`, `completed_with_conflicts`, `failed`, `cancelled`).
- Conflict collection using `ConflictCollector` during import tasks.

### 3. Beets Review Queue (Conflict Resolution Dashboard)
- **Metrics Bar:** Active tracking of Open, Resolving, Resolved, Skipped, Ignored, and Failed conflicts.
- **Provenance Transparency:** Displays raw embedded file tags, filename-derived metadata, and parent directory context.
- **Candidate Cards:** Shows similarity scores, raw distance penalties, catalog numbers, release types, labels, and direct MusicBrainz links.
- **Manual Search:** Dedicated MBID / search query modal to re-query MusicBrainz for custom candidate matches.
- **Actions:** Accept Candidate, Apply Recommendation, Skip For Now, Ignore / Archive, or Import As-Is.

## Troubleshooting
- **YAML Validation Error:** Correct line/column syntax errors in Settings > Beets Engine before saving.
- **Plugin Loading Failure:** Click "Force Reload Plugins" in Settings to inspect plugin import logs and verify Python dependencies.
- **Database Lock:** SQLite transactions are scoped to short-lived background worker threads. Ensure write operations are not held across HTTP calls.

## Test Suite
Run the test suite using pytest:
```bash
PYTHONPATH=. pytest tests/test_beets_config_service.py tests/test_beets_worker.py tests/test_beets_api.py tests/test_beets_provenance.py tests/test_migrations.py
```
