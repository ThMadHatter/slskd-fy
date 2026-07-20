import os
import sys
import asyncio
import logging
import json
from datetime import datetime

# Configure verbose logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("track_portal.audit")

from app.config import settings
from app.database import SessionLocal
from app.services.artist_service import ArtistService
from app.services.track_service import TrackService
from app.services.search_ranking_service import SearchRankingService
from app.services.slskd import SlskdClient
from app.services.cache_service import CacheService
from app.models import CacheEntry, CacheMetric

async def run_audit():
    logger.info("=============================================================")
    logger.info("STARTING END-TO-END AUDIT OF TRACK PORTAL WORKFLOWS")
    logger.info("=============================================================")

    db = SessionLocal()

    # Check slskd settings
    logger.info(f"Using slskd API URL: {settings.SLSKD_API_URL}")
    logger.info(f"Using slskd API Key: {settings.SLSKD_API_KEY[:4]}...{settings.SLSKD_API_KEY[-4:] if len(settings.SLSKD_API_KEY) > 8 else ''}")

    # 1. ARTIST AUTOCOMPLETE AUDIT
    logger.info("\n--- STEP 1: ARTIST AUTOCOMPLETE ---")
    artist_query = "Daft Punk"
    logger.info(f"Request Sent: ArtistService.autocomplete with query='{artist_query}'")

    # Record cache status before request
    mb_cache_key = f"mb:artist_search:{artist_query.lower()}"
    cached_artist = CacheService.get(db, mb_cache_key, "artist")
    logger.info(f"Cache lookup for key '{mb_cache_key}': {'HIT' if cached_artist is not None else 'MISS'}")

    start_time = datetime.utcnow()
    artists = await ArtistService.autocomplete(artist_query, db)
    duration = (datetime.utcnow() - start_time).total_seconds()

    logger.info(f"Response Received: Found {len(artists)} artists in {duration:.3f}s")
    logger.info("Records Before Scoring/Filtering (from MusicBrainz or Cache):")
    # MusicBrainz search_artists returns up to 10 artists. Let's show them:
    for idx, a in enumerate(artists):
        logger.info(f"  [{idx+1}] ID: {a.get('id')} | Name: '{a.get('name')}' | Score: {a.get('score')} | Type: {a.get('type')}")

    logger.info("Records After Scoring/Filtering (Threshold score >= 40):")
    filtered_artists = [a for a in artists if a.get("score", 0) >= 40]
    for idx, a in enumerate(filtered_artists):
        logger.info(f"  [{idx+1}] Name: '{a.get('name')}' | Score: {a.get('score')} | Match Type: {a.get('match_type')}")

    # 2. SEARCH REQUEST GENERATION AUDIT
    logger.info("\n--- STEP 2: SEARCH REQUEST GENERATION ---")
    target_artist = "Daft Punk"
    target_track = "Get Lucky"
    logger.info(f"Request Sent: Generate queries for Artist='{target_artist}', Track='{target_track}'")

    for mode in ["A", "B", "C"]:
        queries = SearchRankingService.generate_queries(target_artist, target_track, mode=mode)
        logger.info(f"  - Mode {mode}: {queries}")

    # 3. SLSKD API CALLS & 4. RESULTS RETRIEVAL / PARSING
    logger.info("\n--- STEPS 3 & 4: SLSKD API CALLS & SEARCH RESULT PARSING ---")
    slskd_client = SlskdClient()
    search_query = "Daft Punk Get Lucky"
    logger.info(f"Request Sent: POST /api/v0/searches with searchText='{search_query}'")

    try:
        search_obj = await slskd_client.search(search_query)
        search_id = search_obj.get("id")
        logger.info(f"Response Received: Search started successfully. Search ID: '{search_id}'")

        # Poll and fetch responses
        logger.info("Polling slskd search responses (waiting 5 seconds)...")
        await asyncio.sleep(5)

        logger.info(f"Request Sent: GET /api/v0/searches/{search_id}/responses")
        responses = await slskd_client.get_search_responses(search_id)
        logger.info(f"Response Received: Found {len(responses)} peer responses.")

        # 5. RESULT FILTERING & SCORING AUDIT
        logger.info("\n--- STEP 5: RESULT FILTERING & SCORING ---")
        raw_files_count = 0
        parsed_results = []
        rejected_count = 0

        for resp in responses:
            username = resp.get("username", "")
            files = resp.get("files", [])
            for f in files:
                raw_files_count += 1
                filename = f.get("filename", "")
                ext = os.path.splitext(filename)[1].lstrip(".").lower()
                size = f.get("size", 0)
                bitrate = f.get("bitRate", 0)
                sample_rate = f.get("sampleRate", 0)
                queue_length = resp.get("queueLength", 0)

                # Check rejection rules (junk files, samples, non-audio extensions)
                if SearchRankingService.should_reject_result(filename, ext):
                    rejected_count += 1
                    continue

                # Parse
                from app.services.filename_parser import parse_filename
                parsed = parse_filename(filename)

                res_artist = parsed.get("artist") or "Unknown"
                res_track = parsed.get("track") or "Unknown"
                res_album = parsed.get("album") or ""
                res_year = parsed.get("year") or None

                parsed_results.append({
                    "artist": res_artist,
                    "track": res_track,
                    "album": res_album,
                    "year": res_year,
                    "filename": filename,
                    "size": size,
                    "username": username,
                    "format": ext,
                    "bitrate": bitrate,
                    "sample_rate": sample_rate,
                    "queue_length": queue_length
                })

        logger.info(f"Total raw files evaluated: {raw_files_count}")
        logger.info(f"Files rejected before parsing (non-audio, junk, samples): {rejected_count}")
        logger.info(f"Files successfully parsed: {len(parsed_results)}")

        # Score and rank candidates
        scored_candidates = []
        for r in parsed_results:
            diag = SearchRankingService.score_result(r, target_artist, target_track)
            r["ranking_diagnostics"] = diag
            r["quality_score"] = diag["final_score"]
            if diag["final_score"] >= 40: # Score threshold
                scored_candidates.append(r)

        logger.info(f"Records After Filtering (Score >= 40): {len(scored_candidates)}")
        scored_candidates.sort(key=lambda x: x["quality_score"], reverse=True)

        # Display top 10 results
        for idx, r in enumerate(scored_candidates[:10]):
            diag = r["ranking_diagnostics"]
            logger.info(f"  [{idx+1}] User: '{r['username']}' | Filename: '{os.path.basename(r['filename'])}'")
            logger.info(f"      Artist: '{r['artist']}' | Track: '{r['track']}' | Format: {r['format']} | Bitrate: {r['bitrate']}")
            logger.info(f"      Score Breakdown: Total={r['quality_score']} | Artist={diag['artist_score']} | Track={diag['track_score']} | Quality={diag['quality_score']} | Classification: {diag['classification']}")

    except Exception as e:
        logger.error(f"Failed to execute slskd search/polling during audit: {e}")

    # 6. CACHE LAYER AUDIT
    logger.info("\n--- STEP 6: CACHE LAYER STATUS ---")
    metrics = CacheService.get_metrics(db)
    logger.info(f"Cache Metrics: {json.dumps(metrics, indent=2)}")

    total_entries = db.query(CacheEntry).count()
    logger.info(f"Total entries in cache_entries table: {total_entries}")

    logger.info("\n=============================================================")
    logger.info("AUDIT RUN COMPLETED")
    logger.info("=============================================================")

    db.close()

if __name__ == "__main__":
    asyncio.run(run_audit())
