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
        if not query or len(query.strip()) < 2:
            return []

        clean_query = query.strip()

        # 1. Try MusicBrainz
        try:
            mb_results = await MusicBrainzService.search_artists(clean_query, db)
            if mb_results:
                logger.info(f"Artist autocomplete: found {len(mb_results)} from MusicBrainz")
                return mb_results
        except Exception as e:
            logger.error(f"Error in MusicBrainz artist search: {e}")

        # 2. Try Lidarr API
        # Since Lidarr API is a stub, we simulate or handle it gracefully
        try:
            lidarr = LidarrIntegrationClient()
            # If Lidarr had a search_artist method, we'd use it. We'll handle it gracefully.
            if hasattr(lidarr, "search_artists"):
                lidarr_results = await lidarr.search_artists(clean_query)
                if lidarr_results:
                    logger.info(f"Artist autocomplete: found {len(lidarr_results)} from Lidarr")
                    return lidarr_results
        except Exception as e:
            logger.error(f"Error in Lidarr artist search: {e}")

        # 3. Try Local cache/database fallback
        logger.info("Artist autocomplete: falling back to local database/cache")
        local_results = []
        seen_names = set()

        # Check existing cached artists in CacheEntry
        try:
            cached_entries = db.query(CacheEntry).filter(
                CacheEntry.entity_type == "artist",
                CacheEntry.key.contains(clean_query.lower())
            ).all()
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
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Error reading artist cache database: {e}")

        # Check Download History
        try:
            history_matches = db.query(DownloadHistory).filter(
                DownloadHistory.artist.like(f"%{clean_query}%")
            ).all()
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

        return local_results[:10]
