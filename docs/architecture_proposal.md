# Track Portal: Single Orchestration Layer Architecture Proposal
**Target Stack**: Track Portal ⇄ slskd ⇄ Beets ⇄ Navidrome
**Design Philosophy**: TRACK-FIRST, minimal, extremely fast, uncluttered (Google/Spotify Search aesthetic).
**Core Mantra**: "Search quality is more important than feature count."

---

## 1. Proposed Architecture

Under the new architecture, **Track Portal becomes the single decision-making orchestration layer**. All file management, scheduling, quality ranking, and integration triggers are centralized here. Third-party automation tools (such as Lidarr, Soularr, or custom external cron scripts) are completely decoupled from the system.

### 1.1 Architectural Flow Diagram

```
                        ┌────────────────────────┐
                        │      TRACK PORTAL      │
                        │ (Single Decision Maker)│
                        └──────────┬───┬─────────┘
                                   │   │
           1. Trigger Download     │   │ 3. Execute Non-Interactive Import
                                   ▼   ▼
                        ┌──────────────┐ ┌──────────────┐
                        │    slskd     │ │    Beets     │
                        │ (Soulseek)   │ │  (Importer)  │
                        └──────────────┘ └──────┬───────┘
                                                │
                                                │ 4. Organized & Normalized Files
                                                ▼
                                         ┌──────────────┐
                                         │  Music Lib   │
                                         │ (/mnt/music) │
                                         └──────┬───────┘
                                                │
                                                │ 5. Trigger Library Rescan
                                                ▼
                                         ┌──────────────┐
                                         │  Navidrome   │
                                         │  (Streamer)  │
                                         └──────────────┘
```

### 1.2 Core Design Principles
1. **Search is the Homepage**:
   - No complex dashboards, no statistics walls, and no download history displayed on first load.
   - The landing page is a clean, hyper-focused search interface (similar to Google or Spotify Search).
2. **Track-Centricity**: The system default is single-track accuracy (Search -> Download -> Beets singleton import -> Navidrome rescan). Album search and imports remain secondary.
3. **Decoupled Folder Isolation**:
   - Incoming downloads path: `/mnt/music/Downloads/slskd`
   - Permanent target library: `/mnt/music/Music`

---

## 2. Database Schema Changes

To support the lightweight "Wanted" monitoring system, we introduce a dedicated database table `wanted_items`. This table keeps track of active monitoring targets, and scheduling metadata.

### 2.1 Schema Definition (SQLAlchemy Model)

```python
import datetime
from sqlalchemy import Column, Integer, String, DateTime
from app.database import Base

class WantedItem(Base):
    __tablename__ = "wanted_items"

    id = Column(Integer, primary_key=True, index=True)

    # Core search target information
    query = Column(String, nullable=False, index=True) # E.g., "Pink Floyd - Time" or "Rare bootleg 1981"
    type = Column(String, nullable=False, default="track") # "track", "album", or "arbitrary_query"

    # State and tracking information
    status = Column(String, default="monitored") # "monitored", "searching", "downloading", "completed", "failed"
    attempts = Column(Integer, default=0, nullable=False)
    last_checked = Column(DateTime, nullable=True)
    best_score = Column(Integer, default=0, nullable=False) # Best candidate quality score (0-100)

    # Audit timestamps
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
```

### 2.2 Schema Update & Migrations Plan
We generate the SQLite DB schema change programmatically via Alembic:
```bash
docker compose exec track-portal alembic revision --autogenerate -m "create_wanted_items"
docker compose exec track-portal alembic upgrade head
```

---

## 3. API & UI Layout Changes

### 3.1 Homepage Layout (The Search Experience)

The home page (`/`) is redesigned to be clean and minimal. It contains:
1. **Search Mode Selector**: Toggle tabs/buttons for `Track` or `Album`.
2. **Master Mode Selector Toggle**:
   ```
   [ Structured Search ] [ Keyword Search ]
   ```
   - **Structured Search**: Form fields for `Artist Name` and `Track/Album Title`.
   - **Keyword Search**: A single, clean free-text box (e.g., "Pink Floyd Time", "Rare bootleg 1981").
3. **Minimal Discover Section**: Positioned directly below the search box, keeping it secondary.
   - *Trending in Library* or *Recently Added* (limit 3 items max).
   - This must never dominate or clutter the landing page.

### 3.2 Monitored / Settings Endpoints

| Method | Endpoint | Description |
|---|---|---|
| **GET** | `/wanted` | Minimal UI listing active monitored items |
| **POST** | `/api/wanted/create` | Adds a track, album, or raw query to the monitoring queue |
| **DELETE** | `/api/wanted/{id}` | Removes an item from the monitored system |
| **POST** | `/api/wanted/{id}/toggle` | Pauses/resumes monitoring for an item |
| **GET** | `/settings` | Single, consolidated settings panel |

