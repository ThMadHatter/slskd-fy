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

    async def ping_check(self) -> Dict[str, Any]:
        """
        Pings the Navidrome Subsonic endpoint to check connectivity and status.
        Useful for diagnostics/health checks.
        """
        url = f"{self.base_url}/rest/ping.view"
        params = self._get_auth_params()

        logger.info(f"Pinging Navidrome Subsonic API at: {url}")
        async with httpx.AsyncClient() as client:
            try:
                # Use a smaller timeout for healthchecks to prevent blocking
                response = await client.get(url, params=params, timeout=5)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        subsonic_response = data.get("subsonic-response", {})
                        if subsonic_response.get("status") == "ok":
                            return {"connected": True, "version": subsonic_response.get("version"), "message": "OK"}
                        else:
                            err = subsonic_response.get("error", {})
                            msg = f"Subsonic Error {err.get('code')}: {err.get('message')}"
                            logger.error(f"Navidrome ping returned error status: {msg}")
                            return {"connected": False, "message": msg}
                    except Exception as e:
                        logger.error(f"Navidrome ping response is not valid JSON: {response.text[:200]}")
                        return {"connected": False, "message": f"Invalid JSON response: {e}"}
                else:
                    logger.error(f"Navidrome ping returned HTTP {response.status_code}")
                    return {"connected": False, "message": f"HTTP status {response.status_code}"}
            except httpx.ConnectError as e:
                logger.error(f"Navidrome connection failed: connection refused or unresolvable host: {e}")
                return {"connected": False, "message": f"Connection refused/failed: {e}"}
            except httpx.TimeoutException as e:
                logger.error(f"Navidrome connection timeout: {e}")
                return {"connected": False, "message": f"Connection timed out: {e}"}
            except Exception as e:
                logger.error(f"Exception during Navidrome ping check: {e}")
                return {"connected": False, "message": str(e)}

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
                logger.warning(f"Navidrome track search is currently unavailable: {e}")
                return False

    async def search_songs_by_artist(self, artist_name: str, query: str) -> List[Dict[str, Any]]:
        """
        Searches Navidrome for songs by artist and queries. Returns list of recordings/tracks.
        """
        url = f"{self.base_url}/rest/search3.view"
        # Search for artist name combined with query
        full_query = f"{artist_name} {query}" if query else artist_name
        params = self._get_auth_params()
        params["query"] = full_query

        logger.info(f"Querying Navidrome songs for autocomplete: '{full_query}'")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, timeout=10)
                results = []
                if response.status_code == 200:
                    data = response.json()
                    subsonic_response = data.get("subsonic-response", {})
                    if subsonic_response.get("status") == "ok":
                        search_result = subsonic_response.get("searchResult3", {})
                        song_list = search_result.get("song", [])

                        normalized_artist = artist_name.lower().strip()
                        for song in song_list:
                            song_artist = song.get("artist", "").lower().strip()
                            # Ensure the song artist is a close match to the selected artist
                            if normalized_artist in song_artist or song_artist in normalized_artist:
                                results.append({
                                    "id": song.get("id"),
                                    "title": song.get("title"),
                                    "artist": song.get("artist"),
                                    "album": song.get("album", ""),
                                    "year": song.get("year"),
                                    "cover_url": f"{self.base_url}/rest/getCoverArt.view?id={song.get('coverArt')}&u={self.username}&t={params.get('t')}&s={params.get('s')}&v=1.16.0&c=trackportal" if song.get("coverArt") else ""
                                })
                return results
            except Exception as e:
                logger.error(f"Exception during Navidrome songs autocomplete search: {e}")
                return []
