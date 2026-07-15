import logging
from typing import List, Dict, Any, Optional
from app.services.filename_parser import parse_filename

logger = logging.getLogger("track_portal.search_ranking")

class SearchRankingService:
    @staticmethod
    def generate_queries(artist: str, track: str, album: Optional[str] = None) -> List[str]:
        """
        Generates optimized slskd search queries using canonical artist information.
        (Task 4: Search generation must use canonical artist information)
        """
        clean_artist = artist.strip().strip("'\"").strip()
        clean_track = track.strip().strip("'\"").strip()
        clean_album = album.strip().strip("'\"").strip() if album else ""

        # Task 4 & 7: Generating optimized query strings
        # Use canonical artist name in double quotes for exact match on Soulseek
        queries = []
        if clean_artist and clean_track:
            queries.append(f'"{clean_artist}" {clean_track}')
            queries.append(f"{clean_artist} {clean_track}")
        elif clean_artist:
            queries.append(f'"{clean_artist}"')
            queries.append(clean_artist)
        elif clean_track:
            queries.append(clean_track)

        # Unique values preserving order
        seen = set()
        return [q for q in queries if not (q in seen or seen.add(q))]

    @staticmethod
    def score_result(
        item: Dict[str, Any],
        target_artist: str,
        target_track: str,
        target_album: Optional[str] = None
    ) -> int:
        """
        Scores a single slskd search result from 0 to 100 based on Task 2 & Task 4 requirements.
        """
        filename = item.get("filename", "")
        parsed = parse_filename(filename)

        # Retrieve parsed/slskd values
        parsed_artist = (parsed.get("artist") or item.get("artist") or "Unknown").lower().strip()
        parsed_track = (parsed.get("track") or item.get("track") or "Unknown").lower().strip()
        parsed_album = (parsed.get("album") or item.get("album") or "").lower().strip()
        featured_artists = [a.lower().strip() for a in parsed.get("featured_artists", [])]

        tgt_artist = target_artist.lower().strip()
        tgt_track = target_track.lower().strip()
        tgt_album = target_album.lower().strip() if target_album else ""

        # --- Artist Confidence Model (Task 4) ---
        artist_score = 0
        if parsed_artist == tgt_artist:
            artist_score = 50
        elif any(tgt_artist == f for f in featured_artists) or f"feat. {tgt_artist}" in parsed_track or f"feat {tgt_artist}" in parsed_track:
            artist_score = 20
        elif tgt_artist in parsed_artist or parsed_artist in tgt_artist or any(w in parsed_artist for w in tgt_artist.split() if len(w) > 3):
            # Let's ensure non-matches like "Willie Kendrick" vs "Kendrick Lamar" score low!
            # If they both contain the word but they are completely different artists (different words):
            artist_score = 10
        else:
            artist_score = 0

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
        fmt = item.get("format", "").lower()
        bitrate = item.get("bitrate", 0) or 0

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
        size_bytes = item.get("size", 0) or 0
        if size_bytes > 10 * 1024 * 1024:  # > 10MB
            size_score = 5
        elif size_bytes > 1024 * 1024:     # > 1MB
            size_score = 2

        total_score = artist_score + track_score + quality_score + album_score + size_score
        return min(max(total_score, 0), 100)
