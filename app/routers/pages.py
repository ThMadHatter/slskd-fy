import os
import shutil
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models import User, Wishlist, Favorites, DownloadHistory, SearchHistory, AuditLog
from app.auth import (
    get_current_user, get_optional_user, create_access_token, COOKIE_NAME, CSRF_COOKIE_NAME,
    generate_csrf_token, verify_password, hash_password, verify_csrf_token, log_audit_action,
    check_login_rate_limit
)
from app.services.slskd import SlskdClient
from app.services.navidrome import NavidromeClient
from app.services.duplicate_detector import check_duplicate
from app.services.tagger import read_tags, write_tags

logger = logging.getLogger("track_portal.pages")

router = APIRouter()

# Helper function to inject common variables into templates (csrf, user, etc)
def render_template(template_name: str, request: Request, context: dict) -> HTMLResponse:
    from app.main import templates

    # Generate or fetch CSRF token
    csrf_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not csrf_token:
        csrf_token = generate_csrf_token()

    context.update({
        "request": request,
        "csrf_token": csrf_token,
        "user": context.get("user") or request.state.user if hasattr(request.state, "user") else None,
        "filebrowser_url": settings.FILEBROWSER_URL,
        "navidrome_ui_url": settings.NAVIDROME_UI_URL,
        "settings": settings
    })

    response = templates.TemplateResponse(request=request, name=template_name, context=context)
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,  # Needs to be readable by HTMX/JS
        samesite="lax",
        secure=False     # Change to True if HTTPS
    )
    return response

# --- Auth Pages ---

@router.get("/login", response_class=HTMLResponse)
async def get_login(request: Request, user: Optional[User] = Depends(get_optional_user)):
    if user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return render_template("login.html", request, {"error": None})

@router.post("/login")
async def post_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    remember_me: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    ip_address = request.client.host if request.client else "unknown"

    # Rate Limiting Check on Login
    if check_login_rate_limit(ip_address):
        logger.warning(f"Login rate limit exceeded for IP: {ip_address}")
        log_audit_action(db, "LOGIN_BLOCKED", f"Rate limit exceeded for IP: {ip_address}", ip_address)
        return render_template("login.html", request, {"error": "Too many login attempts. Please wait a minute."})

    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        log_audit_action(db, "LOGIN_FAILED", f"Failed login attempt for user '{username}'", ip_address)
        return render_template("login.html", request, {"error": "Invalid username or password"})

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    # Log Successful Login Action
    log_audit_action(db, "LOGIN_SUCCESS", f"User '{username}' logged in successfully.", ip_address)

    # Create session token with secure cookie configuration
    expires = timedelta(days=30) if remember_me else timedelta(hours=12)
    token = create_access_token({"sub": user.username}, expires_delta=expires)

    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # True in prod behind HTTPS
        max_age=int(expires.total_seconds())
    )
    return response

@router.get("/logout")
async def get_logout(request: Request, db: Session = Depends(get_db), user: Optional[User] = Depends(get_optional_user)):
    if user:
        ip_address = request.client.host if request.client else "unknown"
        log_audit_action(db, "LOGOUT", f"User '{user.username}' logged out.", ip_address)

    response = RedirectResponse(url="/login")
    response.delete_cookie(COOKIE_NAME)
    return response

# --- Dashboard, Search and Downloads pages ---

@router.get("/", response_class=HTMLResponse)
async def root_redirect(user: Optional[User] = Depends(get_optional_user)):
    if user:
        return RedirectResponse(url="/dashboard")
    return RedirectResponse(url="/login")

