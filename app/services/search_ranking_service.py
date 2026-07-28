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
        [HARD REJECTION] Immediately discards non-song result types (e.g. sample packs, stems, etc.).
        """
        filename_lower = filename.lower()

        # 1. Non-audio extension rejection
        if ext not in ["mp3", "flac", "wav", "m4a", "ogg", "alac", "wma", "aac", "aiff", "ape"]:
            return True

        # 2. Hard Rejection of specific non-song categories
        hard_reject_words = [
            "samplepack", "samplepacks", "stems", "multitracks", "drumkits",
            "loop packs", "looppack", "looppacks", "loop pack", "drumkit", "drum kit",
            "producer packs", "producerpack", "producerpacks", "producer pack"
        ]
        for word in hard_reject_words:
            if word in filename_lower:
                return True

        # 3. Check JUNK patterns
        for pattern in JUNK_FILENAME_PATTERNS:
            if re.search(pattern, filename_lower):
                return True

        # 4. Obviously malformed / blob names
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
        Scores a candidate result based on exact matching, folder structures,
        lossless files, bitrates, and a negative scoring penalty engine.
        """
        filename = result.filename
        filename_lower = filename.lower()
        ext = result.format.lower().strip(".")
        size = result.size
        bitrate = result.bitrate or 0

        # Use enriched values on SlskdResult if present, else parse filename
        parsed_artist = (result.parsed_artist or parse_filename(filename).get("artist") or "Unknown").lower().strip()
        parsed_track = (result.parsed_track or parse_filename(filename).get("track") or "Unknown").lower().strip()
        parsed_album = (result.parsed_album or parse_filename(filename).get("album") or "").lower().strip()

        tgt_artist = query.artist.lower().strip()
        tgt_track = query.track.lower().strip()

        # --- Positive Scoring Elements ---
        artist_score = 0
        track_score = 0
        artist_folder_bonus = 0
        album_folder_bonus = 0
        flac_bonus = 0
        lossless_bonus = 0
        bitrate_bonus = 0
        clean_filename_bonus = 0

        # 1. Exact artist match: +40
        if tgt_artist and parsed_artist == tgt_artist:
            artist_score = 40

        # 2. Exact track match: +30
        if tgt_track and parsed_track == tgt_track:
            track_score = 30

        # Folder hierarchy scanning
        path_lower = filename_lower.replace("\\", "/")
        path_parts = [p.strip() for p in path_lower.split("/") if p.strip()]

        # 3. Artist found in folder hierarchy: +10
        artist_in_folders = False
        if len(path_parts) > 1:
            for folder in path_parts[:-1]:
                if tgt_artist in folder:
                    artist_in_folders = True
                    break
        if artist_in_folders:
            artist_folder_bonus = 10

        # 4. Album found in folder hierarchy: +10
        album_in_folders = False
        if len(path_parts) > 1:
            for folder in path_parts[:-1]:
                if tgt_track in folder:
                    album_in_folders = True
                    break
        if album_in_folders:
            album_folder_bonus = 10

        # 5. FLAC bonus: +15
        if ext == "flac":
            flac_bonus = 15

        # 6. Lossless bonus: +15
        lossless_exts = {"flac", "alac", "wav", "ape", "aiff"}
        if ext in lossless_exts:
            lossless_bonus = 15

        # 7. High bitrate MP3: +10
        if ext == "mp3" and bitrate >= 320:
            bitrate_bonus = 10

        # 8. Clean filename structure: +5 (fully parsed, no "Unknown")
        if parsed_artist != "unknown" and parsed_track != "unknown" and "unknown" not in filename_lower:
            clean_filename_bonus = 5

        # --- Negative Penalty Stage ---
        remix_penalty = 0
        mashup_penalty = 0
        bootleg_penalty = 0
        dj_edit_penalty = 0
        acapella_penalty = 0
        instrumental_penalty = 0
        sample_pack_penalty = 0
        stems_penalty = 0

        # Remix Penalty: -20
        remix_words = ["remix", "rework", "vip mix", "extended mix"]
        if any(w in filename_lower for w in remix_words):
            remix_penalty = 20

        # Mashup Penalty: -25
        if "mashup" in filename_lower:
            mashup_penalty = 25

        # Bootleg Penalty: -25
        if "bootleg" in filename_lower:
            bootleg_penalty = 25

        # DJ Edit Penalty: -30
        dj_words = [
            "edit", "clean edit", "dirty edit", "intro", "outro",
            "transition", "transition edit", "quick hit", "radio edit", "dj tool", "dj tools"
        ]
        if any(w in filename_lower for w in dj_words):
            dj_edit_penalty = 30

        # Acapella Penalty: -50
        acapella_words = ["acapella", "acapellas"]
        if any(w in filename_lower for w in acapella_words):
            acapella_penalty = 50

        # Instrumental Penalty: -50
        if "instrumental" in filename_lower:
            instrumental_penalty = 50

        # Sample Pack Penalty: -100
        if "samplepack" in filename_lower or "samplepacks" in filename_lower:
            sample_pack_penalty = 100

        # Stems Penalty: -100
        if "stems" in filename_lower or "stem" in filename_lower:
            stems_penalty = 100

        # Converge Score
        positive_total = (
            artist_score + track_score + artist_folder_bonus + album_folder_bonus +
            flac_bonus + lossless_bonus + bitrate_bonus + clean_filename_bonus
        )
        negative_total = (
            remix_penalty + mashup_penalty + bootleg_penalty + dj_edit_penalty +
            acapella_penalty + instrumental_penalty + sample_pack_penalty + stems_penalty
        )

        final_score = positive_total - negative_total
        final_score = min(max(final_score, 0), 100)

        # Log exact required multiline format
        pos_logs = []
        if artist_score > 0: pos_logs.append(f"Artist Match +{artist_score}")
        if track_score > 0: pos_logs.append(f"Track Match +{track_score}")
        if artist_folder_bonus > 0: pos_logs.append(f"Artist found in folder hierarchy +{artist_folder_bonus}")
        if album_folder_bonus > 0: pos_logs.append(f"Album found in folder hierarchy +{album_folder_bonus}")
        if flac_bonus > 0: pos_logs.append(f"FLAC +{flac_bonus}")
        if lossless_bonus > 0: pos_logs.append(f"Lossless +{lossless_bonus}")
        if bitrate_bonus > 0: pos_logs.append(f"High Bitrate MP3 +{bitrate_bonus}")
        if clean_filename_bonus > 0: pos_logs.append(f"Clean Filename Structure +{clean_filename_bonus}")

        neg_logs = []
        if remix_penalty > 0: neg_logs.append(f"Remix Penalty -{remix_penalty}")
        if mashup_penalty > 0: neg_logs.append(f"Mashup Penalty -{mashup_penalty}")
        if bootleg_penalty > 0: neg_logs.append(f"Bootleg Penalty -{bootleg_penalty}")
        if dj_edit_penalty > 0: neg_logs.append(f"DJ Edit Penalty -{dj_edit_penalty}")
        if acapella_penalty > 0: neg_logs.append(f"Acapella Penalty -{acapella_penalty}")
        if instrumental_penalty > 0: neg_logs.append(f"Instrumental Penalty -{instrumental_penalty}")
        if sample_pack_penalty > 0: neg_logs.append(f"Sample Pack Penalty -{sample_pack_penalty}")
        if stems_penalty > 0: neg_logs.append(f"Stems Penalty -{stems_penalty}")

        log_lines = []
        log_lines.extend(pos_logs)
        log_lines.extend(neg_logs)
        log_lines.append(f"Final Score: {final_score}")
        log_str = "\n".join(log_lines)

        logger.info(f"\n[RANKING DETAIL] Filename: '{filename}'\n{log_str}")

        return {
            "artist_score": artist_score,
            "track_score": track_score,
            "artist_folder_bonus": artist_folder_bonus,
            "album_folder_bonus": album_folder_bonus,
            "flac_bonus": flac_bonus,
            "lossless_bonus": lossless_bonus,
            "bitrate_bonus": bitrate_bonus,
            "clean_filename_bonus": clean_filename_bonus,
            "remix_penalty": remix_penalty,
            "mashup_penalty": mashup_penalty,
            "bootleg_penalty": bootleg_penalty,
            "dj_edit_penalty": dj_edit_penalty,
            "acapella_penalty": acapella_penalty,
            "instrumental_penalty": instrumental_penalty,
            "final_score": final_score,
            "score_reasons": log_str
        }

    # Contract implementation methods
    @classmethod
    def generate_queries(cls, artist_or_query: Union[str, SearchQuery], track: Optional[str] = None, mode: Optional[str] = "A") -> List[str]:
        if isinstance(artist_or_query, SearchQuery):
            return cls.generate_queries(artist_or_query.artist, artist_or_query.track, mode=artist_or_query.mode)

        # If it's called with artist string and track string
        if mode == "B":
            # Mode B (Quotes)
            clean_artist = artist_or_query.replace('"', '').strip() if artist_or_query else ""
            clean_track = track.replace('"', '').strip() if track else ""
            return [f'"{clean_artist}" "{clean_track}"']
        elif mode == "C":
            # Mode C (Prefixes)
            clean_artist = artist_or_query.replace('"', '').strip() if artist_or_query else ""
            clean_track = track.replace('"', '').strip() if track else ""
            return [f"artist:{clean_artist} track:{clean_track}"]
        else:
            # Mode A (Default)
            return cls.generate_queries_progressive(artist_or_query, track or "")

    def score_result(
        self,
        result: Union[Dict[str, Any], SlskdResult],
        *args,
        target_artist: Optional[str] = None,
        target_track: Optional[str] = None,
        target_album: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Backward and Contract-compatible score_result method.
        """
        # Parse inputs
        if isinstance(result, dict):
            filename = result["filename"]
            format_ext = result["format"]
            size = result.get("size", 0)
            bitrate = result.get("bitrate", 0)
            sample_rate = result.get("sample_rate", 0)
            username = result.get("username", "peer")
            queue_length = result.get("queue_length", 0)
        else:
            filename = result.filename
            format_ext = result.format
            size = result.size
            bitrate = result.bitrate or 0
            sample_rate = result.sample_rate or 0
            username = result.username
            queue_length = result.queue_length

        # Parse target artist/track/album
        if args and isinstance(args[0], SearchQuery):
            query = args[0]
            tgt_artist = query.artist
            tgt_track = query.track
            tgt_album = query.album or ""
        else:
            tgt_artist = target_artist
            tgt_track = target_track
            tgt_album = target_album or ""

            if args:
                if len(args) > 0 and not tgt_artist:
                    tgt_artist = args[0]
                if len(args) > 1 and not tgt_track:
                    tgt_track = args[1]
                if len(args) > 2 and not tgt_album:
                    tgt_album = args[2]

        tgt_artist = (tgt_artist or "").lower().strip()
        tgt_track = (tgt_track or "").lower().strip()
        tgt_album = (tgt_album or "").lower().strip()

        filename_lower = filename.lower()
        ext = format_ext.lower().strip(".")

        # Compute artist match score and classification
        artist_score = 0
        classification = "NO_MATCH"

        parsed_info = parse_filename(filename)
        parsed_artist = (parsed_info.get("artist") or "").lower().strip()
        parsed_track = (parsed_info.get("track") or "").lower().strip()

        if tgt_artist:
            # Word sharing partial match
            tgt_words = [w for w in tgt_artist.split() if len(w) >= 3]
            parsed_words = [w for w in parsed_artist.split() if len(w) >= 3]
            shared_words = set(tgt_words).intersection(set(parsed_words))

            if parsed_artist == tgt_artist:
                artist_score = 50
                classification = "PRIMARY_ARTIST_MATCH"
            elif f"feat. {tgt_artist}" in filename_lower or f"featuring {tgt_artist}" in filename_lower or f"ft. {tgt_artist}" in filename_lower:
                artist_score = 35
                classification = "FEATURED_ARTIST_MATCH"
            elif len(shared_words) > 0 or tgt_artist in parsed_artist or parsed_artist in tgt_artist:
                artist_score = 15
                classification = "PARTIAL_MATCH"
            elif tgt_artist in filename_lower:
                artist_score = 15
                classification = "PARTIAL_MATCH"

        track_score = 0
        if tgt_track:
            if parsed_track == tgt_track or tgt_track in filename_lower:
                track_score = 30

        album_score = 0
        if tgt_album and tgt_album in filename_lower:
            album_score = 10

        # Codec / format bonus
        format_bonus = 0
        if ext == "flac":
            format_bonus = 20
        elif ext == "mp3" and bitrate >= 320:
            format_bonus = 10

        # Size bonus
        size_bonus = 0
        if size <= 1024 * 1024: # <= 1MB
            size_bonus = 0
        elif size > 10 * 1024 * 1024: # > 10MB
            size_bonus = 5
        else:
            size_bonus = 2

        final_score = artist_score + track_score + album_score + format_bonus + size_bonus
        final_score = min(max(final_score, 0), 100)

        return {
            "artist_score": artist_score,
            "track_score": track_score,
            "album_score": album_score,
            "format_bonus": format_bonus,
            "size_bonus": size_bonus,
            "final_score": final_score,
            "classification": classification
        }
