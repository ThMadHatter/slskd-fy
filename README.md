# Track Portal - Production-Ready Self-Hosted Music discovery & Downloader

Track Portal is a production-ready, Spotify-like single track discovery and download application designed exclusively for the Soulseek file-sharing network via the `slskd` REST API.

It runs on **FastAPI**, **SQLite**, **Alembic**, and **Jinja2 + HTMX**, and is specifically constructed to remain isolated from Lidarr/Soularr album workflows.

---

## Folder Structure

```
track_portal/
  ├── app/
  │    ├── __init__.py
  │    ├── main.py                # FastAPI app initialization, lifespans, and middlewares
  │    ├── config.py              # Configuration settings and env variables via Pydantic
  │    ├── database.py            # SQLite database engine and session maker
  │    ├── models.py              # SQLAlchemy DB models (User, History, Wishlist, Favorites, AuditLogs)
  │    ├── schemas.py             # Pydantic schemas for data validation
  │    ├── auth.py                # Password hashing (bcrypt) and session/cookie/CSRF security
  │    ├── services/
  │    │    ├── __init__.py
  │    │    ├── slskd.py          # Real HTTP calls to slskd REST API
  │    │    ├── navidrome.py      # Navidrome rescan & track searching via Subsonic API
  │    │    ├── tagger.py         # Mutagen-based tag writing for FLAC, MP3, M4A, OGG
  │    │    ├── duplicate_detector.py # Multi-source duplicate detection
  │    │    └── downloads_poller.py # Background poller & track organizer
  │    └── templates/             # Jinja2 + HTMX HTML templates
  ├── migrations/                 # Alembic DB migration versions
  ├── tests/                      # Testing suite (60 unit & integration tests)
  ├── Dockerfile                  # Multi-stage optimized Docker setup
  ├── docker-compose.yml          # Container stack orchestration
  ├── .env.example                # Sample environment file
  ├── alembic.ini                 # Alembic migrations configuration
  ├── requirements.txt            # Python dependencies
  └── README.md                   # Deployment and Operational Guide
```

---

## Prerequisites

- Debian 13 (Trixie) or Debian 12 (Bookworm)
- Docker & Docker Compose (v2)
- Access to `slskd` instance (and its REST API key)
- Optional: `Navidrome` instance (for library scanning & integration)
- Optional: `FileBrowser` instance (for directory explorer linking)

---

## Installation & Docker Deployment

### 1. Set up directories
Ensure your Proxmox Debian LXC host mounts the respective music volumes correctly:
- Music Library: `/mnt/music/Music`
- Uploads Directory: `/mnt/music/Uploads`
- Singles Directory: `/mnt/music/Uploads/Singles`
- slskd Downloads: `/mnt/music/Downloads/slskd`
- Config/Database folder: `/mnt/music/Config`

### 2. Download code and configure `.env`
Create your directory, copy the files, and prepare `.env` by copying `.env.example`:
```bash
mkdir -p /mnt/music/Config/track_portal
cd /mnt/music/Config/track_portal
cp .env.example .env
```
Edit `.env` to supply your **slskd API key**, secure passwords, and URLs.

### 3. Deploy Stack
Start the Track Portal container using Docker Compose:
```bash
docker compose up -d --build
```
This will:
- Programmatically execute any pending SQLite migrations.
- Automatically bootstrap the single administrator user using `ADMIN_USERNAME` and `ADMIN_PASSWORD`.
- Start the background downloads polling task.
- Serve the application on `http://localhost:8000`.

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `SLSKD_API_URL` | Full URL to slskd REST API endpoint | `http://localhost:5030/api/v0` |
| `SLSKD_API_KEY` | Key created under slskd yaml config | `your_slskd_api_key_here` |
| `MUSIC_LIBRARY_PATH` | Mount path of your main music library | `/music` |
| `UPLOADS_PATH` | Mount path for uploads | `/uploads` |
| `SINGLES_PATH` | Mount path for single track downloads | `/uploads/Singles` |
| `DOWNLOADS_PATH` | Mount path for slskd downloads | `/downloads` |
| `DATABASE_URL` | SQLAlchemy connection string | `sqlite:////config/track_portal.db` |
| `SECRET_KEY` | Secret key used to sign session cookies | `supersecretkey_change_me_in_production` |
| `ADMIN_USERNAME` | Administrator login name | `admin` |
| `ADMIN_PASSWORD` | Administrator initial bootstrap password | `adminpasswordchange_me` |
| `NAVIDROME_URL` | Base URL of your Navidrome server | `http://localhost:4533` |
| `NAVIDROME_USER` | Navidrome admin username | `admin` |
| `NAVIDROME_PASSWORD`| Navidrome admin password | `navidrome_admin_password` |
| `FILEBROWSER_URL` | Optional: FileBrowser web link | `http://localhost:8080` |
| `NAVIDROME_UI_URL` | Optional: Navidrome UI web link | `http://localhost:4533` |
| `QUALITY_RANKING` | Preference weighting list of formats | `flac,alac,wav,aac,mp3_320,mp3_v0` |

---

## Operational Workflows

### Complete Download Lifecycle
1. **Search**: Search for Artist, Song, or generic query on the **Search** page.
2. **Duplicate warning**: The search result table instantly displays duplicate alerts if matches are found on disk, in SQLite history, or in the Navidrome library.
3. **Queue**: Clicking **Download** enqueues the track to slskd.
4. **Move & Organize**: The background poller monitors progress. Once completed, the file is automatically moved to the singles folder (`SINGLES_PATH`), completely isolated from Lidarr/Soularr download directories. Residual slskd folder files are deleted.
5. **Metadata Queue**: Completed single tracks wait inside the **Metadata Queue** page.
6. **Edit Tags**: Click **Edit Tags** to write standard ID3/Vorbis/MP4 tags (Artist, Album, Title, Year, Genre, Track, Comment, and Cover Art upload) for FLAC, MP3, M4A, or OGG files.
7. **Import**: Clicking **Import to Library** automatically moves the track to the permanent path: `/music/Artist/Album/Artist - Title.ext` and triggers a Navidrome scan.

