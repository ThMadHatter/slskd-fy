import os
import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from pydantic import ValidationError
from app.config import settings
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

    def generate_progressive_queries(self, artist: str, track: str, strategy: str) -> List[str]:
        """
        Generates progressive, broad, and forgiving queries based on SEARCH_STRATEGY settings.
        """
        queries = []
        clean_artist = artist.replace('"', '').strip() if artist else ""
        clean_track = track.replace('"', '').strip() if track else ""

        strategy = strategy.upper().strip()

        # Step 1: Artist + Track combinations
        if clean_artist and clean_track:
            queries.append(f"{clean_artist} {clean_track}")
            queries.append(f'"{clean_artist}" {clean_track}')
            queries.append(f'"{clean_artist}" "{clean_track}"')
        elif clean_track:
            queries.append(clean_track)
        elif clean_artist:
            queries.append(clean_artist)

        # If STRICT mode, stop here
        if strategy == "STRICT":
            seen = set()
            return [q for q in queries if q and not (q in seen or seen.add(q))]

        # Step 2: Track only (if both were present)
        if clean_artist and clean_track:
            queries.append(clean_track)

        # Step 3: Artist only (if both were present)
        if clean_artist and clean_track:
            queries.append(clean_artist)
            # Add first word of artist
            artist_words = clean_artist.split()
            if len(artist_words) > 1:
                queries.append(artist_words[0])

        # If BALANCED mode, stop here
        if strategy != "AGGRESSIVE":
            seen = set()
            return [q for q in queries if q and not (q in seen or seen.add(q))]

        # Step 4: AGGRESSIVE partial track words
        if clean_track:
            track_words = clean_track.split()
            if len(track_words) >= 2:
                queries.append(" ".join(track_words[:2]))
            if len(track_words) >= 1:
                queries.append(track_words[0])

        seen = set()
        return [q for q in queries if q and not (q in seen or seen.add(q))]

    async def execute_search(self, query: SearchQuery) -> List[SlskdResult]:
        """
        [QG-002] Fallback Search Loop: STRICT -> BALANCED -> AGGRESSIVE.
        Funnels execution progressively until candidates are retrieved or search exhaustion.
        """
        from app.routers.pages import SearchDebugTracker

        strategy = os.getenv("SEARCH_STRATEGY") or settings.SEARCH_STRATEGY or "BALANCED"
        logger.info(f"FallbackSearchExecutor: Starting progressive search loop with strategy {strategy} for {query.artist} - {query.track}")

        # Generate progressive queries list
        query_strings = self.generate_progressive_queries(query.artist, query.track, strategy)

        all_results: List[SlskdResult] = []
        seen_files = set()

        # Clear/Reset telemetry
        SearchDebugTracker.last_queries_telemetry = []

        for target_q in query_strings:
            logger.info(f"FallbackSearchExecutor: Polling slskd with query '{target_q}' in Strategy {strategy}")
            start_time = time.time()

            try:
                candidates, responses = await self._poll_slskd_search(target_q)
                duration = time.time() - start_time

                # Log query telemetry to console/file
                logger.info(
                    f"\n[TELEMETRY] SEARCH_QUERY:\n"
                    f"\"{target_q}\"\n"
                    f"Results: (Peer responses): {len(responses)}, Files: {len(candidates)}, Duration: {duration:.2f}s\n"
                )

                # Store telemetry in SearchDebugTracker
                SearchDebugTracker.last_queries_telemetry.append({
                    "query": target_q,
                    "peer_responses": len(responses),
                    "files": len(candidates),
                    "duration": duration
                })

                # Deduplicate and merge candidates
                for cand in candidates:
                    key = (cand.username, cand.filename)
                    if key not in seen_files:
                        seen_files.add(key)
                        all_results.append(cand)

                # Stop only when a meaningful result set is obtained (e.g. >= 15 unique files)
                if len(all_results) >= 15:
                    logger.info(f"FallbackSearchExecutor: Meaningful result count threshold met ({len(all_results)} >= 15). Breaking loop.")
                    break
                else:
                    logger.info(f"FallbackSearchExecutor: Query yielded {len(candidates)} candidates. Combined total is {len(all_results)}. Proceeding with next fallback query if available.")

            except Exception as e:
                logger.error(f"FallbackSearchExecutor: Query execution failed for '{target_q}': {e}")
                # Graceful degradation [RSL-003]: continue to next fallback mode
                continue

        return all_results

    async def _poll_slskd_search(self, query_string: str) -> tuple[List[SlskdResult], List[Dict[str, Any]]]:
        """
        Helper method to coordinate active polling with slskd backend.
        Parses results into strongly-typed Pydantic SlskdResult schemas [CDA-002].
        """
        search_obj = await self.slskd_client.search(query_string)
        search_id = search_obj.get("id")
        if not search_id:
            return [], []

        # Poll responses for up to 5 seconds
        responses = []
        candidates: List[SlskdResult] = []
        for _ in range(5):
            await asyncio.sleep(1.0)
            responses = await self.slskd_client.get_search_responses(search_id)

            # Continuously compile and validate candidates
            candidates = []
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

            # If we have valid candidates and at least 8 peer responses, we can break early to keep interactive speed.
            # But if we have 0 files/candidates, we MUST poll for the full 5 seconds before giving up/triggering fallback.
            if len(candidates) > 0 and len(responses) >= 8:
                break

        return candidates, responses
