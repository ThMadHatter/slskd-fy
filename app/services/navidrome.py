import hashlib
import logging
import random
import string
from typing import Optional, Dict, Any, List
import httpx
from app.config import settings

logger = logging.getLogger("track_portal.navidrome")

class NavidromeClient:
    def __init__(self):
        self.base_url = settings.NAVIDROME_URL.rstrip("/")
        self.username = settings.NAVIDROME_USER
        self.password = settings.NAVIDROME_PASSWORD
        self.token = settings.NAVIDROME_TOKEN
        self.salt = settings.NAVIDROME_SALT

    def _get_auth_params(self) -> Dict[str, str]:
        """
        Generates Subsonic API authentication parameters.
        Subsonic supports token/salt authentication:
        t = md5(password + salt)
        """
        if self.token and self.salt:
            return {
                "u": self.username,
                "t": self.token,
                "s": self.salt,
                "v": "1.16.0",
                "c": "trackportal",
                "f": "json"
            }
        elif self.password:
            # Generate a random salt
            salt = "".join(random.choices(string.ascii_letters + string.digits, k=10))
            hash_input = self.password + salt
            token = hashlib.md5(hash_input.encode("utf-8")).hexdigest()
            return {
                "u": self.username,
                "t": token,
                "s": salt,
                "v": "1.16.0",
                "c": "trackportal",
                "f": "json"
            }
        else:
            # Fallback to no-auth or configured values
            return {
                "u": self.username,
                "v": "1.16.0",
                "c": "trackportal",
                "f": "json"
            }

    async def start_scan(self) -> bool:
        """
        Triggers a library rescan in Navidrome using startScan.view Subsonic API.
        """
        url = f"{self.base_url}/rest/startScan.view"
        params = self._get_auth_params()

        logger.info("Triggering Navidrome library rescan via Subsonic API")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    subsonic_response = data.get("subsonic-response", {})
                    if subsonic_response.get("status") == "ok":
                        scan_status = subsonic_response.get("scanStatus", {})
                        logger.info(f"Navidrome scan triggered successfully: {scan_status}")
                        return True
                    else:
                        error_msg = subsonic_response.get("error", {}).get("message", "Unknown Subsonic error")
                        logger.error(f"Navidrome startScan returned error: {error_msg}")
                        return False
                else:
                    logger.error(f"Failed to scan Navidrome, status code {response.status_code}")
                    return False
            except Exception as e:
                logger.error(f"Exception while scanning Navidrome: {e}")
                return False

    async def search_track(self, artist: str, title: str) -> bool:
        """
        Searches Navidrome library for matching tracks using search3.view.
        Returns True if a track with matching artist and title is found.
        """
        url = f"{self.base_url}/rest/search3.view"
        query = f"{artist} {title}"
        params = self._get_auth_params()
        params["query"] = query

        logger.info(f"Searching Navidrome for track duplicate: '{query}'")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    subsonic_response = data.get("subsonic-response", {})
                    if subsonic_response.get("status") == "ok":
                        # Look at searchResult3 inside subsonic-response
                        search_result = subsonic_response.get("searchResult3", {})
                        song_list = search_result.get("song", [])

                        # Normalize inputs for robust comparison
                        normalized_artist = artist.lower().strip()
                        normalized_title = title.lower().strip()

                        for song in song_list:
                            song_artist = song.get("artist", "").lower().strip()
                            song_title = song.get("title", "").lower().strip()
                            # Check for a match
                            if (normalized_artist in song_artist or song_artist in normalized_artist) and \
                               (normalized_title in song_title or song_title in normalized_title):
                                logger.info(f"Found exact/close match in Navidrome: '{song.get('artist')}' - '{song.get('title')}'")
                                return True
                        return False
                    else:
                        logger.error("Subsonic response status was not ok")
                        return False
                else:
                    logger.error(f"Subsonic search failed with HTTP status: {response.status_code}")
                    return False
            except Exception as e:
                logger.error(f"Exception searching Navidrome: {e}")
                return False
