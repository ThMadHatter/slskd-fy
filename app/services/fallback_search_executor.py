import os
import asyncio
import logging
from typing import List, Dict, Any, Optional
from app.contracts.schemas import SearchQuery, SlskdResult
from app.contracts.services import (
    SearchExecutorContract, SlskdClientContract, SearchProviderContract, CacheProviderContract
)
from app.services.search_ranking_service import SearchRankingService

logger = logging.getLogger("track_portal.fallback_search_executor")

class FallbackSearchExecutor(SearchExecutorContract):
    """
    [CDA-001] FallbackSearchExecutor coordinates the fallback search loop strategy.
    Implements SearchExecutorContract, utilizing dependency injection [CDA-003]
    and validating incoming data structures via Pydantic [CDA-002].
    """

    def __init__(
        self,
        slskd_client: SlskdClientContract,
        search_provider: SearchProviderContract,
        cache_provider: Optional[CacheProviderContract] = None
    ):
        """
        [CDA-003] Dependencies are explicitly injected at instantiation.
        """
        self.slskd_client = slskd_client
        self.search_provider = search_provider
        self.cache_provider = cache_provider

    async def execute_search(self, query: SearchQuery) -> List[SlskdResult]:
        """
        [QG-002] Fallback Search Loop: STRICT (Mode B) -> BALANCED (Mode A) -> AGGRESSIVE (Mode C).
        Funnels execution progressively until candidates are retrieved or search exhaustion.
        """
        strategies = ["B", "A", "C"]  # B: STRICT, A: BALANCED, C: AGGRESSIVE
        last_results: List[SlskdResult] = []

        logger.info(f"FallbackSearchExecutor: Starting progressive search loop for {query.artist} - {query.track}")

        for mode in strategies:
            logger.info(f"FallbackSearchExecutor: Transitioning search loop -> Mode {mode}")
            current_query = SearchQuery(
                artist=query.artist,
                track=query.track,
                album=query.album,
                mode=mode
            )

            # Generate target slskd query strings
            query_strings = self.search_provider.generate_queries(current_query)
            if not query_strings:
                continue

            target_q = query_strings[0]
            logger.info(f"FallbackSearchExecutor: Polling slskd with query '{target_q}' in Mode {mode}")

            try:
                candidates = await self._poll_slskd_search(target_q)
                if candidates:
                    logger.info(f"FallbackSearchExecutor: Found {len(candidates)} candidates in Mode {mode}. Breaking fallback loop.")
                    last_results = candidates
                    break
                else:
                    logger.info(f"FallbackSearchExecutor: Mode {mode} yielded 0 candidates.")
            except Exception as e:
                logger.error(f"FallbackSearchExecutor: Query execution failed under Mode {mode}: {e}")
                # Graceful degradation [RSL-003]: continue to next fallback mode
                continue

        return last_results

    async def _poll_slskd_search(self, query_string: str) -> List[SlskdResult]:
        """
        Helper method to coordinate active polling with slskd backend.
        Parses results into strongly-typed Pydantic SlskdResult schemas [CDA-002].
        """
        search_obj = await self.slskd_client.search(query_string)
        search_id = search_obj.get("id")
        if not search_id:
            return []

        # Poll responses briefly (up to 3 seconds for fast interactive execution)
        responses = []
        for _ in range(3):
            await asyncio.sleep(1.0)
            responses = await self.slskd_client.get_search_responses(search_id)
            if len(responses) >= 8:
                break

        candidates: List[SlskdResult] = []
        for resp in responses:
            username = resp.get("username", "")
            queue_length = resp.get("queueLength", 0) or resp.get("queue_length", 0) or 0
            files = resp.get("files", [])

            for f in files:
                filename = f.get("filename", "")
                ext = os.path.splitext(filename)[1].lstrip(".").lower()
                size = f.get("size", 0)
                bitrate = f.get("bitRate", 0) or f.get("bitrate", 0) or 0
                sample_rate = f.get("sampleRate", 0) or f.get("sample_rate", 0) or 0

                # Reject obviously malformed/junk files
                if SearchRankingService.should_reject_result(filename, ext):
                    continue

                try:
                    # Parse and validate via SlskdResult Pydantic schema [CDA-002]
                    result_model = SlskdResult(
                        filename=filename,
                        size=size,
                        username=username,
                        format=ext,
                        bitrate=bitrate,
                        sample_rate=sample_rate,
                        queue_length=queue_length
                    )
                    candidates.append(result_model)
                except ValidationError as ve:
                    logger.warning(f"FallbackSearchExecutor: File failed Pydantic validation: {ve}")
                    continue

        return candidates
