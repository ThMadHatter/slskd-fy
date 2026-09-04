import os
import sqlite3
import logging
import httpx
from typing import List, Dict, Any

logger = logging.getLogger("track_portal.beets_service")

class BeetsServiceClient:
    """
    Client service to interact with beets REST API /item/query/ endpoints
    or directly query local Beets SQLite library database to fetch metadata candidates.
    """
    def __init__(self, api_url: str = None, db_path: str = None):
        self.api_url = (api_url or os.getenv("BEETS_API_URL", "http://beets:8337")).rstrip("/")
        self.db_path = db_path or os.getenv("BEETS_DB_PATH", "/config/beets/library.db")

    async def search_items(self, query: str) -> List[Dict[str, Any]]:
        """
        Queries Beets REST API matching results: GET /item/query/<querystring>
        Falls back to local SQLite library DB or beet CLI if HTTP request fails or returns 0 matches.
        """
        url = f"{self.api_url}/item/query/{query}"
        logger.info(f"Querying beets service web API with URL: {url}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=3.0)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        results = data
                    elif isinstance(data, dict):
                        results = data.get("results", [])
                    else:
                        results = []
                    if results:
                        logger.info(f"Beets API query successful. Found {len(results)} matches.")
                        return results
            except Exception as e:
                logger.debug(f"HTTP communication with beets service at {self.api_url} failed: {e}")

        # Defensive fallback: Query local SQLite library database directly
        return self._search_sqlite_db(query)

    def _search_sqlite_db(self, query: str) -> List[Dict[str, Any]]:
        """Directly queries local Beets library SQLite database for matches."""
        possible_paths = [
            self.db_path,
            "/config/beets/library.db",
            "/config/library.db",
            os.path.expanduser("~/.config/beets/library.db")
        ]
        active_db = next((p for p in possible_paths if p and os.path.exists(p)), None)
        if not active_db:
            logger.debug("No local Beets SQLite library database found.")
            return []

        try:
            conn = sqlite3.connect(active_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Simple token parsing for query like artist:"Artist" title:"Track"
            artist_term = ""
            title_term = ""
            if 'artist:"' in query:
                try:
                    artist_term = query.split('artist:"')[1].split('"')[0]
                except Exception:
                    pass
            if 'title:"' in query:
                try:
                    title_term = query.split('title:"')[1].split('"')[0]
                except Exception:
                    pass

            if artist_term and title_term:
                cursor.execute(
                    "SELECT artist, title, album, year FROM items WHERE artist LIKE ? AND title LIKE ? LIMIT 5",
                    (f"%{artist_term}%", f"%{title_term}%")
                )
            elif artist_term:
                cursor.execute(
                    "SELECT artist, title, album, year FROM items WHERE artist LIKE ? LIMIT 5",
                    (f"%{artist_term}%",)
                )
            elif title_term:
                cursor.execute(
                    "SELECT artist, title, album, year FROM items WHERE title LIKE ? LIMIT 5",
                    (f"%{title_term}%",)
                )
            else:
                cursor.execute(
                    "SELECT artist, title, album, year FROM items WHERE artist LIKE ? OR title LIKE ? LIMIT 5",
                    (f"%{query}%", f"%{query}%")
                )

            rows = cursor.fetchall()
            results = [dict(row) for row in rows]
            conn.close()
            logger.info(f"SQLite Beets query successful. Found {len(results)} matches in {active_db}.")
            return results
        except Exception as e:
            logger.warning(f"Error querying local Beets SQLite database at {active_db}: {e}")
            return []
