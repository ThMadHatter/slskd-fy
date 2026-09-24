import os
import re
import uuid
import hashlib
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("track_portal.beets_collector")


def clean_query_hint(raw_hint: str, is_artist: bool = False, artist: str = "") -> str:
    """
    Sanitizes search query hints by extracting file basenames, stripping extensions,
    leading track numbers, leading year prefixes, and bracketed format tags,
    while strictly preserving full artist names (e.g. 'Brunori Sas').
    Does NOT mutate raw tags on disk.
    """
    if not raw_hint:
        return ""

    text = str(raw_hint)

    # 1. If raw_hint is a file or folder path, extract basename
    if "/" in text or "\\" in text:
        text = os.path.basename(text)

    # 2. Strip common audio/archive file extensions
    text = re.sub(r'\.(flac|mp3|m4a|wav|aac|ogg|zip|rar|7z)$', '', text, flags=re.IGNORECASE)

    # 3. Strip leading track numbers e.g. '02 - ', '01. ' (unless cleaning an artist name)
    if not is_artist:
        text = re.sub(r'^\s*\d{1,3}\s*[-._\s]\s*', '', text)

    # 4. Strip leading year prefix like '2025 - ' or '2024-'
    text = re.sub(r'^\s*\b(19|20)\d{2}\b\s*[-–—]\s*', '', text)

    # 5. Remove bracketed technical descriptors e.g. '[Flac 24-44]', '[320k]', '[WEB]'
    text = re.sub(r'\[[^\]]*\]', '', text)

    # 6. Remove standalone year patterns in parentheses e.g. '(2025)'
    text = re.sub(r'\(\s*(19|20)\d{2}\s*\)', '', text)

    # 7. Strip leading artist prefix if artist provided e.g. 'Brunori Sas - L'albero delle noci' -> 'L'albero delle noci'
    if not is_artist and artist:
        clean_art = re.escape(artist.strip())
        text = re.sub(rf'^{clean_art}\s*[-–—]\s*', '', text, flags=re.IGNORECASE)

    # 8. Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text or str(raw_hint)


