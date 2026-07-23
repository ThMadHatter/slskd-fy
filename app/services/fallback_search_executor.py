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
from app.services.filename_parser import parse_filename
from app.services.beets_service import BeetsServiceClient

logger = logging.getLogger("track_portal.fallback_search_executor")

class FallbackSearchExecutor(SearchExecutorContract):
    """
    [CDA-001] FallbackSearchExecutor coordinates the fallback search loop strategy sequentially.
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
        self.beets_client = BeetsServiceClient()

    def generate_progressive_queries(self, artist: str, track: str, strategy: str = "BALANCED") -> List[str]:
        """
        Generates progressive, broad, and forgiving queries based on artist and track.
        """
        return SearchRankingService.generate_queries_progressive(artist, track)

    async def execute_search(self, query: SearchQuery) -> List[SlskdResult]:
        """
        Sequentially triggers, polls, merges, enriches with beets, and ranks candidates.
        Guarantees that only ONE active slskd search operation is performed at any time to avoid HTTP 429.
        """
        artist = query.artist.strip()
        track = query.track.strip()

        # Log exact required log keyword: SEARCH_START
        logger.info(f"SEARCH_START - Artist: '{artist}', Track: '{track}'")

        # 1. Generate progressive query permutations
        query_strings = self.generate_progressive_queries(artist, track)

        # Log exact required log keyword: GENERATED QUERIES
        logger.info(f"GENERATED QUERIES: {query_strings}")

        unique_candidates = []
        seen_files = set()

        # 2. Execute searches sequentially to avoid slskd parallel search limit (HTTP 429)
        for idx, q_str in enumerate(query_strings):
            # Log exact required log keyword: SEARCH_STEP_START
            logger.info(f"SEARCH_STEP_START - Executing query: '{q_str}'")

            # Fire search to slskd
            responses = []
            search_id = None
            try:
                # Log exact required log keyword: QUERY_EXECUTED
                logger.info(f"QUERY_EXECUTED - Executing query: '{q_str}'")
                search_obj = await self.slskd_client.search(q_str)
                search_id = search_obj.get("id")

                if search_id:
                    # Poll responses sequentially
                    for _ in range(5):
                        await asyncio.sleep(1.0)
                        responses = await self.slskd_client.get_search_responses(search_id)
                        if len(responses) >= 8:
                            break
            except Exception as e:
                logger.error(f"Error executing sequential query '{q_str}': {e}")

            # Log exact required log keyword: SEARCH_STEP_COMPLETE
            logger.info(f"SEARCH_STEP_COMPLETE - Query: '{q_str}'")

            # Parse and merge files from this query
            query_candidates_count = 0
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

                    # Deduplicate in-memory by username and filename
                    key = (username, filename)
                    if key not in seen_files:
                        seen_files.add(key)

                        parsed = parse_filename(filename)
                        unique_candidates.append({
                            "filename": filename,
                            "size": size,
                            "username": username,
                            "format": ext,
                            "bitrate": bitrate,
                            "sample_rate": sample_rate,
                            "queue_length": queue_length,
                            "parsed_artist": parsed.get("artist") or artist or "Unknown",
                            "parsed_track": parsed.get("track") or track or "Unknown",
                            "parsed_album": parsed.get("album") or "",
                            "parsed_year": parsed.get("year") or None
                        })
                    query_candidates_count += 1

            # Clean up the search in slskd sequentially before initiating the next query
            if search_id:
                try:
                    await self.slskd_client.delete_search(search_id)
                except Exception as e:
                    logger.warning(f"Failed to delete search {search_id} from slskd: {e}")

            # Log exact required log keyword: QUERY_RESULT_COUNT
            logger.info(f"QUERY_RESULT_COUNT - Query: '{q_str}', Count: {query_candidates_count}")

            # Log exact required log keyword: RESULT_COUNT
            logger.info(f"RESULT_COUNT - Query: '{q_str}', Results: {query_candidates_count}")

            # Stop the sequential fallback loop early if we hit a robust threshold of results (e.g. 15 unique results)
            if len(unique_candidates) >= 15:
                logger.info(f"Sequential search threshold reached ({len(unique_candidates)} >= 15). Stopping fallback loop.")
                break
            elif idx < len(query_strings) - 1:
                # Log exact required log keyword: FALLBACK_TRIGGERED
                logger.info(f"FALLBACK_TRIGGERED - Low result count ({len(unique_candidates)}). Proceeding with next sequential query.")

        # Log exact required log keyword: DEDUPLICATION
        logger.info(f"DEDUPLICATION - Completed. Unique count: {len(unique_candidates)}")

        # 3. Beets Enrichment on top candidates
        # Sort initially by raw match heuristics to get the top results (e.g. up to 20 candidates)
        for cand in unique_candidates:
            temp_score = 0
            if cand["parsed_artist"].lower() == artist.lower():
                temp_score += 40
            if cand["parsed_track"].lower() == track.lower():
                temp_score += 30
            cand["temp_score"] = temp_score

        unique_candidates.sort(key=lambda x: x["temp_score"], reverse=True)
        top_candidates = unique_candidates[:20]

        # Log exact required log keyword: BEETS ENRICHMENT
        logger.info("BEETS ENRICHMENT - Querying beets service API for top results")
        for cand in top_candidates:
            beets_matches = await self.beets_client.search_items(f'artist:"{cand["parsed_artist"]}" title:"{cand["parsed_track"]}"')
            cand["beets_confidence"] = False
            if beets_matches:
                # We have a high confidence match! Enrich metadata
                best_match = beets_matches[0]
                cand["parsed_artist"] = best_match.get("artist") or cand["parsed_artist"]
                cand["parsed_track"] = best_match.get("title") or cand["parsed_track"]
                cand["parsed_album"] = best_match.get("album") or cand["parsed_album"]
                cand["parsed_year"] = best_match.get("year") or cand["parsed_year"]
                cand["beets_confidence"] = True

                # Log exact required log keyword: ENRICHMENT_APPLIED
                logger.info(f"ENRICHMENT_APPLIED - Filename: '{cand['filename']}', Beets Artist: '{best_match.get('artist')}', Beets Track: '{best_match.get('title')}'")

        # 4. Final Ranking and Scoring
        # Log exact required log keyword: RANKING DECISIONS
        logger.info("RANKING DECISIONS - Computing final scores and sorting candidates")
        final_results: List[SlskdResult] = []
        for cand in unique_candidates:
            # Build SlskdResult model
            res_model = SlskdResult(
                filename=cand["filename"],
                size=cand["size"],
                username=cand["username"],
                format=cand["format"],
                bitrate=cand["bitrate"],
                sample_rate=cand["sample_rate"],
                queue_length=cand["queue_length"],
                parsed_artist=cand["parsed_artist"],
                parsed_track=cand["parsed_track"],
                parsed_album=cand["parsed_album"],
                parsed_year=cand["parsed_year"],
                beets_confidence=cand.get("beets_confidence", False)
            )

            # Calculate scores using ranking service
            scores = SearchRankingService.score_candidate(res_model, query, beets_confidence=cand.get("beets_confidence", False))
            res_model.score = scores["final_score"]

            # Log exact required log keyword: RANKING_SCORE
            logger.info(f"RANKING_SCORE - Filename: '{cand['filename']}', Score: {res_model.score}, Decisions: {scores}")
            final_results.append(res_model)

        # Sort final results by score descending, then lossless formats first
        lossless_exts = {"flac", "alac", "wav", "ape", "aiff"}
        final_results.sort(key=lambda x: (x.score or 0, x.format in lossless_exts), reverse=True)
        return final_results
