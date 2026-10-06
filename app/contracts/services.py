from typing import Protocol, List, Optional, Dict, Any
from app.contracts.schemas import SearchQuery, SlskdResult, TelemetryData

class CacheProviderContract(Protocol):
    """
    [CDA-001] Protocol defining the cache provider storage contract.
    """
    def get(self, key: str, domain: str = "general") -> Optional[Any]:
        """
        Retrieves a cached item by key and domain.
        """
        ...

    def set(self, key: str, value: Any, domain: str = "general", ttl_days: int = 1) -> None:
        """
        Persistently writes an item to the cache with a specified TTL.
        """
        ...


class SlskdClientContract(Protocol):
    """
    [CDA-001] Protocol defining the Slskd REST interaction contract.
    Decouples raw API invocations.
    """
    async def search(
        self,
        query: str,
        timeout_sec: int = 15,
        wait_until_complete: bool = False
    ) -> Dict[str, Any]:
        """
        Launches an asynchronous search on the slskd backend.
        """
        ...

    async def get_search_responses(self, search_id: str) -> List[Dict[str, Any]]:
        """
        Polls completed file listings for a specific active search ID.
        """
        ...

    async def enqueue_download(
        self,
        username: str,
        filename: str,
        size: int
    ) -> bool:
        """
        Instructs slskd to start downloading a specific file from a peer.
        """
        ...

    async def get_downloads(self, include_removed: bool = False) -> List[Dict[str, Any]]:
        """
        Retrieves current transfer queues and active downloads from slskd.
        """
        ...

    async def cancel_download(self, username: str, id_: str) -> bool:
        """
        Cancels an active download queue on the slskd backend.
        """
        ...


class TelemetryContract(Protocol):
    """
    [CDA-001] Protocol defining execution metrics and telemetry tracking.
    Supports asynchronous, non-blocking writes.
    """
    def record_search_metrics(self, data: TelemetryData) -> None:
        """
        [DAT-001] Safely registers search performance analytics without blocking.
        """
        ...

    def get_aggregate_stats(self) -> Dict[str, Any]:
        """
        Retrieves formatted performance statistics.
        """
        ...
