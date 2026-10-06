import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.services.beets_service import BeetsServiceClient
from app.services.ext_integrations import LidarrIntegrationClient
from app.models import DownloadHistory, CacheEntry

logger = logging.getLogger("track_portal.artist_service")

class ArtistService:
    @staticmethod
    async def autocomplete(query: str, db: Session) -> List[Dict[str, Any]]:
        """
        Autocomplete artist suggestions using Beets library, Lidarr API, and local DB.
        """
        logger.info(f"ArtistService.autocomplete initiated: query='{query}'")
        if not query or len(query.strip()) < 2:
            return []

        clean_query = query.strip()
        results: List[Dict[str, Any]] = []
        seen_names = set()

        # 1. Beets Library
        try:
            beets_client = BeetsServiceClient()
            beets_items = await beets_client.search_items(clean_query)
            for item in beets_items:
                name = item.get("artist")
                if name and name.lower() not in seen_names and clean_query.lower() in name.lower():
                    seen_names.add(name.lower())
                    results.append({
                        "id": item.get("mb_artistid"),
                        "name": name,
                        "type": "Artist",
                        "country": "",
                        "disambiguation": "Beets Library"
                    })
        except Exception as e:
            logger.error(f"Error in Beets artist search: {e}")

        # 2. Lidarr API
        try:
            lidarr = LidarrIntegrationClient()
            if hasattr(lidarr, "search_artists"):
                lidarr_results = await lidarr.search_artists(clean_query)
                for a in lidarr_results:
                    name = a.get("name")
                    if name and name.lower() not in seen_names:
                        seen_names.add(name.lower())
                        results.append(a)
        except Exception as e:
            logger.error(f"Error in Lidarr artist search: {e}")

        # 3. Local Cache & Download History
        try:
            history_matches = db.query(DownloadHistory).filter(
                DownloadHistory.artist.like(f"%{clean_query}%")
            ).all()
            for record in history_matches:
                name = record.artist
                if name and name.lower() not in seen_names:
                    seen_names.add(name.lower())
                    results.append({
                        "id": None,
                        "name": name,
                        "type": "Artist",
                        "country": "",
                        "disambiguation": "Download History"
                    })
        except Exception as e:
            logger.error(f"Error querying download history for artists: {e}")

        return results[:10]
