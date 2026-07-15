import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.services.musicbrainz_service import MusicBrainzService
from app.services.ext_integrations import LidarrIntegrationClient
from app.models import DownloadHistory, CacheEntry

logger = logging.getLogger("track_portal.artist_service")

class ArtistService:
    @staticmethod
    async def autocomplete(query: str, db: Session) -> List[Dict[str, Any]]:
        """
        Autocomplete artist suggestions.
        Priority:
        1. MusicBrainz
        2. Lidarr API
        3. Local cache/database
        """
        logger.info(f"ArtistService.autocomplete initiated: query='{query}'")
        if not query or len(query.strip()) < 2:
            logger.info("ArtistService.autocomplete query too short (length < 2), returning empty.")
            return []

        clean_query = query.strip()

        # 1. Try MusicBrainz
        try:
            logger.debug(f"ArtistService.autocomplete: Attempting MusicBrainz lookup for '{clean_query}'")
            mb_results = await MusicBrainzService.search_artists(clean_query, db)
            if mb_results:
                logger.info(f"ArtistService.autocomplete MATCH [MusicBrainz] found {len(mb_results)} artists for query='{clean_query}'")
                return mb_results
            else:
                logger.debug(f"ArtistService.autocomplete: No results found from MusicBrainz for '{clean_query}'")
        except Exception as e:
            logger.error(f"Error in MusicBrainz artist search: {e}")

        # 2. Try Lidarr API
        # Since Lidarr API is a stub, we simulate or handle it gracefully
        try:
            logger.debug(f"ArtistService.autocomplete: Attempting Lidarr API lookup for '{clean_query}'")
            lidarr = LidarrIntegrationClient()
            # If Lidarr had a search_artist method, we'd use it. We'll handle it gracefully.
            if hasattr(lidarr, "search_artists"):
                lidarr_results = await lidarr.search_artists(clean_query)
                if lidarr_results:
                    logger.info(f"ArtistService.autocomplete MATCH [Lidarr] found {len(lidarr_results)} artists for query='{clean_query}'")
                    return lidarr_results
        except Exception as e:
            logger.error(f"Error in Lidarr artist search: {e}")

        # 3. Try Local cache/database fallback
        logger.info(f"ArtistService.autocomplete [Fallback] Querying local DB/cache for query='{clean_query}'")
        local_results = []
        seen_names = set()

        # Check existing cached artists in CacheEntry
        try:
            cached_entries = db.query(CacheEntry).filter(
                CacheEntry.entity_type == "artist",
                CacheEntry.key.contains(clean_query.lower())
            ).all()
            logger.debug(f"ArtistService.autocomplete: Found {len(cached_entries)} cache entries matching key containing '{clean_query.lower()}'")
            for entry in cached_entries:
                # Value is stored as JSON array of dicts
                import json
                try:
                    cached_artists = json.loads(entry.value)
                    for a in cached_artists:
                        name = a.get("name")
                        if name and name.lower() not in seen_names and clean_query.lower() in name.lower():
                            seen_names.add(name.lower())
                            local_results.append({
                                "id": a.get("id"),
                                "name": name,
                                "type": a.get("type", "Artist"),
                                "country": a.get("country", ""),
                                "disambiguation": a.get("disambiguation", "Local Cache")
                            })
                except Exception as ex:
                    logger.warning(f"Failed to parse cached artist JSON for entry {entry.key}: {ex}")
        except Exception as e:
            logger.error(f"Error reading artist cache database: {e}")

        # Check Download History
        try:
            history_matches = db.query(DownloadHistory).filter(
                DownloadHistory.artist.like(f"%{clean_query}%")
            ).all()
            logger.debug(f"ArtistService.autocomplete: Found {len(history_matches)} download history matches for '{clean_query}'")
            for record in history_matches:
                name = record.artist
                if name and name.lower() not in seen_names:
                    seen_names.add(name.lower())
                    local_results.append({
                        "id": None,
                        "name": name,
                        "type": "Artist",
                        "country": "",
                        "disambiguation": "Download History"
                    })
        except Exception as e:
            logger.error(f"Error querying download history for artists: {e}")

        logger.info(f"ArtistService.autocomplete COMPLETED: query='{clean_query}', returned count={len(local_results[:10])} (source=Local Cache/DB Fallback)")
        return local_results[:10]
