import os
import uuid
import hashlib
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("track_portal.beets_collector")


class ConflictCollector:
    """
    Intercepts ambiguous, sub-threshold, or skipped Beets import tasks and converts
    them into JSON-safe Data Transfer Objects (DTOs) with stable UUIDs and deterministic fingerprints.
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
        Safely extracts metadata, candidates, and differences from a Beets ImportTask or
        file path into a pure JSON-serializable dictionary.
        """
        conflict_id = str(uuid.uuid4())

        # Determine item_type (album vs singleton)
        item_type = "singleton" if getattr(task, "is_singleton", False) else "album"

        # Safe extraction of current path and tags
        downloaded_path = ""
        if hasattr(task, "to_import_path"):
            downloaded_path = str(task.to_import_path())
        elif hasattr(task, "path"):
            downloaded_path = str(task.path)
        elif hasattr(task, "paths") and task.paths:
            downloaded_path = str(task.paths[0])
        else:
            downloaded_path = "Unknown Path"

        artist = "Unknown Artist"
        track = "Unknown Track"
        album = "Unknown Album"

        # Extract tags from task items
        items = getattr(task, "items", []) or ([task.item] if hasattr(task, "item") and task.item else [])
        if items and len(items) > 0:
            first_item = items[0]
            artist = str(getattr(first_item, "artist", "") or getattr(first_item, "albumartist", "") or artist)
            track = str(getattr(first_item, "title", "") or track)
            album = str(getattr(first_item, "album", "") or album)
        else:
            if hasattr(task, "cur_artist") and task.cur_artist:
                artist = str(task.cur_artist)
            if hasattr(task, "cur_album") and task.cur_album:
                album = str(task.cur_album)
            if hasattr(task, "cur_track") and task.cur_track:
                track = str(task.cur_track)

            # Fallback filename parsing if track or artist is unknown
            if downloaded_path and (artist == "Unknown Artist" or track == "Unknown Track"):
                try:
                    from app.services.filename_parser import parse_filename
                    parsed = parse_filename(downloaded_path)
                    if parsed.get("artist") and parsed["artist"] != "Unknown":
                        artist = parsed["artist"]
                    if parsed.get("track") and parsed["track"] != "Unknown":
                        track = parsed["track"]
                    if parsed.get("album") and parsed["album"] != "Unknown Album":
                        album = parsed["album"]
                except Exception:
                    pass

        fingerprint = cls.calculate_fingerprint(downloaded_path, artist, track)

        # Candidates extraction
        candidates_list: List[Dict[str, Any]] = []
        raw_candidates = getattr(task, "candidates", []) or []

        best_confidence = 50
        recommendation_text = "Multiple candidate matches found with sub-threshold confidence"

        for idx, cand in enumerate(raw_candidates[:10]):
            cand_id = getattr(cand, "id", None) or getattr(cand, "album_id", None) or f"cand_{idx+1}"
            cand_artist = str(getattr(cand, "artist", "") or getattr(cand, "albumartist", "") or artist)
            cand_title = str(getattr(cand, "album", "") or getattr(cand, "title", "") or track)
            cand_year = int(getattr(cand, "year", 0) or 0)
            cand_mbid = str(getattr(cand, "album_id", "") or getattr(cand, "track_id", "") or "")

            # Beets distance calculation -> confidence percentage
            distance = getattr(cand, "distance", None)
            confidence = 75
            if distance is not None:
                try:
                    # Distance is 0.0 (exact match) to 1.0 (no match)
                    dist_float = float(distance)
                    confidence = max(0, min(100, int((1.0 - dist_float) * 100)))
                except Exception:
                    pass

            if idx == 0:
                best_confidence = confidence
                recommendation_text = f"Top suggested candidate: '{cand_artist} - {cand_title}' ({confidence}% confidence)"

            candidates_list.append(
                {
                    "id": str(cand_id),
                    "artist": cand_artist,
                    "title": cand_title,
                    "year": cand_year,
                    "format": "FLAC/MP3",
                    "track_count": len(items) if items else 1,
                    "confidence": confidence,
                    "mbid": cand_mbid,
                    "source": "MusicBrainz Autotag",
                    "url": f"https://musicbrainz.org/release/{cand_mbid}" if cand_mbid else "",
                }
            )

        # Fallback candidate if no candidate array was found
        if not candidates_list:
            candidates_list.append(
                {
                    "id": f"cand_fallback_1",
                    "artist": artist,
                    "title": album if album != "Unknown Album" else track,
                    "year": 0,
                    "format": "FLAC/MP3",
                    "track_count": len(items) if items else 1,
                    "confidence": 60,
                    "source": "Disk File Analysis",
                }
            )

        # Differences calculation between current local tags and top candidate
        differences = {}
        if candidates_list:
            top_cand = candidates_list[0]
            if artist != top_cand["artist"]:
                differences["artist"] = {"current": artist, "candidate": top_cand["artist"]}
            if album != top_cand["title"]:
                differences["album"] = {"current": album, "candidate": top_cand["title"]}

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
            "status": "open",
            "candidates": candidates_list,
            "differences": differences,
            "recommendation_text": recommendation_text,
            "retry_count": 0,
        }