### 3.3 Minimal Settings Layout
The complex configuration forms are replaced with a single minimal page, containing fields only for:
- **slskd Config**: API URL & Key.
- **Navidrome Config**: API URL, User, Password, and Token.
- **Last.fm Integration**: API Key & Secret.
- **Beets Config**: Base library paths.
- **Monitoring Rules**: Score trigger thresholds (Default: `85`).

---

## 4. Beets Integration Design

Beets is used exclusively in the background to handle **metadata normalization, naming consistency, duplicate matching, and album folder consistency**. It requires zero manual user intervention.

### 4.1 Non-Interactive Beets Configuration (`/config/beets/config.yaml`)

```yaml
directory: /mnt/music/Music
library: /config/beets/library.db

import:
    write: yes
    copy: yes
    move: no
    autotag: yes
    quiet: yes                 # Prevents beets from waiting for interactive CLI input
    timid: no                  # Auto-applies high confidence matches
    resume: no
    incremental: yes
    none_rec_action: ask       # In quiet mode, skips low confidence matches automatically
    log: /config/beets/import.log

plugins: fetchart embedart mbsync duplicates inline

paths:
    default: $albumartist/$album%a_num ($year)/$artist - $title
    singleton: Non-Album/$artist/$artist - $title
```

### 4.2 Automated Subprocess Execution In Track Portal

The background download poller detects completed slskd downloads inside `/mnt/music/Downloads/slskd` and immediately launches a non-interactive Beets subprocess:

*   **Track Download**:
    ```bash
    beet import -q -s /mnt/music/Downloads/slskd/completed_track.mp3
    ```
*   **Album Download**:
    ```bash
    beet import -q /mnt/music/Downloads/slskd/completed_album_folder
    ```

```python
async def trigger_beets_import(path: str, is_singleton: bool = True):
    """
    Spawns beets import command as a background async subprocess.
    """
    cmd = ["beet", "import", "-q"]
    if is_singleton:
        cmd.append("-s")
    cmd.append(path)

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return process.returncode == 0
```

---

## 5. Monitoring Subsystem & Scheduled Tasks

A lightweight scheduler task runs continuously inside the Track Portal lifespan.

### 5.1 Scheduled Jobs Frequencies

1. **Track Monitoring**: Evaluated **every 6 hours**.
2. **Album Monitoring**: Evaluated **every 12 hours**.
3. **Library Rescan**: Initiated **daily** (via Navidrome Subsonic rescan trigger).
4. **Last.fm Recommendation Refresh**: Executed **daily**.
5. **Cleanup of Failed Searches**: Runs **weekly** (purges or archives failed monitoring items).

### 5.2 Searching, Ranking, and Download Decision Cycle

For each monitored "Wanted" item, the automated cycle is as follows:
1. **Query Generation**: Format search target using normalization rules (strip file type noise, special characters, and double quotes from inputs).
2. **slskd Search**: Trigger background Soulseek searches using the `SlskdClient`.
3. **Ranking & Quality Evaluation**:
   - Match results using **fuzzy scoring** (Levenshtein distance ratio matching) on title and artist.
   - Enforce **normalization** on parsed filenames.
   - Calculate quality score based on format, size, sample rate, and bitrate.
4. **Threshold Guard**: If the highest-ranked search result score meets or exceeds the threshold (e.g., `85/100`):
   - **Download**: Enqueue download via `slskd`.
   - **Status Update**: Set the Wanted item status to `downloading`.
   - **Track Polling**: Background poller watches progress. Once completed, moves file to singles folder, triggers **Beets auto-import**, sets status to `completed`, and fires a Navidrome scan.

---

## 6. Migration Plan from Current Architecture

### 6.1 Step-by-Step Transition

#### Step 1: Base Environment Update
Upgrade the Track Portal base Docker container to package Beets and python dependencies.
```dockerfile
RUN apt-get update && apt-get install -y beets python3-musicbrainzngs
```

#### Step 2: Database Upgrade
Apply the additive Alembic migration to include the `wanted_items` table. Existing favorites, search histories, and users remain intact.

#### Step 3: Implement Homepage and Settings Redesign
- Replace the current metrics dashboard with the Google/Spotify-inspired search interface.
- Replace complex multi-page configuration screens with the single-panel minimal Settings view.

#### Step 4: Hook Beets into Background Poller
Replace the classic Mutagen tagger and filesystem copy mechanism inside `downloads_poller.py` with the automated Beets CLI import subprocess trigger.

#### Step 5: Activate Scheduled Tasks Loop
Launch the monitoring scheduler task in the FastAPI startup sequence (`app/main.py`), registering the 6-hour track and 12-hour album cron triggers.

---

### 6.2 Roll-back Plan
In case of import failure or misaligned metadata tagging:
1. Revert to the pre-upgrade SQLite backup (`track_portal.db`).
2. Rollback the Docker image to the previous container tags, restoring the classic manual tag editor and direct filesystem importer.
