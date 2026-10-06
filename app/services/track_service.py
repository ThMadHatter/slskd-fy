import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.services.beets_service import BeetsServiceClient
from app.services.navidrome import NavidromeClient
from app.models import DownloadHistory

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
        Autocomplete track suggestions using Beets library, Navidrome, and Download History.
        """
        logger.info(f"TrackService.autocomplete initiated: artist='{artist_name}', query='{query}'")
        if not artist_name or not query or len(query.strip()) < 2:
            return []

        clean_query = query.strip()
        results: List[Dict[str, Any]] = []
        seen_titles = set()

        # 1. Beets Library
        try:
            beets_client = BeetsServiceClient()
            q_str = f'artist:"{artist_name}" title:"{clean_query}"' if artist_name else f'title:"{clean_query}"'
            beets_items = await beets_client.search_items(q_str)
            for item in beets_items:
                title = item.get("title")
                if title and title.lower() not in seen_titles:
                    seen_titles.add(title.lower())
                    results.append({
                        "id": item.get("mb_trackid"),
                        "title": title,
                        "artist": item.get("artist") or artist_name,
                        "album": item.get("album") or "",
                        "year": item.get("year"),
                        "cover_url": ""
                    })
        except Exception as e:
            logger.error(f"Error in Beets track autocomplete search: {e}")

        # 2. Navidrome Library
        try:
            navidrome = NavidromeClient()
            if hasattr(navidrome, "search_songs_by_artist"):
                nav_results = await navidrome.search_songs_by_artist(artist_name, clean_query)
                for s in nav_results:
                    title = s.get("title")
                    if title and title.lower() not in seen_titles:
                        seen_titles.add(title.lower())
                        results.append(s)
        except Exception as e:
            logger.error(f"Error in Navidrome track autocomplete search: {e}")

        # 3. Download History Fallback
        try:
            history_matches = db.query(DownloadHistory).filter(
                DownloadHistory.artist.like(f"%{artist_name}%"),
                DownloadHistory.track.like(f"%{clean_query}%")
            ).all()
            for record in history_matches:
                title = record.track
                if title and title.lower() not in seen_titles:
                    seen_titles.add(title.lower())
                    results.append({
                        "id": None,
                        "title": title,
                        "artist": record.artist,
                        "album": record.album or "Download History",
                        "year": None,
                        "cover_url": ""
                    })
        except Exception as e:
            logger.error(f"Error querying download history for tracks: {e}")

        return results[:15]
