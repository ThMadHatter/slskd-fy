import logging
import uuid
from typing import List, Dict, Any, Optional
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

def start_background_poller():
    logger.info("Background poller started...")

class SlskdClient:
    def __init__(self, api_url: Optional[str] = None, api_key: Optional[str] = None):
        self.api_url = (api_url or settings.SLSKD_API_URL).rstrip("/")
        self.api_key = api_key or settings.SLSKD_API_KEY
        self.headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    # Helper method to keep httpx client setup clean and DRY
    def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(headers=self.headers)

    async def get_searches(self) -> List[Dict[str, Any]]:
        """
        Retrieves active/historical searches from slskd.
        GET /api/v0/searches
        """
        url = f"{self.api_url}/searches"
        async with self._get_client() as client:
            try:
                response = await client.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()
                return data if data is not None else []
            except Exception as e:
                logger.error(f"Failed to retrieve searches from slskd: {e}")
                return []

    async def stop_search(self, search_id: str) -> bool:
        """
        Stops the search corresponding to the specified id.
        PUT /api/v0/searches/{id}
        """
        url = f"{self.api_url}/searches/{search_id}"
        async with self._get_client() as client:
            try:
                response = await client.put(url, timeout=10)
                if response.status_code in [200, 204]:
                    logger.info(f"Stopped search {search_id} in slskd.")
                    return True
                return False
            except Exception as e:
                logger.warning(f"Failed to stop search {search_id} in slskd: {e}")
                return False

    async def cancel_search(self, search_id: str) -> None:
        await self.stop_search(search_id)

    async def clear_active_searches(self) -> None:
        """
        Clears any active/stuck slskd searches to prevent HTTP 400/409/429 concurrency blocks.
        """
        try:
            searches = await self.get_searches()
            for s in searches:
                s_id = s.get("id") or s.get("Id")
                if s_id:
                    await self.stop_search(s_id)
                    await self.delete_search(s_id)
        except Exception as e:
            logger.warning(f"Failed clearing active searches in slskd: {e}")

    async def search(
        self,
        query: str,
        search_id: Optional[str] = None,
        timeout_sec: int = 15,
        wait_until_complete: bool = False,
        file_limit: int = 10000,
        filter_responses: bool = False,
        max_peer_queue_length: int = 1000000,
        min_peer_upload_speed: int = 0,
        min_response_file_count: int = 1,
        response_limit: int = 100
    ) -> Dict[str, Any]:
        """
        Performs a search for the specified request matching slskd SearchesApi DTO.
        POST /api/v0/searches
        """
        url = f"{self.api_url}/searches"

        s_id = search_id
        if not s_id:
            try:
                s_id = str(uuid.uuid4())
            except Exception:
                s_id = None

        timeout_val = 120 if wait_until_complete else (timeout_sec or 15)

        payload = {
            "id": s_id,
            "fileLimit": file_limit,
            "filterResponses": filter_responses,
            "maximumPeerQueueLength": max_peer_queue_length,
            "minimumPeerUploadSpeed": min_peer_upload_speed,
            "minimumResponseFileCount": min_response_file_count,
            "responseLimit": response_limit,
            "searchText": query,
            "searchTimeout": timeout_val,
        }
        print(f"[AUDIT] PAYLOAD - payload={payload}", flush=True)

        safe_api_key = f"{self.api_key[:4]}...{self.api_key[-4:]}" if self.api_key else "None"
        curl_cmd = (f"curl -X POST -H \"X-API-KEY: {safe_api_key}\" "
                    f"-H \"Content-Type: application/json\" -d '{payload}' {url}")

        logger.info(f"Submitting slskd search for query: '{query}' with searchTimeout: {timeout_sec}")
        logger.debug(f"Equivalent Curl Command:\n{curl_cmd}")

        async with self._get_client() as client:
            try:
                response = await client.post(url, json=payload, timeout=20)
                response.raise_for_status()
                data = response.json()
                ret_id = data.get("id") or data.get("Id") if isinstance(data, dict) else s_id
                logger.info(f"Successfully started search. Search ID: {ret_id}.")
                return data
            except httpx.HTTPStatusError as e:
                logger.error(f"Search failed with status {e.response.status_code}: {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Failed to start search in slskd: {e}")
                raise

    async def get_search_state(self, search_id: str, include_responses: bool = False) -> Dict[str, Any]:
        url = f"{self.api_url}/searches/{search_id}"
        params = {"includeResponses": str(include_responses).lower()}
        async with self._get_client() as client:
            try:
                response = await client.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                return data if data is not None else {}
            except Exception as e:
                logger.error(f"Failed to fetch search state for {search_id}: {e}")
                raise

    async def get_search_responses(self, search_id: str) -> List[Dict[str, Any]]:
        url = f"{self.api_url}/searches/{search_id}/responses"
        async with self._get_client() as client:
            try:
                response = await client.get(url, timeout=30)
                response.raise_for_status()
                data = response.json()

                if data is None:
                    logger.info(f"Search {search_id} returned null/empty peer responses.")
                    return []

                # Calculate response files count
                total_files_count = 0
                for resp in data:
                    files = resp.get("files") or resp.get("Files") or []
                    total_files_count += len(files)
                print(f"[AUDIT] SLSKD RESPONSE COUNT - search_id={search_id!r}, peer_responses={len(data)}, total_files={total_files_count}", flush=True)

                logger.info(f"Search {search_id} returned {len(data)} peer responses.")
                return data
            except Exception as e:
                logger.error(f"Failed to fetch search responses for {search_id}: {e}")
                raise

    async def delete_search(self, search_id: str) -> None:
        url = f"{self.api_url}/searches/{search_id}"
        async with self._get_client() as client:
            try:
                response = await client.delete(url, timeout=10)
                response.raise_for_status()
                logger.info(f"Deleted search {search_id} from slskd.")
            except Exception as e:
                logger.error(f"Failed to delete search {search_id}: {e}")

    async def enqueue_download(self, username: str, filename: str, size: int) -> bool:
        url = f"{self.api_url}/transfers/downloads/{username}"
        payload = [{"filename": filename, "size": size}]

        logger.info(f"Enqueuing slskd download: '{filename}' from '{username}'")
        async with self._get_client() as client:
            try:
                response = await client.post(url, json=payload, timeout=15)
                if response.status_code in [200, 201, 204]:
                    logger.info("Successfully enqueued download.")
                    return True
                else:
                    logger.error(f"Enqueue failed (Status {response.status_code}): {response.text}")
                    return False
            except Exception as e:
                logger.error(f"Exception while enqueuing download: {e}")
                return False

    async def get_downloads(self, include_removed: bool = False) -> List[Dict[str, Any]]:
        url = f"{self.api_url}/transfers/downloads"
        params = {"includeRemoved": str(include_removed).lower()}
        async with self._get_client() as client:
            try:
                response = await client.get(url, params=params, timeout=15)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"Failed to retrieve downloads from slskd: {e}")
                return []

    async def cancel_download(self, username: str, id_: str) -> bool:
        url = f"{self.api_url}/transfers/downloads/{username}/{id_}"
        async with self._get_client() as client:
            try:
                response = await client.delete(url, timeout=15)
                if response.status_code in [200, 204]:
                    logger.info(f"Cancelled download ID: {id_} from user: {username}")
                    return True
                else:
                    logger.error(f"Cancel download failed (Status {response.status_code}): {response.text}")
                    return False
            except Exception as e:
                logger.error(f"Exception while cancelling download: {e}")
                return False
