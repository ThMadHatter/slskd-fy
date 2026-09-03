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

    def generate_progressive_queries(
        self,
        artist: str,
        track: str,
        canonical_artist: Optional[str] = None,
        strategy: str = "BALANCED"
    ) -> List[str]:
        """
        Generates progressive, broad, and forgiving queries based on artist, track, and optional canonical_artist.
        """
        return SearchRankingService.generate_queries_progressive(artist, track, canonical_artist=canonical_artist)

    async def execute_search(self, query: SearchQuery) -> List[SlskdResult]:
        """
        Sequentially triggers, polls, merges, enriches with beets, and ranks candidates.
        Guarantees that only ONE active slskd search operation is performed at any time to avoid HTTP 429.
        """
        original_artist = query.artist.strip()
        original_track = query.track.strip()
        timeout_sec = query.timeout_sec or 15
        wait_until_complete = bool(query.wait_until_complete)
        canonical_artist = None

        # Fetch canonical artist name from MusicBrainz for query seed generation (DO NOT replace original user artist)
        if original_artist:
            from app.database import SessionLocal
            from app.services.musicbrainz_service import MusicBrainzService
            db = SessionLocal()
            try:
                artists = await MusicBrainzService.search_artists(original_artist, db)
                if artists:
                    official_name = artists[0].get("name")
                    if official_name:
                        logger.info(f"Canonical MusicBrainz artist found for '{original_artist}' -> '{official_name}'")
                        canonical_artist = official_name
            except Exception as e:
                logger.error(f"Error fetching canonical artist: {e}")
            finally:
                db.close()

        # Log exact required log keyword: SEARCH_START
        logger.info(f"SEARCH_START - Artist: '{original_artist}', Track: '{original_track}'")

        # 1. Generate progressive query permutations using original input and canonical seed
        query_strings = self.generate_progressive_queries(original_artist, original_track, canonical_artist=canonical_artist)

        # Log exact required log keyword: GENERATED QUERIES
        logger.info(f"GENERATED QUERIES: {query_strings}")

        unique_candidates = []
        seen_files = set()

        # Clear any active/stuck slskd searches first
        try:
            if hasattr(self.slskd_client, "clear_active_searches"):
                await self.slskd_client.clear_active_searches()
        except Exception as e:
            logger.warning(f"Failed clearing active searches in FallbackSearchExecutor: {e}")

        # 2. Execute searches sequentially to avoid slskd parallel search limit (HTTP 429)
        for idx, q_str in enumerate(query_strings):
            # Log exact required log keyword: SEARCH_STEP_START
            logger.info(f"SEARCH_STEP_START - Executing query: '{q_str}'")

            # Fire search to slskd
            responses = []
            search_id = None
            start_time = time.time()
            try:
                # Log exact required log keyword: QUERY_EXECUTED
                logger.info(f"QUERY_EXECUTED - Executing query: '{q_str}' (timeout_sec={timeout_sec}, wait_until_complete={wait_until_complete})")
                search_obj = await self.slskd_client.search(q_str, timeout_sec=timeout_sec, wait_until_complete=wait_until_complete)
                search_id = search_obj.get("id") or search_obj.get("Id") if isinstance(search_obj, dict) else None

                if search_id:
                    poll_interval = 0.5
                    max_poll_time = 120.0 if wait_until_complete else float(timeout_sec)
                    elapsed = 0.0

                    while elapsed < max_poll_time:
                        await asyncio.sleep(poll_interval)
                        elapsed += poll_interval

                        try:
                            batch = await self.slskd_client.get_search_responses(search_id)
                            if batch:
                                responses = batch
                        except Exception as e:
                            logger.warning(f"Error fetching search responses for {search_id}: {e}")

                        # Check search state
                        try:
                            if hasattr(self.slskd_client, "get_search_state"):
                                state = await self.slskd_client.get_search_state(search_id)
                                state_str = (state.get("state") or state.get("State") or "").lower()
                                if state_str in ("complete", "timed_out", "cancelled", "completed", "timedout"):
                                    logger.info(f"Search {search_id} state reached final status '{state_str}' after {elapsed:.2f}s")
                                    break
                        except Exception as e:
                            logger.debug(f"Could not check search state for {search_id}: {e}")

                        if not wait_until_complete and len(responses) >= 10:
                            break

                    duration = time.time() - start_time
                    logger.info(f"BENCHMARK - Query '{q_str}' search completed in {duration:.2f}s with {len(responses)} peer responses")
            except Exception as e:
                logger.error(f"Error executing sequential query '{q_str}': {e}")

            # Log exact required log keyword: SEARCH_STEP_COMPLETE
            logger.info(f"SEARCH_STEP_COMPLETE - Query: '{q_str}'")

            # Parse and merge files from this query
            query_candidates_count = 0
            for resp in responses:
                username = resp.get("username") or resp.get("Username") or ""
                queue_length = resp.get("queueLength") or resp.get("queue_length") or resp.get("QueueLength") or 0
                files = resp.get("files") or resp.get("Files") or []
                for f in files:
                    filename = f.get("filename") or f.get("Filename") or ""
                    ext = os.path.splitext(filename)[1].lstrip(".").lower()
                    size = f.get("size") or f.get("Size") or 0
                    bitrate = f.get("bitRate") or f.get("bitrate") or f.get("BitRate") or 0
                    sample_rate = f.get("sampleRate") or f.get("sample_rate") or f.get("SampleRate") or 0

                    # Reject obviously malformed/junk files
                    if SearchRankingService.should_reject_result(filename, ext):
                        continue

                    # Deduplicate in-memory by username and filename
                    key = (username, filename)
                    if key not in seen_files:
                        seen_files.add(key)
                        query_candidates_count += 1

                        parsed = parse_filename(filename)
                        unique_candidates.append({
                            "filename": filename,
                            "size": size,
                            "username": username,
                            "format": ext,
                            "bitrate": bitrate,
                            "sample_rate": sample_rate,
                            "queue_length": queue_length,
                            "parsed_artist": parsed.get("artist") or original_artist or "Unknown",
                            "parsed_track": parsed.get("track") or original_track or "Unknown",
                            "parsed_album": parsed.get("album") or "",
                            "parsed_year": parsed.get("year") or None
                        })

            # Clean up the search in slskd sequentially AFTER polling finishes
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
            if cand["parsed_artist"].lower() == original_artist.lower():
                temp_score += 40
            if cand["parsed_track"].lower() == original_track.lower():
                temp_score += 30
            cand["temp_score"] = temp_score

        unique_candidates.sort(key=lambda x: x["temp_score"], reverse=True)
        top_candidates = unique_candidates[:20]

        # Log exact required log keyword: BEETS ENRICHMENT
        logger.info("BEETS ENRICHMENT - Querying beets service API for top results")
        for cand in top_candidates:
            cand["beets_confidence"] = False
            try:
                beets_matches = await self.beets_client.search_items(f'artist:"{cand["parsed_artist"]}" title:"{cand["parsed_track"]}"')
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
            except Exception as e:
                logger.warning(f"Failed beets enrichment for candidate '{cand['filename']}': {e}")

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
            res_model.score_reasons = scores.get("score_reasons")
            final_results.append(res_model)

        # 5. Tie-breaker sorting
        # Prefer: 1. Original release, 2. Single release, 3. Album release, 4. FLAC, 5. High bitrate MP3
        # Over: remixes, edits, mashups, DJ versions
        def sort_key(x: SlskdResult):
            fn_lower = x.filename.lower()

            # Detect any remix/edit/mashup/dj keywords
            has_penalties = any(w in fn_lower for w in [
                "remix", "rework", "vip mix", "extended mix", "mashup", "bootleg",
                "edit", "intro", "outro", "transition", "quick hit", "radio edit", "dj tool", "dj tools"
            ])
            prefer_original = not has_penalties

            is_single = bool("single" in fn_lower or (x.parsed_album and "single" in x.parsed_album.lower()))
            is_album = bool(bool(x.parsed_album) and not is_single)

            is_flac = x.format.lower() == "flac"
            is_high_bitrate_mp3 = x.format.lower() == "mp3" and (x.bitrate or 0) >= 320

            # Boolean True (1) sorts before False (0) under reverse=True
            return (
                x.score or 0,
                prefer_original,
                is_single,
                is_album,
                is_flac,
                is_high_bitrate_mp3
            )

        final_results.sort(key=sort_key, reverse=True)
        return final_results
