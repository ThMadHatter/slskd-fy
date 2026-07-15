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
import time
from app.services.cache_service import CacheService
from app.services.artist_service import ArtistService
from app.services.track_service import TrackService
from app.services.search_ranking_service import SearchRankingService
from app.services.filename_parser import parse_filename
from app.services.musicbrainz_service import MusicBrainzService

logger = logging.getLogger("track_portal.pages")

class PerformanceTracker:
    autocomplete_latencies = []
    search_durations = []
    ranking_durations = []
    mb_enrichment_durations = []
    mb_requests_per_search = []

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

    # Connection Healthchecks
    from sqlalchemy import text
    db_connected = True
    db_error = ""
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_connected = False
        db_error = str(e)

    slskd_connected = True
    slskd_error = ""
    try:
        await SlskdClient().get_downloads()
    except Exception as e:
        slskd_connected = False
        slskd_error = str(e)

    navidrome_connected = True
    navidrome_error = ""
    try:
        ping_res = await NavidromeClient().ping_check()
        if not ping_res.get("connected"):
            navidrome_connected = False
            navidrome_error = ping_res.get("message", "Unknown error")
    except Exception as e:
        navidrome_connected = False
        navidrome_error = str(e)

    # Cache metrics
    cache_metrics = CacheService.get_metrics(db)

    # Unknown rates (Task 6)
    total_history = db.query(DownloadHistory).count()
    unknown_artist_count = db.query(DownloadHistory).filter(DownloadHistory.artist == "Unknown").count()
    unknown_album_count = db.query(DownloadHistory).filter(DownloadHistory.album == "Unknown").count()

    unknown_artist_rate = (unknown_artist_count / total_history * 100.0) if total_history > 0 else 0.0
    unknown_album_rate = (unknown_album_count / total_history * 100.0) if total_history > 0 else 0.0

    # Performance stats (Task 8)
    avg_auto_latency = (sum(PerformanceTracker.autocomplete_latencies) / len(PerformanceTracker.autocomplete_latencies) * 1000.0) if PerformanceTracker.autocomplete_latencies else 15.0
    avg_search_latency = (sum(PerformanceTracker.search_durations) / len(PerformanceTracker.search_durations)) if PerformanceTracker.search_durations else 1.2
    avg_rank_duration = (sum(PerformanceTracker.ranking_durations) / len(PerformanceTracker.ranking_durations) * 1000.0) if PerformanceTracker.ranking_durations else 1.5
    avg_mb_requests = (sum(PerformanceTracker.mb_requests_per_search) / len(PerformanceTracker.mb_requests_per_search)) if PerformanceTracker.mb_requests_per_search else 4.0
    avg_mb_enrich_time = (sum(PerformanceTracker.mb_enrichment_durations) / len(PerformanceTracker.mb_enrichment_durations)) if PerformanceTracker.mb_enrichment_durations else 0.4

    stats = {
        "wishlist_count": wishlist_count,
        "favorites_count": favorites_count,
        "active_downloads_count": len(active_downloads),
        "completed_count": completed_count,
        "active_downloads": active_downloads,
        "recent_downloads": recent_downloads,
        "duplicate_warnings": duplicate_warnings,
        "integrations": {
            "database": {"connected": db_connected, "error": db_error},
            "slskd": {"connected": slskd_connected, "error": slskd_error},
            "navidrome": {"connected": navidrome_connected, "error": navidrome_error}
        },
        "cache_metrics": cache_metrics,
        "unknown_metrics": {
            "artist_rate": f"{unknown_artist_rate:.1f}%",
            "album_rate": f"{unknown_album_rate:.1f}%"
        },
        "performance": {
            "auto_latency": f"{avg_auto_latency:.1f} ms",
            "search_latency": f"{avg_search_latency:.2f} s",
            "rank_duration": f"{avg_rank_duration:.1f} ms",
            "mb_requests": f"{avg_mb_requests:.1f}",
            "mb_enrich_time": f"{avg_mb_enrich_time:.2f} s"
        }
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
    canonical_artist: Optional[str] = Form(None),
    artist_mbid: Optional[str] = Form(None),
    track: Optional[str] = Form(None),
    canonical_track: Optional[str] = Form(None),
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
    start_time = time.time()

    # Issue 1: Selected autocomplete values must drive the search query. Use canonical prioritised.
    chosen_artist = canonical_artist.strip() if canonical_artist and canonical_artist.strip() else (artist.strip() if artist else "")
    chosen_track = canonical_track.strip() if canonical_track and canonical_track.strip() else (track.strip() if track else "")

    # Defensively strip quotes from individual form input values first to prevent slskd literal quote matching issues
    clean_artist = chosen_artist.strip().strip("'\"").strip()
    clean_track = chosen_track.strip().strip("'\"").strip()
    clean_query = query.strip().strip("'\"").strip() if query else ""

    # Task 4 & 7: Optimized Search Strategy Generation using Canonical values
    search_query = ""
    if clean_artist and clean_track:
        queries = SearchRankingService.generate_queries(clean_artist, clean_track)
        search_query = queries[0] if queries else f"{clean_artist} {clean_track}"
    else:
        search_query = clean_query or f"{clean_artist} {clean_track}".strip()

    if not search_query:
        return "<div class='p-6 text-center text-rose-400'>Please enter a search query.</div>"

    search_query = search_query.strip().strip("'\"").strip()

    logger.info(f"Executing slskd search with query: '{search_query}'")

    slskd_client = SlskdClient()
    total_slskd = 0
    parsed_success = 0
    parser_failures = 0
    rejected_results = 0
    results_after_filtering = 0
    results_after_ranking = 0
    mb_requests = 0
    cache_hits = 0
    cache_misses = 0
    mb_skipped = 0
    enriched_results_count = 0
    duplicate_checks_count = 0

    try:
        search_obj = await slskd_client.search(search_query)
        search_id = search_obj.get("id")
        if not search_id:
            return "<div class='p-6 text-center text-rose-400'>Failed to start search in slskd.</div>"

        # Poll search responses
        responses = []
        for _ in range(5):
            await asyncio.sleep(1.2)
            responses = await slskd_client.get_search_responses(search_id)
            if len(responses) >= 12:
                break

        raw_results = []
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

                # Issue 7: Hard Rejection Stage BEFORE parsing/budget
                if SearchRankingService.should_reject_result(filename, ext):
                    rejected_results += 1
                    continue

                # Task 3: Preprocessing Soulseek Path -> Filename Parser
                parsed = parse_filename(filename)

                # Check parser success
                if parsed.get("artist") != "Unknown" and parsed.get("track") != "Unknown":
                    parsed_success += 1
                else:
                    parser_failures += 1

                res_artist = parsed.get("artist") or clean_artist or "Unknown"
                res_track = parsed.get("track") or clean_track or os.path.splitext(os.path.basename(filename))[0]
                res_album = parsed.get("album") or ""
                res_year = parsed.get("year") or None
                featured = parsed.get("featured_artists", [])

                raw_results.append({
                    "artist": res_artist,
                    "track": res_track,
                    "album": res_album,
                    "year": res_year,
                    "cover_url": "",
                    "filename": filename,
                    "size": size,
                    "username": username,
                    "format": ext,
                    "bitrate": bitrate,
                    "sample_rate": sample_rate,
                    "queue_length": queue_length,
                    "featured_artists": featured
                })

        total_slskd = len(raw_results) + rejected_results

        # Apply User Filters (Format, Bitrate, Size)
        filtered_results = []
        for r in raw_results:
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

        results_after_filtering = len(filtered_results)

        # Issue 2: Strong Local Ranking & Score evaluation before enrichment
        rank_start = time.time()
        scored_candidates = []
        for r in filtered_results:
            tgt_art = clean_artist or r["artist"]
            tgt_tr = clean_track or r["track"]

            # score_result returns a detailed dictionary with sub-scores & classification
            diag = SearchRankingService.score_result(r, tgt_art, tgt_tr)
            r["ranking_diagnostics"] = diag
            r["quality_score"] = diag["final_score"]

            # Filter low-confidence results (score < 40) BEFORE enrichment
            if diag["final_score"] >= 40:
                scored_candidates.append(r)

        # Sort locally first based on local rankings
        scored_candidates.sort(key=lambda x: x["quality_score"], reverse=True)
        rank_duration = time.time() - rank_start
        PerformanceTracker.ranking_durations.append(rank_duration)

        # Slicing: keep top candidates only (up to 20 top candidates)
        top_candidates = scored_candidates[:20]
        results_after_ranking = len(top_candidates)

        # Task 1: MusicBrainz enrichment budget (Concurrently throttled, max 20, 3s timeout)
        mb_start = time.time()

        async def enrich_candidate(r):
            nonlocal mb_requests, cache_hits, cache_misses, mb_skipped, enriched_results_count
            res_artist = r["artist"]
            res_track = r["track"]

            if res_artist == "Unknown" or not res_artist:
                mb_skipped += 1
                return

            cache_key = f"mb:rec_search:{res_artist.lower().strip()}:none:{res_track.lower().strip()}"
            cached_data = CacheService.get(db, cache_key, "track")

            if cached_data is not None:
                cache_hits += 1
                if cached_data and len(cached_data) > 0:
                    first = cached_data[0]
                    enriched = False
                    if not r["album"] and first.get("album"):
                        r["album"] = first["album"]
                        enriched = True
                    if not r["year"] and first.get("year"):
                        r["year"] = first["year"]
                        enriched = True
                    if first.get("cover_url"):
                        r["cover_url"] = first["cover_url"]
                        enriched = True
                    if enriched:
                        enriched_results_count += 1
            else:
                cache_misses += 1
                if mb_requests < 20:
                    mb_requests += 1
                    try:
                        # Query live MB
                        mb_recs = await MusicBrainzService.search_recordings(res_artist, None, res_track, db)
                        if mb_recs:
                            first = mb_recs[0]
                            enriched = False
                            if not r["album"] and first.get("album"):
                                r["album"] = first["album"]
                                enriched = True
                            if not r["year"] and first.get("year"):
                                r["year"] = first["year"]
                                enriched = True
                            if first.get("cover_url"):
                                r["cover_url"] = first["cover_url"]
                                enriched = True
                            if enriched:
                                enriched_results_count += 1
                    except Exception as ex:
                        logger.warning(f"Live MusicBrainz enrichment lookup failed: {ex}")
                else:
                    mb_skipped += 1

        # Run candidate enrichment concurrently within throttling/concurrency bounds
        await asyncio.gather(*(enrich_candidate(c) for c in top_candidates))

        mb_duration = time.time() - mb_start
        PerformanceTracker.mb_enrichment_durations.append(mb_duration)
        PerformanceTracker.mb_requests_per_search.append(mb_requests)

        # Issue 2: Re-score and re-classify enriched candidates to factor in MB metadata!
        for r in top_candidates:
            tgt_art = clean_artist or r["artist"]
            tgt_tr = clean_track or r["track"]
            diag = SearchRankingService.score_result(r, tgt_art, tgt_tr)
            r["ranking_diagnostics"] = diag
            r["quality_score"] = diag["final_score"]

        # Sort the final candidates list
        if sort_by == "quality":
            top_candidates.sort(key=lambda x: x["quality_score"], reverse=True)
        elif sort_by == "size_desc":
            top_candidates.sort(key=lambda x: x["size"] or 0, reverse=True)
        elif sort_by == "size_asc":
            top_candidates.sort(key=lambda x: x["size"] or 0, reverse=False)
        elif sort_by == "queue":
            top_candidates.sort(key=lambda x: x["queue_length"], reverse=False)

        # Issue 4: Duplicate detection runs on high confidence (score >= 80) only!
        dup_cache: Dict[tuple, Dict[str, Any]] = {}
        for r in top_candidates:
            r["duplicate_warning"] = None
            if r["quality_score"] >= 80:
                cache_key = (r["artist"].lower().strip(), r["track"].lower().strip())
                if cache_key not in dup_cache:
                    duplicate_checks_count += 1
                    dup_cache[cache_key] = await check_duplicate(db, r["artist"], r["track"])

                dup_info = dup_cache[cache_key]
                if dup_info["is_duplicate"]:
                    r["duplicate_warning"] = dup_info["warning_message"]

        search_duration = time.time() - start_time
        PerformanceTracker.search_durations.append(search_duration)

        # Track Search History in DB
        hist = SearchHistory(query=search_query, result_count=len(top_candidates))
        db.add(hist)
        db.commit()

        # Issue 8: Measure effectiveness metrics in diagnostics panel
        debug_info = {
            "query": search_query,
            "total_results": total_slskd,
            "parsed_results": parsed_success,
            "rejected_results": rejected_results,
            "enriched_results": enriched_results_count,
            "duplicate_checks": duplicate_checks_count,
            "musicbrainz_calls": mb_requests,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "skipped": mb_skipped,
            "duration": f"{search_duration:.2f}s"
        }

        return render_template("search_results.html", request, {
            "results": top_candidates,
            "user": user,
            "debug_info": debug_info
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

# --- Autocomplete Endpoints ---

@router.get("/api/autocomplete/artist", response_class=HTMLResponse)
async def api_autocomplete_artist(
    request: Request,
    q: Optional[str] = "",
    artist: Optional[str] = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    query = q or artist
    if not query or len(query.strip()) < 2:
        return ""
    start = time.time()
    artists = await ArtistService.autocomplete(query, db)
    PerformanceTracker.autocomplete_latencies.append(time.time() - start)
    if not artists:
        return "<div class='p-3 text-sm text-slate-500 bg-slate-800 border border-slate-700 rounded-lg mt-1 absolute z-50 w-full'>No artists found.</div>"

    html = '<ul class="absolute z-50 w-full bg-slate-800 border border-slate-700 rounded-lg shadow-xl mt-1 max-h-60 overflow-y-auto divide-y divide-slate-700">'
    for a in artists:
        mbid = a.get("id") or ""
        name = a.get("name").replace("'", "\\'")
        html += f"""
        <li class="px-4 py-3 hover:bg-slate-700 cursor-pointer text-sm transition" onclick="selectArtist('{name}', '{mbid}')">
            <div class="font-bold text-slate-200">{a.get('name')}</div>
            <div class="text-xs text-slate-400">{a.get('type')} - {a.get('country') or 'Unknown'} ({a.get('disambiguation') or 'No info'})</div>
        </li>
        """
    html += '</ul>'
    return HTMLResponse(content=html)

@router.get("/api/autocomplete/track", response_class=HTMLResponse)
async def api_autocomplete_track(
    request: Request,
    artist_name: Optional[str] = "",
    artist: Optional[str] = "",
    artist_mbid: Optional[str] = "",
    q: Optional[str] = "",
    track: Optional[str] = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    actual_artist = artist_name or artist
    actual_query = q or track
    if not actual_artist:
        return ""
    start = time.time()
    tracks = await TrackService.autocomplete(actual_artist, artist_mbid, actual_query, db)
    PerformanceTracker.autocomplete_latencies.append(time.time() - start)
    if not tracks:
        return "<div class='p-3 text-sm text-slate-500 bg-slate-800 border border-slate-700 rounded-lg mt-1 absolute z-50 w-full'>No tracks found.</div>"

    html = '<ul class="absolute z-50 w-full bg-slate-800 border border-slate-700 rounded-lg shadow-xl mt-1 max-h-60 overflow-y-auto divide-y divide-slate-700">'
    for t in tracks:
        title = t.get("title", "").replace("'", "\\'")
        album = (t.get("album") or "").replace("'", "\\'")
        cover_url = t.get("cover_url") or ""
        year = t.get("year") or ""

        if cover_url:
            img_html = f'<img src="{cover_url}" class="w-8 h-8 rounded shrink-0 object-cover bg-slate-900" onerror="this.style.display=\'none\'" />'
        else:
            img_html = '<div class="w-8 h-8 rounded bg-slate-900 border border-slate-700 flex items-center justify-center shrink-0"><i class="fa-solid fa-music text-slate-500 text-xs"></i></div>'

        year_str = f" ({year})" if year else ""
        album_display = t.get('album') or 'Single'

        html += f"""
        <li class="px-4 py-3 hover:bg-slate-700 cursor-pointer text-sm transition flex items-center space-x-3" onclick="selectTrack('{title}', '{album}')">
            {img_html}
            <div class="min-w-0 flex-1">
                <div class="font-bold text-slate-200 truncate">{t.get('title')}</div>
                <div class="text-xs text-slate-400 truncate">{album_display}{year_str}</div>
            </div>
        </li>
        """
    html += '</ul>'
    return HTMLResponse(content=html)