class ConflictCollector:
    """
    Intercepts ambiguous, sub-threshold, or skipped Beets import tasks and converts
    them into JSON-safe Data Transfer Objects (DTOs) with metadata provenance,
    rich MusicBrainz candidate info, and exact Beets distance breakdowns.
    """

    @staticmethod
    def calculate_fingerprint(source_path: str, artist: str = "", track: str = "") -> str:
        """
        Calculates a deterministic sha256 fingerprint hash for duplicate detection based on
        normalized source path and metadata content.
        """
        norm_path = os.path.normpath(str(source_path)).lower()
        key_str = f"{norm_path}:{artist.lower().strip()}:{track.lower().strip()}"
        return hashlib.sha256(key_str.encode("utf-8")).hexdigest()

    @classmethod
    def extract_conflict_dto(
        cls, task: Any, session: Any = None, job_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Safely extracts metadata provenance, rich external candidates, and differences
        from a Beets ImportTask or file path into a pure JSON-serializable dictionary.
        """
        conflict_id = str(uuid.uuid4())

        # Determine item_type (album vs singleton)
        item_type = "singleton" if getattr(task, "is_singleton", False) else "album"

        # Safe extraction of current path
        downloaded_path = ""
        if hasattr(task, "to_import_path"):
            downloaded_path = str(task.to_import_path())
        elif hasattr(task, "path"):
            downloaded_path = str(task.path)
        elif hasattr(task, "paths") and task.paths:
            downloaded_path = str(task.paths[0])
        else:
            downloaded_path = "Unknown Path"

        # Initialize Provenance Tracking
        embedded_tags = {"artist": None, "track": None, "album": None, "year": None}
        filename_inferred = {"artist": None, "track": None, "album": None}
        parent_dir_inferred = {"artist": None, "album": None, "year": None}
        technical_props = {"format": "FLAC", "bitrate": None, "sample_rate": None, "channels": None}

        items = getattr(task, "items", []) or ([task.item] if hasattr(task, "item") and task.item else [])
        if items and len(items) > 0:
            first_item = items[0]
            embedded_tags["artist"] = getattr(first_item, "artist", None) or getattr(first_item, "albumartist", None)
            embedded_tags["track"] = getattr(first_item, "title", None)
            embedded_tags["album"] = getattr(first_item, "album", None)
            embedded_tags["year"] = getattr(first_item, "year", None)

            technical_props["format"] = getattr(first_item, "format", "FLAC") or "FLAC"
            technical_props["bitrate"] = getattr(first_item, "bitrate", None)
            technical_props["sample_rate"] = getattr(first_item, "samplerate", None)

        # Inferred metadata from filename & parent folder
        if downloaded_path:
            try:
                from app.services.filename_parser import parse_filename
                parsed = parse_filename(downloaded_path)
                filename_inferred["artist"] = parsed.get("artist")
                filename_inferred["track"] = parsed.get("track")
                filename_inferred["album"] = parsed.get("album")

                parent_dir = os.path.basename(os.path.dirname(downloaded_path))
                if parent_dir:
                    parent_dir_inferred["album"] = parent_dir
            except Exception:
                pass

        # Final active local tags (prioritizing valid embedded tags)
        artist = embedded_tags["artist"] or filename_inferred["artist"] or "Unknown Artist"
        track = embedded_tags["track"] or filename_inferred["track"] or "Unknown Track"
        raw_album = embedded_tags["album"] or filename_inferred["album"] or "Unknown Album"

        # Sanitize query hints to remove uploader tags, brackets, and year noise for candidate searching
        clean_artist_hint = clean_query_hint(artist)
        clean_track_hint = clean_query_hint(track)
        clean_album_hint = clean_query_hint(raw_album) if raw_album != "Unknown Album" else ""

        album = clean_album_hint if clean_album_hint else raw_album

        # If candidates list is empty or lacks candidates, execute a fallback search via Beets autotag/metadata plugins
        raw_candidates = getattr(task, "candidates", None)
        if raw_candidates is None:
            try:
                search_ids = [session.search_ids] if hasattr(session, "search_ids") and session.search_ids else []
                if hasattr(task, "lookup_candidates"):
                    task.lookup_candidates(search_ids=search_ids)
                    raw_candidates = getattr(task, "candidates", []) or []
            except Exception as e:
                logger.warning(f"Error executing task.lookup_candidates(): {e}")
                raw_candidates = []
        else:
            raw_candidates = raw_candidates or []

        fingerprint = cls.calculate_fingerprint(downloaded_path, artist, track)

        # Candidate Extraction from Beets Match Candidates
        candidates_list: List[Dict[str, Any]] = []
        raw_candidates = getattr(task, "candidates", []) or []

        best_confidence = 0
        raw_distance = None

        for idx, cand in enumerate(raw_candidates[:10]):
            # Extract rich MusicBrainz metadata
            cand_artist = str(getattr(cand, "artist", "") or getattr(cand, "albumartist", "") or artist)
            cand_title = str(getattr(cand, "album", "") or getattr(cand, "title", "") or track)
            cand_year = int(getattr(cand, "year", 0) or 0)

            release_id = str(getattr(cand, "album_id", "") or getattr(cand, "release_id", "") or getattr(cand, "id", "") or "")
            recording_id = str(getattr(cand, "track_id", "") or getattr(cand, "recording_id", "") or "")
            release_group_id = str(getattr(cand, "releasegroup_id", "") or getattr(cand, "release_group_id", "") or "")

            country = str(getattr(cand, "country", "") or "US")
            label = str(getattr(cand, "label", "") or "")
            catalog_num = str(getattr(cand, "catalognum", "") or "")
            media = str(getattr(cand, "media", "") or "Digital Media")

            # Beets distance calculation -> UI similarity score
            distance_obj = getattr(cand, "distance", None)
            cand_dist_val = 0.5
            dist_penalties = {}

            if distance_obj is not None:
                try:
                    cand_dist_val = float(distance_obj)
                    if hasattr(distance_obj, "penalties"):
                        dist_penalties = {p: float(v) for p, v in distance_obj.penalties().items()}
                except Exception:
                    pass

            # Explicit UI similarity score calculation formula: (1.0 - raw_distance) * 100
            ui_similarity_score = max(0, min(100, int((1.0 - cand_dist_val) * 100)))

            if idx == 0:
                best_confidence = ui_similarity_score
                raw_distance = cand_dist_val

            cand_mbid = release_id if item_type == "album" else recording_id
            cand_url = ""
            if release_id:
                cand_url = f"https://musicbrainz.org/release/{release_id}"
            elif recording_id:
                cand_url = f"https://musicbrainz.org/recording/{recording_id}"

            candidates_list.append({
                "id": str(getattr(cand, "id", None) or cand_mbid or f"cand_{idx+1}"),
                "source": "MusicBrainz",
                "candidate_type": item_type,
                "artist": cand_artist,
                "title": cand_title,
                "year": cand_year,
                "release_id": release_id,
                "recording_id": recording_id,
                "release_group_id": release_group_id,
                "country": country,
                "label": label,
                "catalog_num": catalog_num,
                "media": media,
                "format": technical_props["format"],
                "track_count": len(getattr(cand, "tracks", [])) or (len(items) if items else 1),
                "ui_similarity_score": ui_similarity_score,
                "raw_distance": cand_dist_val,
                "penalties": dist_penalties,
                "mbid": cand_mbid,
                "url": cand_url,
            })

        # Dynamic Assessment Text Generation based on true candidate counts and confidence
        candidate_count = len(candidates_list)
        if candidate_count == 0:
            recommendation_text = "No external MusicBrainz match found for this release."
        elif candidate_count == 1:
            top = candidates_list[0]
            if top["ui_similarity_score"] >= 85:
                recommendation_text = f"Strong match candidate found: '{top['artist']} — {top['title']}' ({top['ui_similarity_score']}% match)."
            else:
                recommendation_text = f"One low-confidence match candidate found: '{top['artist']} — {top['title']}' ({top['ui_similarity_score']}% match)."
        else:
            top = candidates_list[0]
            recommendation_text = f"Ambiguous candidates found ({candidate_count} matches). Top match: '{top['artist']} — {top['title']}' ({top['ui_similarity_score']}% match)."

        # Field Differences Calculation
        differences = {}
        if candidates_list:
            top_cand = candidates_list[0]
            if artist.lower() != top_cand["artist"].lower():
                differences["artist"] = {"current": artist, "candidate": top_cand["artist"]}
            if album.lower() != top_cand["title"].lower():
                differences["album"] = {"current": album, "candidate": top_cand["title"]}

        provenance_dto = {
            "embedded_tags": embedded_tags,
            "filename_inferred": filename_inferred,
            "parent_dir_inferred": parent_dir_inferred,
            "technical_props": technical_props,
            "clean_album_hint": clean_album_hint,
        }

        return {
            "conflict_id": conflict_id,
            "fingerprint": fingerprint,
            "job_id": job_id,
            "item_type": item_type,
            "artist": artist,
            "track": track,
            "album": album,
            "downloaded_path": downloaded_path,
            "confidence_score": best_confidence,
            "raw_distance": raw_distance,
            "status": "open",
            "provenance": provenance_dto,
            "candidates": candidates_list,
            "differences": differences,
            "recommendation_text": recommendation_text,
            "retry_count": 0,
        }
