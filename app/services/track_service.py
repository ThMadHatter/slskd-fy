import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.services.musicbrainz_service import MusicBrainzService
from app.services.navidrome import NavidromeClient
from app.models import DownloadHistory, CacheEntry

logger = logging.getLogger("track_portal.track_service")

class TrackService:
    @staticmethod
    async def autocomplete(
        artist_name: str,
        artist_mbid: Optional[str],
        query: str,
        db: Session
    ) -> List[Dict[str, Any]]:
        """
        Autocomplete track/song suggestions.
        Priority:
        1. MusicBrainz recordings
        2. Local library (Navidrome)
        3. Local cache/database
        """
        if not artist_name:
            return []

        clean_query = query.strip() if query else ""

        # 1. Try MusicBrainz recordings
        try:
            mb_results = await MusicBrainzService.search_recordings(
                artist_name=artist_name,
                artist_mbid=artist_mbid,
                query=clean_query,
                db=db
            )
            if mb_results:
                logger.info(f"Track autocomplete: found {len(mb_results)} from MusicBrainz")
                return mb_results
        except Exception as e:
            logger.error(f"Error in MusicBrainz track search: {e}")

        # 2. Try Local Library (Navidrome)
        try:
            navidrome = NavidromeClient()
            # If Navidrome client has a search or we can query it, let's search via Subsonic API
            # Let's inspect navidrome.py to see how we can search or query.
            # In navidrome.py: search_track(artist, title) returns bool.
            # Let's write a dedicated search method or check if we can query songs directly.
            # We can expand NavidromeClient or just query. Let's make sure if we need to search,
            # we can look for matching songs.
            if hasattr(navidrome, "search_songs_by_artist"):
                nav_results = await navidrome.search_songs_by_artist(artist_name, clean_query)
                if nav_results:
                    logger.info(f"Track autocomplete: found {len(nav_results)} from Navidrome")
                    return nav_results
        except Exception as e:
            logger.error(f"Error in Navidrome track autocomplete search: {e}")

        # 3. Try Local cache/database fallback
        logger.info("Track autocomplete: falling back to local database/cache")
        local_results = []
        seen_titles = set()

        # Check cached recordings in CacheEntry
        try:
            cached_entries = db.query(CacheEntry).filter(
                CacheEntry.entity_type == "track",
                CacheEntry.key.contains(artist_name.lower())
            ).all()
            import json
            for entry in cached_entries:
                try:
                    cached_tracks = json.loads(entry.value)
                    for t in cached_tracks:
                        title = t.get("title")
                        if title and title.lower() not in seen_titles and (not clean_query or clean_query.lower() in title.lower()):
                            seen_titles.add(title.lower())
                            local_results.append({
                                "id": t.get("id"),
                                "title": title,
                                "artist": artist_name,
                                "album": t.get("album", "Local Cache"),
                                "year": t.get("year"),
                                "cover_url": t.get("cover_url", "")
                            })
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Error reading track cache database: {e}")

        # Check Download History
        try:
            history_matches = db.query(DownloadHistory).filter(
                DownloadHistory.artist.like(f"%{artist_name}%"),
                DownloadHistory.track.like(f"%{clean_query}%") if clean_query else True
            ).all()
            for record in history_matches:
                title = record.track
                if title and title.lower() not in seen_titles:
                    seen_titles.add(title.lower())
                    local_results.append({
                        "id": None,
                        "title": title,
                        "artist": record.artist,
                        "album": record.album or "Download History",
                        "year": None,
                        "cover_url": ""
                    })
        except Exception as e:
            logger.error(f"Error querying download history for tracks: {e}")

        return local_results[:15]
