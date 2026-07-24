import logging
import asyncio
import httpx
import re
import time
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.services.cache_service import CacheService

logger = logging.getLogger("track_portal.musicbrainz")

# Compliant User-Agent as requested by MusicBrainz [RSL-001]
HEADERS = {
    "User-Agent": "VibeSearch/1.0 ( contact@example.com )",
    "Accept": "application/json"
}

# Semaphore for maximum concurrent MusicBrainz requests: 3
CONCURRENCY_LIMIT = 3
SEMAPHORE = asyncio.Semaphore(CONCURRENCY_LIMIT)

# Strict 1 request per second rate-limiter [RSL-001]
LAST_REQUEST_TIME = 0.0
RATE_LIMIT_LOCK = asyncio.Lock()

def clean_album_name(album: str) -> str:
    """
    Cleans raw album/folder candidates to remove common noise terms before MusicBrainz queries.
    -CD1, -CD2, -Disc 1, -Disc 2, [FLAC], [MP3], Single, EP, Deluxe, WEB, Remastered, Explicit, Clean
    """
    if not album:
        return ""

    cleaned = album

    # 1. Strip bracketed extension tags
    cleaned = re.sub(r"\[(FLAC|MP3|WEB-FLAC|WEB-MP3|WEB)\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\((CD\d+|Disc\s*\d+|Disk\s*\d+|Deluxe|Remastered|Explicit|Clean|EP|Single)\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(CD\d+|Disc\s*\d+|Disk\s*\d+|Deluxe|Remastered|Explicit|Clean|EP|Single)\b", "", cleaned, flags=re.IGNORECASE)

    # 2. Strip prefixes and suffixes
    cleaned = re.sub(r"\b\d{4}\s*-\s*", "", cleaned)
    cleaned = re.sub(r"\s*-\s*\d{4}\b", "", cleaned)
    cleaned = re.sub(r"\b(Single|EP)\s*-\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*-\s*(Single|EP)\b", "", cleaned, flags=re.IGNORECASE)

    # Strip spaces and redundant dashes
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.strip("-").strip()

    # Reject unresolved generic candidates
    if not cleaned or cleaned.isdigit() or len(cleaned) < 2:
        return ""

    return cleaned

