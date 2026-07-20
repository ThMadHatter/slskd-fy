# Track Portal - Advanced Operations & Troubleshooting Guide

Welcome to the comprehensive operational and architectural documentation for Track Portal's advanced Spotify-like Search and Integrations layer.

---

## 1. Architecture Overview & Metadata Enrichment Pipeline

Track Portal bridges decentralized music sharing (Soulseek) with professional metadata matching (MusicBrainz) and private streaming servers (Navidrome).

```
   Search Request
         │
         ▼
   Autocomplete / Select
         │
         ▼
   Alternative Query Builder (search_ranking_service)
         │
         ▼
   slskd Search Execution
         │
         ▼
┌──────────────────────────────────────────┐
│ METADATA ENRICHMENT PIPELINE             │
│                                          │
│   Search Result (from peer)              │
│         │                                │
│         ▼                                │
│   Filename Parser (clean noise, split)   │
│         │                                │
│         ▼                                │
│   MusicBrainz Lookup (Enrich Album/Year) │
│         │                                │
│         ▼                                │
│   Quality Scoring & Ranking (0-100)      │
└──────────────────────────────────────────┘
         │
         ▼
   Sorted Spotify-like UX Display
```

### 1.1 Metadata Sources & Fallback Priority
When autocompleting, the application queries metadata sources in a strict priority order to optimize query latency and prevent unnecessary external API hits:

#### Artist Autocomplete:
1. **MusicBrainz Search API**: Queries the live MusicBrainz artist index using standard HTTP REST queries.
2. **Lidarr API**: Secondary fallback queried via the Lidarr Integration client if configured and active.
3. **Local Cache / Database**: Falls back to existing database history and cached metadata when external APIs are unreachable or unconfigured.

#### Track Autocomplete:
1. **MusicBrainz Recordings API**: Performs structured searches scoped to the selected artist's MusicBrainz ID (MBID) or name.
2. **Navidrome Subsonic API**: Queries matching track objects from your local library.
3. **Local Cache / Database**: Falls back to history of completed tracks.

### 1.2 Caching Strategy & Configurable TTL
To prevent MusicBrainz rate limit blocks (1 req/sec) and minimize network latency, every API search is intercepted by a **Local SQLite Cache Layer** (`CacheEntry` and `CacheMetric` tables):
- **Configurable TTL**: Defaults to 24 hours (`86400` seconds).
- **Background Cleanup**: Automatically removes expired keys during background loop iterations.
- **Cache Efficiency Metrics**: Displayed on the Dashboard, reporting hits and misses for Artist, Track, and MusicBrainz lookups.

---

## 2. Filename Parser & Intelligent Inference

Many slskd peers report files with `Artist = Unknown` and `Album = Unknown` tags. To solve this, the **Filename Parser** (`app/services/filename_parser.py`) executes rule-based regex extraction:

### 2.1 Supported Patterns
- **Standard Splitting**: `Artist - Track` or `Artist - Album - Track`.
- **Scene Releases**: Detects and replaces dots/underscores, parses trailing years and groups (e.g., `Kendrick_Lamar-Not_Like_Us-2024-GRP.flac` -> Artist: Kendrick Lamar, Track: Not Like Us, Year: 2024).
- **Track & Disc Prefixes**: Automatically extracts and strips indices like `01 - `, `1-01 `, `CD1 - 03 - `.
- **Bracket Noise Stripping**: Removes brackets and flags like `[FLAC]`, `(320kbps)`, `[Lossless]`, `(Official Video)`.

### 2.2 Enrichment Pipeline
If the parsed result is successfully mapped to an artist but is missing an album or release year, the pipeline conducts a **Soft MusicBrainz match**. If found, the metadata is enriched in-memory before display, reducing the occurrence of "Unknown" values to near zero.

---

## 3. Smarter Search Ranking & Quality Scoring

Queries are scored from **0 to 100** so users can quickly locate high-quality, verified tracks.

### 3.1 Scoring Algorithm Weights
- **Artist Match (30 pts)**: Exact match gets 30, partial/substring gets 15.
- **Track Match (30 pts)**: Exact match gets 30, partial gets 15.
- **Album Match (10 pts)**: Exact match gets 10, partial gets 5.
- **Codec Format (15 pts)**: Lossless (FLAC/ALAC/WAV) gets 15, M4A/AAC gets 10, MP3 gets 8.
- **Bitrate (10 pts)**: Lossless gets 10, >=320 kbps gets 8, >=256 kbps gets 6, >=192 kbps gets 4.
- **Sample Rate (5 pts)**: >=96 kHz gets 5, >=48 kHz gets 4, 44.1 kHz gets 3.
- **File Size (5 pts)**: Promotes files > 1 MB (protects against fake/empty files).

---

## 4. Navidrome Integration & Diagnostics

The Navidrome client has been upgraded with **Actionable Diagnostics** and explicit Subsonic path validation.

### 4.1 Diagnostics Table
If the Dashboard reports a connection issue, it inspects the exact error type:
- **Connection Refused**: Actionable advice on Docker network bridge loop (reminds user that `localhost` within a container points to itself, and to use `host.docker.internal` instead).
- **Subsonic Auth Error**: Pinpoints whether the token, salt, or admin credentials did not pass Subsonic MD5 authentication.
- **Timeout**: Suggests checking firewall rules or server responsiveness.

---

## 5. Deployment & Operations Guide

### 5.1 Security Hardening
- **Authentication**: Bcrypt hashing of passwords with high-cost salt factors.
- **Session Security**: Session tokens are stored in `HttpOnly`, `SameSite=Lax` secure cookies.
- **Universal CSRF protection**: Verified via header `X-CSRF-Token` on all HTMX mutable requests.
- **Login Rate Limiting**: REST and form requests are rate-limited to 5 attempts per minute per IP.

### 5.2 Backup & Restore Guide
1. **Back up Database**:
   ```bash
   cp /config/track_portal.db /backups/track_portal_$(date +%F).db
   ```
2. **Restore Database**:
   ```bash
   docker compose down
   cp /backups/track_portal_backup_file.db /config/track_portal.db
   docker compose up -d
   ```

### 5.3 Docker Compose Configuration
```yaml
services:
  track-portal:
    image: track-portal:latest
    container_name: track_portal
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=sqlite:////config/track_portal.db
      - SLSKD_API_URL=http://host.docker.internal:5030/api/v0
      - SLSKD_API_KEY=your_key
      - NAVIDROME_URL=http://host.docker.internal:4533
      - NAVIDROME_USER=admin
      - NAVIDROME_PASSWORD=navidrome_password
    volumes:
      - /mnt/music/Config:/config
      - /mnt/music/Music:/music
      - /mnt/music/Uploads/Singles:/uploads/Singles
    restart: unless-stopped
```