---

## Security Hardening & Isolation

1. **Isolation**: Completely separates its downloading and staging directories from Soularr and Lidarr. It uses only `UPLOADS_PATH/Singles` for staging.
2. **Authentication**: Form-based sign-in with password verification hashed securely via `Bcrypt (5.0.0)`.
3. **Rate Limiting**: Enforces max 5 login attempts per minute per IP address to block brute force attacks.
4. **Session Expiry**: Handles cookie sessions with standard JWT verification, secure HttpOnly cookie settings, and session extensions for Remember Me.
5. **CSRF Protection**: Universal custom cookie-based token validation verified on all mutable HTMX / Form requests (POST/PUT/DELETE) using header `X-CSRF-Token`.
6. **Audit Logs**: Generates database entries in `AuditLog` for logins, password updates, downloads enqueued, and library imports.

---

## Reverse Proxy Examples

### Nginx Proxy Manager / Nginx config
To map subdomains or paths to Track Portal (port `8000`):
```nginx
server {
    listen 443 ssl;
    server_name track-portal.example.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Session cookie security headers
        proxy_cookie_path / "/; HttpOnly; SameSite=Lax; Secure";
    }
}
```

### Traefik
Add labels to the `docker-compose.yml` service block:
```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.track-portal.rule=Host(`track-portal.example.com`)"
  - "traefik.http.routers.track-portal.entrypoints=websecure"
  - "traefik.http.routers.track-portal.tls.certresolver=myresolver"
  - "traefik.http.services.track-portal.loadbalancer.server.port=8000"
```

### Cloudflare Tunnel (`cloudflared`)
Add ingress rule to `config.yml`:
```yaml
ingress:
  - hostname: track-portal.example.com
    service: http://localhost:8000
```

---

## Maintenance Guides

### Upgrades
To upgrade to a new version of Track Portal:
```bash
docker compose pull
docker compose up -d --build
```

### Backups
To back up the database, wishlist, and favorite files:
```bash
cp /mnt/music/Config/track_portal.db /mnt/music/Backups/track_portal_$(date +%F).db
```

### Restores
To restore from a backup:
```bash
docker compose down
cp /mnt/music/Backups/track_portal_backup_file.db /mnt/music/Config/track_portal.db
docker compose up -d
```

---

## Troubleshooting Guide

#### 1. "Login rate limit exceeded"
- **Cause**: Too many invalid login attempts from your IP.
- **Solution**: Wait 60 seconds for the rate limiter window to clear, or run a python command to clear the DB logs and wait a minute.

#### 2. "CSRF verification failed"
- **Cause**: Browser cookie has expired, or HTMX failed to include the matching token.
- **Solution**: Refresh the page to reload a new secure session token and retry.

#### 3. Slskd downloads completed but not moving to singles folder
- **Cause**: Background poller is looking for the file inside `DOWNLOADS_PATH` but slskd downloaded it to a different sub-folder name.
- **Solution**: Confirm that volume mappings for `/downloads` in `docker-compose.yml` point exactly to the slskd completed directory. Check the Track Portal app logs.

---

## Example Configurations

### slskd YAML config
Ensure API keys are added in `slskd.yml`:
```yaml
web:
  authentication:
    disabled: false
    api_keys:
      portal_key:
        key: "your_slskd_api_key_here"
        role: "Administrator"
        cidr: 0.0.0.0/0
```

### Navidrome integration details
Track Portal communicates via the **Subsonic API**. Trigger scans via:
`/rest/startScan.view?u=admin&t=md5_token&s=salt&v=1.16.0`
This keeps Navidrome instantly indexed.

---

## Expected User Interface Mockups

### 1. Dashboard View
```
+-------------------------------------------------------------------------------+
| TRACK PORTAL                             [Open Singles Folder] [Rescan Library]|
+-------------------------------------------------------------------------------+
|                                                                               |
|  [Wishlist Tracks: 12]  [Active: 2]  [Completed: 45]  [Favorites: 8]          |
|                                                                               |
|  +-------------------------------------+  +--------------------------------+  |
|  | ACTIVE DOWNLOADS                    |  | RECENTLY COMPLETED             |  |
|  |                                     |  |                                |  |
|  | Daft Punk - One More Time           |  | Daft Punk - Instant Crush      |  |
|  | Progress: [=========>      ] 45.0%  |  | Format: MP3 320 [Edit / Import] |  |
|  | Speed: 1.2 MB/s | ETA: 0:00:12      |  |                                |  |
|  +-------------------------------------+  +--------------------------------+  |
+-------------------------------------------------------------------------------+
```

### 2. Search View
```
+-------------------------------------------------------------------------------+
| Search Query: [ Daft Punk ]   [x] FLAC Only   [x] Sort by Quality    [Search] |
+-------------------------------------------------------------------------------+
|                                                                               |
| Results:                                                                      |
| Artist    Track         Format  Bitrate  Size      Queue   Action             |
| --------- ------------- ------- -------- --------- ------- -----------------  |
| Daft Punk Get Lucky     FLAC    1040kbps 32.5 MB   Free    [ Download ]       |
| Daft Punk Instant Crush MP3     320kbps  11.2 MB   Free    [ Already Owned ]  |
+-------------------------------------------------------------------------------+
```
