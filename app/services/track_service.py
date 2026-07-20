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
        logger.info(f"TrackService.autocomplete initiated: artist='{artist_name}' (mbid={artist_mbid or 'none'}), query='{query}'")
        if not artist_name:
            logger.info("TrackService.autocomplete: Missing artist_name, returning empty.")
            return []

        if not query or len(query.strip()) < 2:
            logger.info("TrackService.autocomplete query too short (length < 2), returning empty.")
            return []

        clean_query = query.strip()

        # 1. Try MusicBrainz recordings
        try:
            logger.debug(f"TrackService.autocomplete: Attempting MusicBrainz recordings lookup for artist='{artist_name}', query='{clean_query}'")
            mb_results = await MusicBrainzService.search_recordings(
                artist_name=artist_name,
                artist_mbid=artist_mbid,
                query=clean_query,
                db=db
            )
            if mb_results:
                logger.info(f"TrackService.autocomplete MATCH [MusicBrainz] found {len(mb_results)} recordings for artist='{artist_name}', query='{clean_query}'")
                return mb_results
            else:
                logger.debug(f"TrackService.autocomplete: No recordings found from MusicBrainz for artist='{artist_name}', query='{clean_query}'")
        except Exception as e:
            logger.error(f"Error in MusicBrainz track search: {e}")

        # 2. Try Local Library (Navidrome)
        try:
            logger.debug(f"TrackService.autocomplete: Attempting Navidrome library lookup for artist='{artist_name}', query='{clean_query}'")
            navidrome = NavidromeClient()
            if hasattr(navidrome, "search_songs_by_artist"):
                nav_results = await navidrome.search_songs_by_artist(artist_name, clean_query)
                if nav_results:
                    logger.info(f"TrackService.autocomplete MATCH [Navidrome] found {len(nav_results)} songs for artist='{artist_name}', query='{clean_query}'")
                    return nav_results
        except Exception as e:
            logger.error(f"Error in Navidrome track autocomplete search: {e}")

        # 3. Try Local cache/database fallback
        logger.info(f"TrackService.autocomplete [Fallback] Querying local DB/cache for artist='{artist_name}', query='{clean_query}'")
        local_results = []
        seen_titles = set()

        # Check cached recordings in CacheEntry
        try:
            cached_entries = db.query(CacheEntry).filter(
                CacheEntry.entity_type == "track",
                CacheEntry.key.contains(artist_name.lower())
            ).all()
            logger.debug(f"TrackService.autocomplete: Found {len(cached_entries)} cache entries matching artist key contain '{artist_name.lower()}'")
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
                except Exception as ex:
                    logger.warning(f"Failed to parse cached track JSON for key {entry.key}: {ex}")
        except Exception as e:
            logger.error(f"Error reading track cache database: {e}")

        # Check Download History
        try:
            history_matches = db.query(DownloadHistory).filter(
                DownloadHistory.artist.like(f"%{artist_name}%"),
                DownloadHistory.track.like(f"%{clean_query}%") if clean_query else True
            ).all()
            logger.debug(f"TrackService.autocomplete: Found {len(history_matches)} download history track matches for artist='{artist_name}', query='{clean_query}'")
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

        logger.info(f"TrackService.autocomplete COMPLETED: artist='{artist_name}', query='{clean_query}', returned count={len(local_results[:15])} (source=Local Cache/DB Fallback)")
        return local_results[:15]