class MusicBrainzService:
    """
    [CDA-001] Service layer handling MusicBrainz metadata resolution with robust circuit breaker
    and strict rate limit compliance.
    """
    # Circuit Breaker state parameters as class variables to prevent import/scoping conflicts [DAT-002]
    CIRCUIT_OPEN = False
    FAILURE_COUNT = 0
    MAX_FAILURES = 3
    LAST_FAILURE_TIME = 0.0
    RESET_TIMEOUT_SEC = 60.0  # Attempt reset after 1 minute

    @classmethod
    async def _make_request(cls, url: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        [RSL-001] Rate-limiting and throttled request dispatcher.
        Enforces 1 request/second, concurrency limit of 3, strict 3-second timeouts,
        and manages the Circuit Breaker [DAT-002] for graceful degradation.
        """
        global LAST_REQUEST_TIME

        # Check Circuit Breaker status [DAT-002]
        now = time.time()
        if cls.CIRCUIT_OPEN:
            if now - cls.LAST_FAILURE_TIME > cls.RESET_TIMEOUT_SEC:
                logger.warning("MusicBrainz Circuit Breaker: Reset timeout elapsed. Attempting half-open retry...")
                cls.CIRCUIT_OPEN = False
                cls.FAILURE_COUNT = 0
            else:
                logger.error("MusicBrainz Circuit Breaker is OPEN. Bypassing outbound call to prevent blocking UI.")
                return None

        async with RATE_LIMIT_LOCK:
            delta = time.time() - LAST_REQUEST_TIME
            if delta < 1.0:
                await asyncio.sleep(1.0 - delta)
            LAST_REQUEST_TIME = time.time()

        async with SEMAPHORE:
            async with httpx.AsyncClient(headers=HEADERS, timeout=3.0) as client:
                for attempt in range(2):
                    try:
                        response = await client.get(url, params=params)
                        if response.status_code == 200:
                            # Reset failure counter upon success
                            cls.FAILURE_COUNT = 0
                            return response.json()
                        elif response.status_code == 503:
                            logger.warning(f"MusicBrainz API rate limit (503). Retrying in 1s (attempt {attempt+1})...")
                            await asyncio.sleep(1.0)
                        else:
                            logger.error(f"MusicBrainz request failed with status {response.status_code}: {response.text[:150]}")
                            cls._register_failure()
                            return None
                    except (httpx.TimeoutException, asyncio.TimeoutError):
                        logger.warning(f"MusicBrainz API request timed out (3s threshold) for: {url}")
                        cls._register_failure()
                        return None
                    except Exception as e:
                        logger.error(f"Exception during MusicBrainz request: {e}")
                        cls._register_failure()
                        await asyncio.sleep(0.5)
                return None

    @classmethod
    def _register_failure(cls):
        """
        Registers request failures and trips the Circuit Breaker [DAT-002] if thresholds are crossed.
        """
        cls.FAILURE_COUNT += 1
        cls.LAST_FAILURE_TIME = time.time()
        logger.warning(f"MusicBrainz API Failure recorded. Consecutive count: {cls.FAILURE_COUNT}/{cls.MAX_FAILURES}")
        if cls.FAILURE_COUNT >= cls.MAX_FAILURES:
            logger.error("MusicBrainz Circuit Breaker TRIP -> OPEN state! Gracefully degrading UI to manual search.")
            cls.CIRCUIT_OPEN = True

    @classmethod
    async def search_artists(cls, query: str, db: Session) -> List[Dict[str, Any]]:
        """
        Searches MusicBrainz for artists with prefix-wildcard support. Result is cached.
        Fallback [DAT-002]: Serves stale cache data first if circuit is open.
        """
        clean_q = query.strip()
        cache_key = f"mb:artist_search:{clean_q.lower()}"
        cached = CacheService.get(db, cache_key, "artist")
        if cached is not None:
            logger.info(f"MusicBrainz artist search cache hit for '{clean_q}'")
            return cached

        logger.info(f"MusicBrainz artist search cache miss for '{clean_q}'. Querying MusicBrainz with prefix wildcard...")
        url = "https://musicbrainz.org/ws/2/artist/"

        lucene_query = f"artist:({clean_q}*)"
        params = {
            "query": lucene_query,
            "fmt": "json",
            "limit": 10
        }

        data = await cls._make_request(url, params)
        results = []
        if data and "artists" in data:
            for artist in data["artists"]:
                results.append({
                    "id": artist.get("id"),
                    "name": artist.get("name"),
                    "type": artist.get("type", "Unknown"),
                    "country": artist.get("country", "Unknown"),
                    "disambiguation": artist.get("disambiguation", "")
                })

        # Cache results for 1 day
        CacheService.set(db, cache_key, results, "artist", ttl_seconds=86400)
        return results

    @classmethod
    async def search_recordings(cls, artist_name: str, artist_mbid: Optional[str], query: str, db: Session) -> List[Dict[str, Any]]:
        """
        Searches MusicBrainz for recordings.
        Fallback [DAT-002]: Serves stale cache data first if circuit is open.
        """
        clean_artist = artist_name.lower().strip()
        clean_query = query.lower().strip()
        cache_key = f"mb:rec_search:{clean_artist}:{artist_mbid or 'none'}:{clean_query}"

        cached = CacheService.get(db, cache_key, "track")
        if cached is not None:
            logger.info(f"MusicBrainz recordings cache hit for '{artist_name} - {query}'")
            return cached

        logger.info(f"MusicBrainz recordings cache miss for '{artist_name} - {query}'. Querying MusicBrainz...")

        if artist_mbid:
            lucene_query = f"arid:{artist_mbid} AND recording:{query}"
        else:
            lucene_query = f"artist:\"{artist_name}\" AND recording:\"{query}\""

        url = "https://musicbrainz.org/ws/2/recording/"
        params = {
            "query": lucene_query,
            "fmt": "json",
            "limit": 15
        }

        data = await cls._make_request(url, params)
        results = []
        if data and "recordings" in data:
            for rec in data["recordings"]:
                album_name = ""
                release_id = ""
                year = None

                releases = rec.get("releases", [])
                if releases:
                    first_release = releases[0]
                    album_name = first_release.get("title", "")
                    release_id = first_release.get("id", "")
                    release_date = first_release.get("date", "")
                    if release_date:
                        match = re.search(r"\b(19|20)\d{2}\b", release_date)
                        if match:
                            year = int(match.group(0))

                cover_url = f"https://coverartarchive.org/release/{release_id}/front-250" if release_id else ""

                results.append({
                    "id": rec.get("id"),
                    "title": rec.get("title"),
                    "artist": artist_name,
                    "album": album_name,
                    "year": year,
                    "cover_url": cover_url,
                    "release_id": release_id
                })

        # Cache results for 1 day
        CacheService.set(db, cache_key, results, "track", ttl_seconds=86400)
        return results

    @classmethod
    async def match_release(cls, artist_name: str, album_name: str, db: Session) -> Optional[Dict[str, Any]]:
        """
        Attempts to match a cleaned album candidate and artist against MusicBrainz releases.
        Computes a confidence score out of 100.
        """
        cleaned_album = clean_album_name(album_name)
        if not cleaned_album:
            return None

        clean_artist = artist_name.lower().strip()
        clean_album_q = cleaned_album.lower().strip()
        cache_key = f"mb:release_match:{clean_artist}:{clean_album_q}"

        cached = CacheService.get(db, cache_key, "track")
        if cached is not None:
            return cached

        logger.info(f"MusicBrainz release match miss for '{artist_name} - {cleaned_album}'. Querying MusicBrainz...")

        lucene_query = f"artist:\"{artist_name}\" AND release:\"{cleaned_album}\""
        url = "https://musicbrainz.org/ws/2/release/"
        params = {
            "query": lucene_query,
            "fmt": "json",
            "limit": 5
        }

        data = await cls._make_request(url, params)
        if data and "releases" in data and data["releases"]:
            best_match = None
            highest_score = 0

            for r in data["releases"]:
                title = r.get("title", "")
                mbid = r.get("id", "")
                date = r.get("date", "")

                score = 0
                if title.lower().strip() == cleaned_album.lower().strip():
                    score += 50
                elif cleaned_album.lower().strip() in title.lower().strip():
                    score += 35

                artist_credits = r.get("artist-credit", [])
                for ac in artist_credits:
                    if artist_name.lower().strip() == ac.get("artist", {}).get("name", "").lower().strip():
                        score += 40
                        break

                if score > highest_score:
                    highest_score = score
                    year = None
                    if date:
                        match = re.search(r"\b(19|20)\d{2}\b", date)
                        if match:
                            year = int(match.group(0))

                    best_match = {
                        "release_name": title,
                        "release_year": year,
                        "release_mbid": mbid,
                        "confidence_score": min(score + 10, 100)
                    }

            if best_match and best_match["confidence_score"] >= 65:
                CacheService.set(db, cache_key, best_match, "track", ttl_seconds=86400)
                return best_match

        return None
