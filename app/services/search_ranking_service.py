import os
import logging
import re
from typing import List, Dict, Any, Optional, Union
from app.services.filename_parser import parse_filename
from app.contracts.schemas import SearchQuery, SlskdResult
from app.contracts.services import SearchProviderContract

logger = logging.getLogger("track_portal.search_ranking")

# Regex patterns for junk rejection
JUNK_FILENAME_PATTERNS = [
    r"\b(poster|artwork|cover|front|back|albumart|cdart|insert|booklet|folder\.jpg|cover\.jpg|thumb)\b",
    r"\b(sample\s*pack|drum\s*kit|stems|multitracks|loop\s*kit|presets|wav\s*loop|loop\s*pack)\b",
    r"\b(dj\s*tool|acapella\s*pack|acapella\s*collection|vocals\s*only|isolated\s*vocals|sound\s*effect|sfx)\b",
    r"\b(password\s*protected|keygen|crack|unzip\s*me|read\s*me|readme|nfo\s*file|torrent)\b"
]

class SearchRankingService(SearchProviderContract):
    """
    SearchRankingService implements query generation, result filtering,
    and a robust scoring/ranking engine for Soulseek files.
    """

    @staticmethod
    def should_reject_result(filename: str, ext: str) -> bool:
        """
        Rejects non-music formats or obviously junk files.
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
        if re.match(r"^[a-f0-9]{32,64}$", basename): # Raw hex hashes
            return True

        return False

    @classmethod
    def generate_queries_progressive(cls, artist: str, track_or_album: str) -> List[str]:
        """
        Generates progressive, broad, and robust query permutations based on inputs.
        """
        queries = []
        clean_artist = artist.replace('"', '').strip() if artist else ""
        clean_track = track_or_album.replace('"', '').strip() if track_or_album else ""

        # Step 1: Broad Artist + Track combination
        if clean_artist and clean_track:
            queries.append(f"{clean_artist} {clean_track}")
            # Step 2: Quoted Artist + Track
            queries.append(f'"{clean_artist}" {clean_track}')
            # Step 3: Quoted Artist + Quoted Track
            queries.append(f'"{clean_artist}" "{clean_track}"')

        # Step 4: Track/Album only
        if clean_track:
            queries.append(clean_track)

        # Step 5: Artist only
        if clean_artist:
            queries.append(clean_artist)
            # First word of artist
            artist_words = clean_artist.split()
            if len(artist_words) > 1:
                queries.append(artist_words[0])

        # Step 6: Partials of Track
        if clean_track:
            track_words = clean_track.split()
            if len(track_words) >= 2:
                queries.append(" ".join(track_words[:2]))
            if len(track_words) >= 1:
                queries.append(track_words[0])

        # Unique values preserving order
        seen = set()
        res = [q for q in queries if q and not (q in seen or seen.add(q))]
        return res

    @classmethod
    def score_candidate(
        cls,
        result: SlskdResult,
        query: SearchQuery,
        beets_confidence: bool = False
    ) -> Dict[str, Any]:
        """
        Scores a candidate result based on robust criteria from 0 to 100.
        """
        filename = result.filename
        ext = result.format.lower().strip(".")
        size = result.size
        bitrate = result.bitrate or 0

        # Use enriched values on SlskdResult if present, else parse filename
        parsed_artist = (result.parsed_artist or parse_filename(filename).get("artist") or "Unknown").lower().strip()
        parsed_track = (result.parsed_track or parse_filename(filename).get("track") or "Unknown").lower().strip()
        parsed_album = (result.parsed_album or parse_filename(filename).get("album") or "").lower().strip()

        tgt_artist = query.artist.lower().strip()
        tgt_track = query.track.lower().strip()

        # Score components
        artist_score = 0
        track_score = 0
        album_score = 0
        beets_score = 0
        quality_score = 0
        bitrate_score = 0
        filename_score = 0

        # 1. Exact artist match
        if tgt_artist and parsed_artist == tgt_artist:
            artist_score = 40
        elif tgt_artist and (tgt_artist in parsed_artist or parsed_artist in tgt_artist):
            artist_score = 20

        # 2. Exact track match
        if tgt_track and parsed_track == tgt_track:
            track_score = 30
        elif tgt_track and (tgt_track in parsed_track or parsed_track in tgt_track):
            track_score = 15

        # 3. Album match (heuristic)
        if tgt_track and parsed_album == tgt_track:
            album_score = 10

        # 4. Metadata confidence from Beets
        if beets_confidence:
            beets_score = 20

        # 5. Lossless formats (flac, alac, wav, ape, aiff)
        lossless_exts = {"flac", "alac", "wav", "ape", "aiff"}
        if ext in lossless_exts:
            quality_score = 15

        # 6. Higher bitrate
        if ext in lossless_exts:
            bitrate_score = 10
        elif ext == "mp3" and bitrate >= 320:
            bitrate_score = 10
        elif bitrate >= 192:
            bitrate_score = 5

        # 7. Better filename quality (fully parsed, no "Unknown")
        if parsed_artist != "unknown" and parsed_track != "unknown":
            filename_score = 5

        total_score = artist_score + track_score + album_score + beets_score + quality_score + bitrate_score + filename_score
        final_score = min(max(total_score, 0), 100)

        return {
            "artist_score": artist_score,
            "track_score": track_score,
            "album_score": album_score,
            "beets_score": beets_score,
            "quality_score": quality_score,
            "bitrate_score": bitrate_score,
            "filename_score": filename_score,
            "final_score": final_score
        }

    # Contract implementation methods
    def generate_queries(self, query: SearchQuery) -> List[str]:
        return self.generate_queries_progressive(query.artist, query.track)

    def score_result(self, result: SlskdResult, query: SearchQuery) -> Dict[str, Any]:
        return self.score_candidate(result, query, beets_confidence=False)
