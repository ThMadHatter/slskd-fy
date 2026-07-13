import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("track_portal.ext_integrations")

class LidarrIntegrationClient:
    """Extension point for Lidarr HTTP API integration."""
    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None):
        self.api_url = api_url or "http://localhost:8686/api/v1"
        self.api_key = api_key or ""

    async def get_wanted_albums(self) -> Dict[str, Any]:
        """Fetch wanted/missing list from Lidarr."""
        logger.info("Lidarr integration stub: get_wanted_albums")
        return {"records": []}

    async def trigger_import(self, folder_path: str) -> bool:
        """Tell Lidarr to scan and import a downloaded folder."""
        logger.info(f"Lidarr integration stub: trigger_import for path {folder_path}")
        return True


class MusicBrainzClient:
    """Extension point for MusicBrainz XML/JSON metadata service."""
    def __init__(self):
        self.base_url = "https://musicbrainz.org/ws/2"

    async def lookup_track(self, artist: str, title: str) -> Optional[Dict[str, Any]]:
        """Lookup standard MBID, release year, genre, etc."""
        logger.info(f"MusicBrainz stub: looking up track '{artist}' - '{title}'")
        return None


class LastFMClient:
    """Extension point for Last.fm API (scrobbling/album art)."""
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or ""

    async def get_track_info(self, artist: str, title: str) -> Dict[str, Any]:
        """Fetch artist/track tags, cover art, similar tracks."""
        logger.info(f"Last.fm stub: get_track_info for '{artist}' - '{title}'")
        return {}


class ListenBrainzClient:
    """Extension point for ListenBrainz API (scrobbling/playing now)."""
    def __init__(self, token: Optional[str] = None):
        self.token = token or ""

    async def scrobble(self, artist: str, title: str, timestamp: int) -> bool:
        """Submit a track scrobble."""
        logger.info(f"ListenBrainz stub: scrobbling '{artist}' - '{title}'")
        return True