@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wishlist_count = db.query(Wishlist).filter(Wishlist.status != "imported").count()
    favorites_count = db.query(Favorites).count()

    active_downloads = db.query(DownloadHistory).filter(DownloadHistory.status.in_(["downloading", "queued"])).all()
    completed_count = db.query(DownloadHistory).filter(DownloadHistory.status == "completed").count()

    recent_downloads = db.query(DownloadHistory).order_by(DownloadHistory.downloaded_at.desc()).limit(10).all()

    duplicate_warnings = []
    for dl in active_downloads:
        dup = await check_duplicate(db, dl.artist, dl.track)
        if dup["is_duplicate"]:
            duplicate_warnings.append({"artist": dl.artist, "track": dl.track})

    stats = {
        "wishlist_count": wishlist_count,
        "favorites_count": favorites_count,
        "active_downloads_count": len(active_downloads),
        "completed_count": completed_count,
        "active_downloads": active_downloads,
        "recent_downloads": recent_downloads,
        "duplicate_warnings": duplicate_warnings
    }

    return render_template("dashboard.html", request, {
        "active_page": "dashboard",
        "stats": stats,
        "user": user
    })

@router.get("/search", response_class=HTMLResponse)
async def get_search(
    request: Request,
    artist: Optional[str] = None,
    track: Optional[str] = None,
    user: User = Depends(get_current_user)
):
    return render_template("search.html", request, {
        "active_page": "search",
        "artist": artist,
        "track": track,
        "user": user
    })

