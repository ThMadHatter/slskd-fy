import os
import logging
import re
from typing import List, Dict, Any, Optional, Union
from app.services.filename_parser import parse_filename
from app.contracts.schemas import SearchQuery, SlskdResult
from app.contracts.services import SearchProviderContract

logger = logging.getLogger("track_portal.search_ranking")

# Regex patterns for junk rejection (Issue 7: Hard rejection stage)
JUNK_FILENAME_PATTERNS = [
    # Posters & Artwork
    r"\b(poster|artwork|cover|front|back|albumart|cdart|insert|booklet|folder\.jpg|cover\.jpg|thumb)\b",
    # Sample packs & stems
    r"\b(sample\s*pack|drum\s*kit|stems|multitracks|loop\s*kit|presets|wav\s*loop|loop\s*pack)\b",
    # DJ Tools & acapella collections (generic directories or compilations)
    r"\b(dj\s*tool|acapella\s*pack|acapella\s*collection|vocals\s*only|isolated\s*vocals|sound\s*effect|sfx)\b",
    # Obviously malformed / non-music or junk meta
    r"\b(password\s*protected|keygen|crack|unzip\s*me|read\s*me|readme|nfo\s*file|torrent)\b"
]

class SearchRankingService(SearchProviderContract):
    """
    [CDA-001] Refactored SearchRankingService implementing SearchProviderContract.
    Strictly handles typed data boundaries [CDA-002] while maintaining full backward-compatibility.
    """

    @staticmethod
    def should_reject_result(filename: str, ext: str) -> bool:
        """
        Hard rejection stage (Issue 7).
        Rejects non-music formats or obviously junk filenames/releases immediately.
        """
        filename_lower = filename.lower()

        # 1. Non-audio extension rejection
        if ext not in ["mp3", "flac", "wav", "m4a", "ogg", "alac", "wma", "aac", "aiff", "ape"]:
            return True

        # 2. Check JUNK patterns
        for pattern in JUNK_FILENAME_PATTERNS:
            if re.search(pattern, filename_lower):
                return True

        # 3. Obviously malformed / blob names
        basename = os.path.splitext(os.path.basename(filename))[0]
        if len(basename) < 3:
            return True
        if re.match(r"^[a-f0-9]{32,64}$", basename): # Raw hex hashes or blob files
            return True

        return False

    @classmethod
    def generate_queries(cls, query: Union[SearchQuery, str], *args, **kwargs) -> List[str]:
        """
        [QG-002] Generates optimized slskd search queries using canonical artist information.
        Accepts either SearchQuery model or raw strings for backward compatibility.
        """
        if isinstance(query, SearchQuery):
            artist = query.artist
            track = query.track
            album = query.album
            mode = query.mode
        else:
            # Backward compatible path
            artist = query
            track = args[0] if len(args) > 0 else kwargs.get("track", "")
            album = args[1] if len(args) > 1 else kwargs.get("album", None)
            mode = args[2] if len(args) > 2 else kwargs.get("mode", "A")
            # If search_mode is passed in page routing (pages.py Form value is 'search_mode')
            if not mode and kwargs.get("search_mode"):
                mode = kwargs.get("search_mode")

        clean_artist = artist.replace('"', '').strip() if artist else ""
        clean_track = track.replace('"', '').strip() if track else ""

        # Task 1: Debug Query Builder logging
        logger.info(f"Query Builder: Input Selected Artist='{artist}', Track='{track}'")

        queries = []
        mode = (mode or "A").upper().strip()

        if mode == "B":
            # Mode B: "Kendrick Lamar" "Not Like Us"
            if clean_artist and clean_track:
                queries.append(f'"{clean_artist}" "{clean_track}"')
            elif clean_artist:
                queries.append(f'"{clean_artist}"')
            elif clean_track:
                queries.append(f'"{clean_track}"')
        elif mode == "C":
            # Mode C: artist:Kendrick Lamar track:Not Like Us
            if clean_artist and clean_track:
                queries.append(f'artist:{clean_artist} track:{clean_track}')
            elif clean_artist:
                queries.append(f'artist:{clean_artist}')
            elif clean_track:
                queries.append(f'track:{clean_track}')
        else:
            # Mode A (Default): Kendrick Lamar Not Like Us
            if clean_artist and clean_track:
                queries.append(f'{clean_artist} {clean_track}')
                queries.append(f'"{clean_artist}" {clean_track}')
            elif clean_artist:
                queries.append(clean_artist)
            elif clean_track:
                queries.append(clean_track)

        # Unique values preserving order
        seen = set()
        res = [q for q in queries if not (q in seen or seen.add(q))]
        print(f"[AUDIT] GENERATED QUERY - mode={mode}, queries={res}", flush=True)
        logger.info(f"Query Builder: Generated Queries for Mode {mode}: {res}")
        return res

    @classmethod
    def score_result(
        cls,
        result: Union[SlskdResult, Dict[str, Any]],
        query: Optional[Union[SearchQuery, str]] = None,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """
        [UX-003] Scores a single slskd search result from 0 to 100.
        Accepts Pydantic models or raw parameters for backward compatibility.
        """
        if isinstance(result, SlskdResult):
            res_filename = result.filename
            res_format = result.format
            res_size = result.size
            res_bitrate = result.bitrate
            res_queue_length = result.queue_length
        else:
            # Backward compatible path
            res_filename = result.get("filename", "")
            res_format = result.get("format", "")
            res_size = result.get("size", 0)
            res_bitrate = result.get("bitrate", 0) or 0
            res_queue_length = result.get("queue_length", 0) or 0

        if isinstance(query, SearchQuery):
            target_artist = query.artist
            target_track = query.track
            target_album = query.album or ""
        elif query is not None:
            # Backward compatible path
            target_artist = query
            target_track = args[0] if len(args) > 0 else kwargs.get("target_track", "")
            target_album = args[1] if len(args) > 1 else kwargs.get("target_album", "")
            target_album = target_album or ""
        else:
            # All keyword parameters path
            target_artist = kwargs.get("target_artist", "")
            target_track = kwargs.get("target_track", "")
            target_album = kwargs.get("target_album", "")
            target_album = target_album or ""

        parsed = parse_filename(res_filename)

        # Retrieve parsed/slskd values
        parsed_artist = (parsed.get("artist") or (None if isinstance(result, SlskdResult) else result.get("artist")) or "Unknown").lower().strip()
        parsed_track = (parsed.get("track") or (None if isinstance(result, SlskdResult) else result.get("track")) or "Unknown").lower().strip()
        parsed_album = (parsed.get("album") or (None if isinstance(result, SlskdResult) else result.get("album")) or "").lower().strip()
        featured_artists = [a.lower().strip() for a in parsed.get("featured_artists", [])]

        tgt_artist = target_artist.lower().strip()
        tgt_track = target_track.lower().strip()
        tgt_album = target_album.lower().strip() if target_album else ""

        # --- Artist Confidence & Classification (Issue 3, 5, 6) ---
        artist_score = 0
        classification = "UNKNOWN"

        if parsed_artist == tgt_artist:
            artist_score = 50
            classification = "PRIMARY_ARTIST_MATCH"
        elif any(tgt_artist == f for f in featured_artists) or f"feat. {tgt_artist}" in parsed_track or f"feat {tgt_artist}" in parsed_track or f"featuring {tgt_artist}" in parsed_track:
            artist_score = 35
            classification = "FEATURED_ARTIST_MATCH"
        elif tgt_artist and (tgt_artist in parsed_artist or parsed_artist in tgt_artist or any(w in parsed_artist for w in tgt_artist.split() if len(w) > 3)):
            artist_score = 15
            classification = "PARTIAL_MATCH"
        else:
            artist_score = 0
            classification = "UNKNOWN"

        # --- Track Title Matching (Task 2) ---
        track_score = 0
        if parsed_track == tgt_track:
            track_score = 30
        elif tgt_track in parsed_track or parsed_track in tgt_track:
            track_score = 20
        elif any(word in parsed_track for word in tgt_track.split() if len(word) > 2):
            track_score = 5
        else:
            track_score = 0

        # --- Quality / Codec Scoring (Task 2) ---
        quality_score = 0
        fmt = res_format.lower()
        bitrate = res_bitrate or 0

        if fmt == "flac":
            quality_score = 20
        elif fmt == "alac":
            quality_score = 18
        elif fmt == "wav":
            quality_score = 15
        elif fmt == "mp3" and bitrate >= 320:
            quality_score = 10
        else:
            quality_score = 0

        # --- Album Match Weighting (Task 2) ---
        album_score = 0
        if tgt_album:
            if parsed_album == tgt_album:
                album_score = 10
            elif tgt_album in parsed_album or parsed_album in tgt_album:
                album_score = 5

        # Small extra credit for file size to prioritize real downloads (max 5 pts)
        size_score = 0
        size_bytes = res_size or 0
        if size_bytes > 10 * 1024 * 1024:  # > 10MB
            size_score = 5
        elif size_bytes > 1024 * 1024:     # > 1MB
            size_score = 2

        # MusicBrainz enrichment score (Issue 6)
        musicbrainz_score = 0
        # If there is enriched data (e.g. non-empty cover art, or matched year/album via MB)
        # For Pydantic model result, we can check custom attributes in backward compatible or extra properties if present.
        if not isinstance(result, SlskdResult):
            if result.get("cover_url") or result.get("mbid") or (result.get("album") and not parsed.get("album")):
                musicbrainz_score = 10

        total_score = artist_score + track_score + quality_score + album_score + size_score + musicbrainz_score
        final_score = min(max(total_score, 0), 100)

        return {
            "artist_score": artist_score,
            "track_score": track_score,
            "album_score": album_score,
            "quality_score": quality_score,
            "musicbrainz_score": musicbrainz_score,
            "size_score": size_score,
            "final_score": final_score,
            "classification": classification
        }
