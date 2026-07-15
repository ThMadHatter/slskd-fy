import logging
import asyncio
import httpx
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.services.cache_service import CacheService

logger = logging.getLogger("track_portal.musicbrainz")

# Use a custom, descriptive User-Agent as requested by MusicBrainz
HEADERS = {
    "User-Agent": "TrackPortal/1.0.0 ( contact@trackportal.internal )",
    "Accept": "application/json"
}

# Task 1: Maximum concurrent MusicBrainz requests: 3
CONCURRENCY_LIMIT = 3
SEMAPHORE = asyncio.Semaphore(CONCURRENCY_LIMIT)

class MusicBrainzService:
    @staticmethod
    async def _make_request(url: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Helper method to make rate-limited and throttled requests to MusicBrainz.
        Restricts concurrency to 3 and enforces a strict 3-second timeout.
        """
        async with SEMAPHORE:
            # Enforce strict 3-second timeout per request
            async with httpx.AsyncClient(headers=HEADERS, timeout=3.0) as client:
                for attempt in range(2):
                    try:
                        response = await client.get(url, params=params)
                        if response.status_code == 200:
                            return response.json()
                        elif response.status_code == 503:
                            logger.warning(f"MusicBrainz API rate limit (503). Retrying in 1s (attempt {attempt+1})...")
                            await asyncio.sleep(1.0)
                        else:
                            logger.error(f"MusicBrainz request failed with status {response.status_code}: {response.text[:150]}")
                            return None
                    except (httpx.TimeoutException, asyncio.TimeoutError):
                        logger.warning(f"MusicBrainz API request timed out (3s threshold) for: {url}")
                        return None
                    except Exception as e:
                        logger.error(f"Exception during MusicBrainz request: {e}")
                        await asyncio.sleep(0.5)
                return None

    @classmethod
    async def search_artists(cls, query: str, db: Session) -> List[Dict[str, Any]]:
        """
        Searches MusicBrainz for artists. Result is cached.
        """
        cache_key = f"mb:artist_search:{query.lower().strip()}"
        cached = CacheService.get(db, cache_key, "artist")
        if cached is not None:
            logger.info(f"MusicBrainz artist search cache hit for '{query}'")
            return cached

        logger.info(f"MusicBrainz artist search cache miss for '{query}'. Querying MusicBrainz...")
        url = "https://musicbrainz.org/ws/2/artist/"
        params = {
            "query": f"artist:{query}",
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
        Searches MusicBrainz for recordings (tracks) under a specific artist.
        """
        clean_artist = artist_name.lower().strip()
        clean_query = query.lower().strip()
        cache_key = f"mb:rec_search:{clean_artist}:{artist_mbid or 'none'}:{clean_query}"

        cached = CacheService.get(db, cache_key, "track")
        if cached is not None:
            logger.info(f"MusicBrainz recordings cache hit for '{artist_name} - {query}'")
            return cached

        logger.info(f"MusicBrainz recordings cache miss for '{artist_name} - {query}'. Querying MusicBrainz...")

        # Construct search query
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
                # Extract first release if available
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

                # Build cover art URL if release_id exists
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