@router.post("/search/results", response_class=HTMLResponse)
async def post_search_results(
    request: Request,
    artist: Optional[str] = Form(None),
    track: Optional[str] = Form(None),
    query: Optional[str] = Form(None),
    flac_only: Optional[str] = Form(None),
    lossless_only: Optional[str] = Form(None),
    mp3_only: Optional[str] = Form(None),
    min_bitrate: Optional[str] = Form(None),
    max_size: Optional[str] = Form(None),
    sort_by: str = Form("quality"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    search_query = query
    if not search_query:
        parts = []
        if artist: parts.append(artist)
        if track: parts.append(track)
        search_query = " - ".join(parts)

    if not search_query:
        return "<div class='p-6 text-center text-rose-400'>Please enter a search query.</div>"

    slskd_client = SlskdClient()
    try:
        search_obj = await slskd_client.search(search_query)
        search_id = search_obj.get("id")
        if not search_id:
            return "<div class='p-6 text-center text-rose-400'>Failed to start search in slskd.</div>"

        await asyncio.sleep(4.0)
        responses = await slskd_client.get_search_responses(search_id)

        results: List[Dict[str, Any]] = []
        for resp in responses:
            username = resp.get("username", "")
            queue_length = resp.get("queueLength", 0)
            files = resp.get("files", [])
            for f in files:
                filename = f.get("filename", "")
                ext = os.path.splitext(filename)[1].lstrip(".").lower()
                size = f.get("size", 0)
                bitrate = f.get("bitRate", 0)
                sample_rate = f.get("sampleRate", 0)

                file_artist = artist or ""
                file_track = track or os.path.splitext(os.path.basename(filename))[0]

                results.append({
                    "artist": file_artist or "Unknown",
                    "track": file_track,
                    "album": f.get("album", "") or "",
                    "filename": filename,
                    "size": size,
                    "username": username,
                    "format": ext,
                    "bitrate": bitrate,
                    "sample_rate": sample_rate,
                    "queue_length": queue_length
                })

        # --- Apply Filters ---
        filtered_results: List[Dict[str, Any]] = []
        for r in results:
            fmt = r["format"]
            if flac_only and fmt != "flac":
                continue
            if lossless_only and fmt not in ["flac", "wav", "alac", "ape", "aiff"]:
                continue
            if mp3_only and fmt != "mp3":
                continue
            if min_bitrate:
                try:
                    if r["bitrate"] and r["bitrate"] < int(min_bitrate):
                        continue
                except ValueError:
                    pass
            if max_size:
                try:
                    max_bytes = int(max_size) * 1024 * 1024
                    if r["size"] and r["size"] > max_bytes:
                        continue
                except ValueError:
                    pass
            filtered_results.append(r)

        # --- Preferred Download Quality Ranking (Configurable) ---
        # Quality list: FLAC, ALAC, WAV, AAC, MP3 320, MP3 V0, etc
        ranking_list = [f.strip().lower() for f in settings.QUALITY_RANKING.split(",")]

        def get_sort_key(item):
            fmt = item["format"].lower()
            bitrate = item["bitrate"] or 0

            # Find weight from ranking
            weight = -999
            if fmt == "flac" and "flac" in ranking_list:
                weight = 100 - ranking_list.index("flac")
            elif fmt == "alac" and "alac" in ranking_list:
                weight = 100 - ranking_list.index("alac")
            elif fmt == "wav" and "wav" in ranking_list:
                weight = 100 - ranking_list.index("wav")
            elif fmt == "aac" and "aac" in ranking_list:
                weight = 100 - ranking_list.index("aac")
            elif fmt == "mp3" and bitrate >= 320 and "mp3_320" in ranking_list:
                weight = 100 - ranking_list.index("mp3_320")
            elif fmt == "mp3" and bitrate >= 220 and "mp3_v0" in ranking_list:
                weight = 100 - ranking_list.index("mp3_v0")
            elif fmt in ranking_list:
                weight = 100 - ranking_list.index(fmt)

            if sort_by == "quality":
                return (weight, bitrate)
            elif sort_by == "size_desc":
                return (item["size"] or 0,)
            elif sort_by == "size_asc":
                return (-(item["size"] or 0),)
            elif sort_by == "queue":
                return (-item["queue_length"], weight)
            return (weight, bitrate)

        filtered_results.sort(key=get_sort_key, reverse=True if sort_by in ["quality", "size_desc"] else False)

        # Duplicate detection warning
        for r in filtered_results:
            dup_info = await check_duplicate(db, r["artist"], r["track"])
            if dup_info["is_duplicate"]:
                r["duplicate_warning"] = dup_info["warning_message"]
            else:
                r["duplicate_warning"] = None

        # Track Search History in DB
        hist = SearchHistory(query=search_query, result_count=len(filtered_results))
        db.add(hist)
        db.commit()

        await slskd_client.delete_search(search_id)

        return render_template("search_results.html", request, {
            "results": filtered_results,
            "user": user
        })
    except Exception as e:
        logger.error(f"Error executing search: {e}")
        error_msg = str(e)
        if "Name or service not known" in error_msg or "ConnectError" in error_msg or "ConnectTimeout" in error_msg or "gaierror" in error_msg or "connection attempts failed" in error_msg.lower():
            return f"""
            <div class='p-6 border border-rose-500/30 bg-rose-500/10 rounded-xl space-y-4 max-w-2xl mx-auto my-4 text-left'>
                <div class='flex items-start space-x-3 text-rose-400'>
                    <i class='fa-solid fa-triangle-exclamation text-2xl shrink-0 mt-0.5'></i>
                    <div>
                        <h4 class='font-bold text-lg'>Connection to slskd API Failed</h4>
                        <p class='text-sm mt-1'>Track Portal was unable to resolve or reach the slskd server address at <strong class='underline'>{settings.SLSKD_API_URL}</strong>.</p>
                    </div>
                </div>
                <div class='text-xs text-slate-300 space-y-2 border-t border-slate-700/80 pt-3 pl-9'>
                    <p class='font-semibold text-slate-200'>Troubleshooting & Guidance:</p>
                    <ul class='list-disc pl-4 space-y-1.5'>
                        <li>Verify that <strong>SLSKD_API_URL</strong> in your <code>.env</code> file is correct and accessible.</li>
                        <li><strong>Docker Host & Localhost Notice:</strong> Since Track Portal is running inside a Docker container, using <code>localhost</code> or <code>127.0.0.1</code> will look inside the Track Portal container itself rather than your host. If slskd is running on your host machine or in a separate container, use <strong><code>http://host.docker.internal:5030/api/v0</code></strong>, your host's actual IP address (e.g., <code>http://172.17.0.1:5030/api/v0</code>), or the slskd container's service name (e.g., <code>http://slskd:5030/api/v0</code>).</li>
                        <li>If running in Docker Compose, ensure both Track Portal and slskd are on the <strong>same Docker network</strong>.</li>
                        <li>Check if the slskd container is currently running and healthy.</li>
                        <li>The raw error was: <code class='text-rose-300 bg-rose-950/40 px-1 py-0.5 rounded font-mono'>{error_msg}</code></li>
                    </ul>
                </div>
            </div>
            """
        return f"<div class='p-6 text-center text-rose-400'>Error executing search: {e}</div>"

@router.post("/downloads/create")
async def post_downloads_create(
    request: Request,
    artist: str = Form(...),
    track: str = Form(...),
    album: Optional[str] = Form(""),
    filename: str = Form(...),
    size: int = Form(...),
    username: str = Form(...),
    format: str = Form(...),
    bitrate: Optional[int] = Form(0),
    sample_rate: Optional[int] = Form(0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    slskd_client = SlskdClient()
    success = await slskd_client.enqueue_download(username, filename, size)

    if success:
        # Create DownloadHistory entry with 'downloading' status
        history_entry = DownloadHistory(
            search_query=f"{artist} - {track}",
            artist=artist,
            track=track,
            album=album or "",
            filename=os.path.basename(filename),
            download_id=None,
            source_user=username,
            format=format,
            bitrate=bitrate,
            sample_rate=sample_rate,
            size_bytes=size,
            status="downloading",
            downloaded_at=datetime.utcnow()
        )
        db.add(history_entry)

        # Mark wishlist item status to "searching"
        wishlist_item = db.query(Wishlist).filter(
            Wishlist.artist == artist,
            Wishlist.track == track,
            Wishlist.status != "imported"
        ).first()
        if wishlist_item:
            wishlist_item.status = "searching"

        db.commit()

        # Log Audit Action
        ip_address = request.client.host if request.client else "unknown"
        log_audit_action(db, "DOWNLOAD_START", f"User '{user.username}' enqueued download for '{artist} - {track}' from user '{username}'", ip_address)

        return "<span class='text-emerald-400 font-semibold text-xs flex items-center space-x-1'><i class='fa-solid fa-cloud-arrow-down mr-1'></i>Downloading...</span>"
    else:
        return "<span class='text-rose-400 font-semibold text-xs'>Failed to start download</span>"

@router.get("/downloads", response_class=HTMLResponse)
async def get_downloads_page(request: Request, user: User = Depends(get_current_user)):
    return render_template("downloads.html", request, {
        "active_page": "downloads",
        "user": user
    })

@router.get("/downloads/list", response_class=HTMLResponse)
async def get_downloads_list(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db_downloads = db.query(DownloadHistory).filter(
        DownloadHistory.status.in_(["downloading", "queued", "pending"])
    ).all()

    slskd_client = SlskdClient()
    slskd_downloads = await slskd_client.get_downloads()

    flat_transfers: List[Dict[str, Any]] = []
    if isinstance(slskd_downloads, list):
        flat_transfers = slskd_downloads
    elif isinstance(slskd_downloads, dict):
        if "transfers" in slskd_downloads:
            flat_transfers = slskd_downloads["transfers"]
        elif "directories" in slskd_downloads:
            for d in slskd_downloads["directories"]:
                flat_transfers.extend(d.get("files", []))

    mapped_downloads = []
    for db_dl in db_downloads:
        match = None
        target_basename = os.path.basename(db_dl.filename.replace("\\", "/")).lower()

        for t in flat_transfers:
            t_filename = t.get("filename", "").replace("\\", "/").lower()
            t_username = t.get("username", "").lower().strip()

            if db_dl.source_user.lower().strip() == t_username and \
               (t_filename.endswith(target_basename) or target_basename in t_filename):
                match = t
                break

        progress = 0.0
        speed = "0 KB/s"
        eta = "Unknown"

        if match:
            bytes_transferred = match.get("bytes_transferred", 0) or match.get("bytesTransferred", 0) or 0
            size_bytes = match.get("size", db_dl.size_bytes or 0)

            if size_bytes > 0:
                progress = (bytes_transferred / size_bytes) * 100.0

            percent_complete = match.get("percent_complete") or match.get("percentComplete")
            if percent_complete is not None:
                progress = float(percent_complete)

            avg_speed_bytes = match.get("average_speed") or match.get("averageSpeed") or 0.0
            if avg_speed_bytes > 0:
                if avg_speed_bytes > 1024 * 1024:
                    speed = f"{round(avg_speed_bytes / (1024 * 1024), 1)} MB/s"
                else:
                    speed = f"{round(avg_speed_bytes / 1024, 1)} KB/s"

                bytes_remaining = size_bytes - bytes_transferred
                if bytes_remaining > 0:
                    eta_seconds = int(bytes_remaining / avg_speed_bytes)
                    eta = str(timedelta(seconds=eta_seconds))
            else:
                speed = "Queued / Connecting"
        else:
            speed = "Pending / Polling"

        mapped_downloads.append({
            "id": db_dl.id,
            "artist": db_dl.artist,
            "track": db_dl.track,
            "filename": db_dl.filename,
            "source_user": db_dl.source_user,
            "format": db_dl.format,
            "bitrate": db_dl.bitrate,
            "status": db_dl.status,
            "progress": min(progress, 100.0),
            "speed": speed,
            "eta": eta
        })

    return render_template("downloads_list.html", request, {
        "downloads": mapped_downloads,
        "user": user
    })

@router.post("/downloads/{id}/cancel")
async def post_downloads_cancel(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    dl_entry = db.query(DownloadHistory).filter(DownloadHistory.id == id).first()
    if not dl_entry:
        raise HTTPException(status_code=404, detail="Download not found")

    slskd_client = SlskdClient()
    slskd_downloads = await slskd_client.get_downloads()
    flat_transfers: List[Dict[str, Any]] = []
    if isinstance(slskd_downloads, list):
        flat_transfers = slskd_downloads
    elif isinstance(slskd_downloads, dict):
        if "transfers" in slskd_downloads:
            flat_transfers = slskd_downloads["transfers"]
        elif "directories" in slskd_downloads:
            for d in slskd_downloads["directories"]:
                flat_transfers.extend(d.get("files", []))

    target_basename = os.path.basename(dl_entry.filename.replace("\\", "/")).lower()
    for t in flat_transfers:
        t_filename = t.get("filename", "").replace("\\", "/").lower()
        t_username = t.get("username", "").lower().strip()

        if dl_entry.source_user.lower().strip() == t_username and \
           (t_filename.endswith(target_basename) or target_basename in t_filename):
            t_id = t.get("id")
            if t_id:
                await slskd_client.cancel_download(t_username, t_id)

    dl_entry.status = "failed"
    db.commit()

    # Audit Log
    ip_address = request.client.host if request.client else "unknown"
    log_audit_action(db, "DOWNLOAD_CANCEL", f"User '{user.username}' cancelled download '{dl_entry.artist} - {dl_entry.track}'", ip_address)

    return await get_downloads_list(request, db, user)

# --- Metadata Queue ---

@router.get("/metadata-queue", response_class=HTMLResponse)
async def get_metadata_queue(
    request: Request,
    edit: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # Returns all completed but not imported tracks
    queue = db.query(DownloadHistory).filter(
        DownloadHistory.status.in_(["completed", "tagged"])
    ).order_by(DownloadHistory.downloaded_at.desc()).all()

    edit_item = None
    metadata = {}
    if edit:
        edit_item = db.query(DownloadHistory).filter(DownloadHistory.id == edit).first()
        if edit_item:
            filepath = os.path.join(settings.SINGLES_PATH, edit_item.filename)
            if os.path.exists(filepath):
                metadata = read_tags(filepath)

    return render_template("metadata_queue.html", request, {
        "active_page": "metadata_queue",
        "queue": queue,
        "edit_item": edit_item,
        "metadata": metadata,
        "user": user
    })

@router.post("/metadata-queue/{id}/save")
async def post_metadata_save(
    id: int,
    title: str = Form(...),
    artist: str = Form(...),
    album: str = Form(...),
    album_artist: Optional[str] = Form(None),
    track_number: Optional[str] = Form(None),
    year: Optional[str] = Form(None),
    genre: Optional[str] = Form(None),
    comment: Optional[str] = Form(None),
    cover_art: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    log = db.query(DownloadHistory).filter(DownloadHistory.id == id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Entry not found")

    src_filepath = os.path.join(settings.SINGLES_PATH, log.filename)
    if not os.path.exists(src_filepath):
        raise HTTPException(status_code=400, detail="Downloaded file not found on disk")

    cover_bytes = None
    cover_mime = "image/jpeg"
    if cover_art and cover_art.filename:
        cover_bytes = await cover_art.read()
        cover_mime = cover_art.content_type or "image/jpeg"

    # Write real tags using mutagen tagger
    success = write_tags(
        filepath=src_filepath,
        title=title,
        artist=artist,
        album=album,
        album_artist=album_artist,
        track_number=track_number,
        year=year,
        genre=genre,
        comment=comment,
        cover_image_bytes=cover_bytes,
        cover_mime=cover_mime
    )

    if success:
        log.status = "tagged"
        # Update artist, title, album in history to match tagged metadata
        log.artist = artist
        log.track = title
        log.album = album
        db.commit()
        logger.info(f"Tagged track successfully: '{artist} - {title}'")

    return RedirectResponse(url="/metadata-queue", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/metadata-queue/{id}/import")
async def post_metadata_import(
    id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    log = db.query(DownloadHistory).filter(DownloadHistory.id == id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Entry not found")

    src_filepath = os.path.join(settings.SINGLES_PATH, log.filename)
    if not os.path.exists(src_filepath):
        raise HTTPException(status_code=400, detail="Downloaded file not found on disk")

    # Organize in permanent MUSIC_LIBRARY_PATH under Artist/Album/Filename
    safe_artist = "".join(c for c in log.artist if c.isalnum() or c in "._- ")
    safe_album = "".join(c for c in log.album if c.isalnum() or c in "._- ") or "Single"

    dest_dir = os.path.join(settings.MUSIC_LIBRARY_PATH, safe_artist, safe_album)
    os.makedirs(dest_dir, exist_ok=True)

    dest_filename = f"{log.artist} - {log.track}{os.path.splitext(log.filename)[1]}"
    dest_filename = "".join(c for c in dest_filename if c.isalnum() or c in "._- ")

    dest_filepath = os.path.join(dest_dir, dest_filename)

    try:
        shutil.move(src_filepath, dest_filepath)
        logger.info(f"Imported single track: {src_filepath} -> {dest_filepath}")

        # Update database entry
        log.status = "imported"
        log.filename = dest_filepath
        log.imported_at = datetime.utcnow()

        # Fulfill matching wishlist items
        wishlist_item = db.query(Wishlist).filter(
            Wishlist.artist == log.artist,
            Wishlist.track == log.track,
            Wishlist.status != "imported"
        ).first()
        if wishlist_item:
            wishlist_item.status = "imported"
            wishlist_item.fulfilled_at = datetime.utcnow()

        db.commit()

        # Audit Log
        ip_address = request.client.host if request.client else "unknown"
        log_audit_action(db, "IMPORT_TRACK", f"User '{user.username}' imported '{log.artist} - {log.track}' to library path {dest_filepath}", ip_address)

        # Auto trigger Navidrome scan
        navidrome = NavidromeClient()
        await navidrome.start_scan()

    except Exception as e:
        logger.error(f"Failed to import track to library: {e}")
        raise HTTPException(status_code=500, detail="Failed to import track to library.")

    return RedirectResponse(url="/metadata-queue", status_code=status.HTTP_303_SEE_OTHER)

# --- Wishlist ---

@router.get("/wishlist", response_class=HTMLResponse)
async def get_wishlist(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    wishlist = db.query(Wishlist).order_by(Wishlist.created_at.desc()).all()
    return render_template("wishlist.html", request, {
        "active_page": "wishlist",
        "wishlist": wishlist,
        "user": user
    })

@router.post("/wishlist/create")
async def post_wishlist_create(
    artist: str = Form(...),
    track: str = Form(...),
    album: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    item = Wishlist(
        artist=artist,
        track=track,
        album=album,
        notes=notes,
        status="pending"
    )
    db.add(item)
    db.commit()
    return RedirectResponse(url="/wishlist", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/wishlist/{id}/delete")
async def post_wishlist_delete(id: int, db: Session = Depends(get_db)):
    item = db.query(Wishlist).filter(Wishlist.id == id).first()
    if item:
        db.delete(item)
        db.commit()
    return RedirectResponse(url="/wishlist", status_code=status.HTTP_303_SEE_OTHER)

# --- Favorites ---

@router.get("/favorites", response_class=HTMLResponse)
async def get_favorites(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    favorites = db.query(Favorites).order_by(Favorites.created_at.desc()).all()
    return render_template("favorites.html", request, {
        "active_page": "favorites",
        "favorites": favorites,
        "user": user
    })

@router.post("/favorites/toggle")
async def post_favorites_toggle(
    artist: str = Form(...),
    track: str = Form(...),
    album: Optional[str] = Form(""),
    source: str = Form(...),
    db: Session = Depends(get_db)
):
    existing = db.query(Favorites).filter(
        Favorites.artist == artist,
        Favorites.track == track
    ).first()

    if existing:
        db.delete(existing)
    else:
        fav = Favorites(
            artist=artist,
            track=track,
            album=album or "Unknown",
            source=source
        )
        db.add(fav)
    db.commit()
    return RedirectResponse(url="/favorites", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/favorites/{id}/delete")
async def post_favorites_delete(id: int, db: Session = Depends(get_db)):
    fav = db.query(Favorites).filter(Favorites.id == id).first()
    if fav:
        db.delete(fav)
        db.commit()
    return RedirectResponse(url="/favorites", status_code=status.HTTP_303_SEE_OTHER)

# --- History ---

@router.get("/history", response_class=HTMLResponse)
async def get_history_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    history = db.query(DownloadHistory).order_by(DownloadHistory.downloaded_at.desc()).all()
    return render_template("history.html", request, {
        "active_page": "history",
        "history": history,
        "user": user
    })

# --- Admin Page ---

@router.get("/admin", response_class=HTMLResponse)
async def get_admin_page(
    request: Request,
    success_message: Optional[str] = None,
    error_message: Optional[str] = None,
    user: User = Depends(get_current_user)
):
    return render_template("admin.html", request, {
        "active_page": "admin",
        "success_message": success_message,
        "error_message": error_message,
        "user": user
    })

@router.post("/admin/change-password")
async def post_change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not verify_password(current_password, user.password_hash):
        return render_template("admin.html", request, {
            "active_page": "admin",
            "error_message": "Current password is incorrect.",
            "user": user
        })

    if len(new_password) < 8:
        return render_template("admin.html", request, {
            "active_page": "admin",
            "error_message": "New password must be at least 8 characters long.",
            "user": user
        })

    if new_password != confirm_password:
        return render_template("admin.html", request, {
            "active_page": "admin",
            "error_message": "New passwords do not match.",
            "user": user
        })

    user.password_hash = hash_password(new_password)
    db.commit()

    # Log Audit Action
    ip_address = request.client.host if request.client else "unknown"
    log_audit_action(db, "ADMIN_PASSWORD_CHANGE", f"Administrator password changed successfully by user '{user.username}'", ip_address)

    return render_template("admin.html", request, {
        "active_page": "admin",
        "success_message": "Password changed successfully!",
        "user": user
    })

# --- Navidrome Manual Rescan trigger ---

@router.post("/navidrome/rescan")
async def post_navidrome_rescan(user: User = Depends(get_current_user)):
    navidrome = NavidromeClient()
    success = await navidrome.start_scan()
    if success:
        return HTMLResponse("<span class='text-xs text-emerald-400 font-semibold'><i class='fa-solid fa-circle-check mr-1'></i>Navidrome scan triggered!</span>")
    else:
        return HTMLResponse("<span class='text-xs text-rose-400 font-semibold'><i class='fa-solid fa-triangle-exclamation mr-1'></i>Scan trigger failed</span>")
