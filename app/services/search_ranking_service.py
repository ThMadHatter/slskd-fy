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
            "final_score": final_score
        }

    # Contract implementation methods
    def generate_queries(self, query: SearchQuery) -> List[str]:
        return self.generate_queries_progressive(query.artist, query.track)

    def score_result(self, result: SlskdResult, query: SearchQuery) -> Dict[str, Any]:
        return self.score_candidate(result, query, beets_confidence=False)
