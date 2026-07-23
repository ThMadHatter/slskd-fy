import os
import logging
import httpx
from typing import List, Dict, Any

logger = logging.getLogger("track_portal.beets_service")

class BeetsServiceClient:
    """
    Client service to interact with beets REST API /item/query/ endpoints
    to fetch metadata candidates from beets library database.
    """
    def __init__(self, api_url: str = None):
        self.api_url = (api_url or os.getenv("BEETS_API_URL", "http://beets:8337")).rstrip("/")

    async def search_items(self, query: str) -> List[Dict[str, Any]]:
        """
        Queries Beets REST API matching results: GET /item/query/<querystring>
        Handles both raw list response (official beets format) and defensive dict wrappers.
        """
        url = f"{self.api_url}/item/query/{query}"
        logger.info(f"Querying beets service web API with URL: {url}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        results = data
                    elif isinstance(data, dict):
                        results = data.get("results", [])
                    else:
                        results = []
                    logger.info(f"Beets query successful. Found {len(results)} matches.")
                    return results
                else:
                    logger.warning(f"Beets query failed with status: {response.status_code}")
                    return []
            except Exception as e:
                logger.error(f"Failed to communicate with beets service at {self.api_url}: {e}")
                return []
