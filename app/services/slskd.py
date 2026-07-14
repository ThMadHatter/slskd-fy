import logging
from typing import List, Dict, Any, Optional
import httpx
from app.config import settings

logger = logging.getLogger("track_portal.slskd")

class SlskdClient:
    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None):
        self.api_url = (api_url or settings.SLSKD_API_URL).rstrip("/")
        self.api_key = api_key or settings.SLSKD_API_KEY
        self.headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    async def search(self, query: str, timeout_sec: int = 15) -> Dict[str, Any]:
        """
        Performs a search for the specified query.
        POST /api/v0/searches
        """
        url = f"{self.api_url}/searches"
        # Include both camelCase and snake_case properties to ensure compatibility across all slskd versions
        payload = {
            "searchText": query,
            "search_text": query,
            "searchTimeout": timeout_sec,
            "search_timeout": timeout_sec,
            "filterResponses": True,
            "filter_responses": True
        }
        curl_cmd = f"curl -X POST -H \"X-API-KEY: {self.api_key}\" -H \"Content-Type: application/json\" -d '{{\"searchText\":\"{query}\"}}' {url}"
        logger.info(f"Equivalent Curl Command:\n{curl_cmd}")
        logger.info(f"Submitting slskd search for query: '{query}'")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=self.headers, timeout=20)
                response.raise_for_status()
                data = response.json()
                logger.info(f"Successfully started search. Search ID: {data.get('id')}. Response content: {data}")
                return data
            except Exception as e:
                logger.error(f"Failed to start search in slskd: {e}")
                raise

    async def get_search_state(self, search_id: str) -> Dict[str, Any]:
        """
        Gets the state/status of a search.
        GET /api/v0/searches/{id}
        """
        url = f"{self.api_url}/searches/{search_id}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Failed to fetch search state for {search_id}: {e}")
                raise

    async def get_search_responses(self, search_id: str) -> List[Dict[str, Any]]:
        """
        Gets the list of responses for a completed/active search.
        GET /api/v0/searches/{id}/responses
        """
        url = f"{self.api_url}/searches/{search_id}/responses"
        async with httpx.AsyncClient() as client:
            try:
                logger.info(f"HTTP GET Request: {url}")
                response = await client.get(url, headers=self.headers, timeout=30)
                response.raise_for_status()
                data = response.json()
                # Log a summary and the first response to keep it readable, or print full raw response
                logger.info(f"HTTP GET Response status={response.status_code}. Received {len(data)} responses. Raw: {data}")
                return data
            except Exception as e:
                logger.error(f"Failed to fetch search responses for {search_id}: {e}")
                raise

    async def delete_search(self, search_id: str) -> None:
        """
        Deletes a search to keep slskd clean.
        DELETE /api/v0/searches/{id}
        """
        url = f"{self.api_url}/searches/{search_id}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                logger.info(f"Deleted search {search_id} from slskd.")
            except Exception as e:
                logger.error(f"Failed to delete search {search_id}: {e}")

    async def enqueue_download(self, username: str, filename: str, size: int) -> bool:
        """
        Enqueues a download for a specific file.
        POST /api/v0/transfers/downloads/{username}
        Body format: [{'filename': ..., 'size': ...}]
        """
        url = f"{self.api_url}/transfers/downloads/{username}"
        payload = [{
            "filename": filename,
            "size": size
        }]
        logger.info(f"Enqueuing slskd download: '{filename}' from user '{username}' (size: {size})")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, headers=self.headers, timeout=15)
                # Success code can be 201 or 200
                if response.status_code in [200, 201, 204]:
                    logger.info("Successfully enqueued download.")
                    return True
                else:
                    logger.error(f"Enqueuing download failed with status {response.status_code}: {response.text}")
                    return False
            except Exception as e:
                logger.error(f"Exception while enqueuing download: {e}")
                return False

    async def get_downloads(self, include_removed: bool = False) -> List[Dict[str, Any]]:
        """
        Gets all active/inactive downloads.
        GET /api/v0/transfers/downloads
        """
        url = f"{self.api_url}/transfers/downloads"
        params = {"includeRemoved": str(include_removed).lower()}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, params=params, headers=self.headers, timeout=15)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Failed to retrieve downloads from slskd: {e}")
                return []

    async def cancel_download(self, username: str, id_: str) -> bool:
        """
        Cancels the specified download.
        DELETE /api/v0/transfers/downloads/{username}/{id}
        """
        url = f"{self.api_url}/transfers/downloads/{username}/{id_}"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(url, headers=self.headers, timeout=15)
                if response.status_code in [200, 204]:
                    logger.info(f"Successfully cancelled download ID: {id_} from user: {username}")
                    return True
                else:
                    logger.error(f"Failed to cancel download, status {response.status_code}: {response.text}")
                    return False
            except Exception as e:
                logger.error(f"Exception while cancelling download: {e}")
                return False
