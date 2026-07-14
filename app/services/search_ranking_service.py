import logging
from typing import List, Dict, Any, Optional
from app.services.filename_parser import parse_filename

logger = logging.getLogger("track_portal.search_ranking")

class SearchRankingService:
    @staticmethod
    def generate_queries(artist: str, track: str, album: Optional[str] = None) -> List[str]:
        """
        Generates alternative optimized slskd search queries.
        """
        clean_artist = artist.strip().strip("'\"").strip()
        clean_track = track.strip().strip("'\"").strip()
        clean_album = album.strip().strip("'\"").strip() if album else ""

        queries = []
        # 1. Main query: "Artist Track"
        queries.append(f"{clean_artist} {clean_track}")

        # 2. Alternative double-quoted query: '"Artist" "Track"'
        queries.append(f'"{clean_artist}" "{clean_track}"')

        # 3. If album is provided, "Artist Album Track"
        if clean_album:
            queries.append(f"{clean_artist} {clean_album} {clean_track}")

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
        Scores a single slskd search result from 0 to 100 based on metadata quality and criteria.
        """
        filename = item.get("filename", "")
        parsed = parse_filename(filename)

        # Retrieve parsed/slskd values
        parsed_artist = (parsed.get("artist") or item.get("artist") or "Unknown").lower().strip()
        parsed_track = (parsed.get("track") or item.get("track") or "Unknown").lower().strip()
        parsed_album = (parsed.get("album") or item.get("album") or "").lower().strip()

        tgt_artist = target_artist.lower().strip()
        tgt_track = target_track.lower().strip()
        tgt_album = target_album.lower().strip() if target_album else ""

        # 1. Artist Match (Max 30 points)
        artist_score = 0
        if parsed_artist == tgt_artist:
            artist_score = 30
        elif tgt_artist in parsed_artist or parsed_artist in tgt_artist:
            artist_score = 15

        # 2. Track Match (Max 30 points)
        track_score = 0
        if parsed_track == tgt_track:
            track_score = 30
        elif tgt_track in parsed_track or parsed_track in tgt_track:
            track_score = 15

        # 3. Album Match (Max 10 points)
        album_score = 0
        if tgt_album:
            if parsed_album == tgt_album:
                album_score = 10
            elif tgt_album in parsed_album or parsed_album in tgt_album:
                album_score = 5

        # 4. Codec/Lossless Quality (Max 15 points)
        codec_score = 0
        fmt = item.get("format", "").lower()
        if fmt in ["flac", "alac", "wav", "ape", "aiff"]:
            codec_score = 15
        elif fmt in ["m4a", "aac"]:
            codec_score = 10
        elif fmt == "mp3":
            codec_score = 8
        else:
            codec_score = 5

        # 5. Bitrate Quality (Max 10 points)
        bitrate_score = 0
        bitrate = item.get("bitrate", 0) or 0
        if bitrate >= 1000:
            bitrate_score = 10
        elif bitrate >= 320:
            bitrate_score = 8
        elif bitrate >= 256:
            bitrate_score = 6
        elif bitrate >= 192:
            bitrate_score = 4
        elif bitrate > 0:
            bitrate_score = 2
        else:
            # Fallback based on codec if bitrate is unknown/0
            if fmt in ["flac", "alac", "wav"]:
                bitrate_score = 10
            elif fmt in ["m4a", "aac"]:
                bitrate_score = 6
            elif fmt == "mp3":
                bitrate_score = 4

        # 6. Sample Rate Quality (Max 5 points)
        sample_rate_score = 0
        sample_rate = item.get("sample_rate", 0) or 0
        if sample_rate >= 96000:
            sample_rate_score = 5
        elif sample_rate >= 48000:
            sample_rate_score = 4
        elif sample_rate >= 44100:
            sample_rate_score = 3
        elif sample_rate > 0:
            sample_rate_score = 2
        else:
            if fmt in ["flac", "alac", "wav"]:
                sample_rate_score = 3
            else:
                sample_rate_score = 2

        # 7. File Size (Max 5 points)
        size_score = 5
        size_bytes = item.get("size", 0) or 0
        if size_bytes <= 1024 * 1024:  # <= 1MB is highly likely a stub or fake
            size_score = 0

        total_score = artist_score + track_score + album_score + codec_score + bitrate_score + sample_rate_score + size_score
        return min(max(total_score, 0), 100)
