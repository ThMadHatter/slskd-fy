import os
import logging
import hashlib
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.config import settings
from app.models import DownloadHistory
from app.services.navidrome import NavidromeClient

logger = logging.getLogger("track_portal.duplicate_detector")

def calculate_file_hash(filepath: str) -> str:
    """Calculates MD5 hash of a file for duplicate detection."""
    hash_md5 = hashlib.md5()
    try:
        if not os.path.exists(filepath):
            return ""
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error(f"Failed to calculate file hash for {filepath}: {e}")
        return ""

async def check_duplicate(
    db: Session,
    artist: str,
    title: str,
    file_hash: Optional[str] = None
) -> Dict[str, Any]:
    """
    Checks if a track is likely a duplicate using:
    1. Navidrome library (via Subsonic API search)
    2. File hash lookup (compared to completed/imported tracks in DownloadHistory)
    3. Artist/title metadata (compared to completed/imported tracks in DownloadHistory)
    4. Local Singles directory check
    """
    is_dup = False
    sources = []

    normalized_artist = artist.lower().strip()
    normalized_title = title.lower().strip()

    # 1. Check Navidrome Library (via Subsonic API)
    try:
        navidrome = NavidromeClient()
        if await navidrome.search_track(artist, title):
            is_dup = True
            sources.append("Navidrome Library")
    except Exception as e:
        logger.error(f"Error checking duplicate in Navidrome: {e}")

    # 2. Check Database File Hash
    if file_hash:
        try:
            hash_match = db.query(DownloadHistory).filter(
                DownloadHistory.file_hash == file_hash,
                DownloadHistory.status.in_(["completed", "tagged", "imported"])
            ).first()
            if hash_match:
                is_dup = True
                sources.append("Download History (Exact File Hash)")
        except Exception as e:
            logger.error(f"Error checking duplicate via file hash: {e}")

    # 3. Check Database Artist / Title Metadata
    try:
        history_match = db.query(DownloadHistory).filter(
            DownloadHistory.status.in_(["completed", "tagged", "imported"])
        ).all()

        for record in history_match:
            rec_artist = record.artist.lower().strip()
            rec_track = record.track.lower().strip()
            if (normalized_artist in rec_artist or rec_artist in normalized_artist) and \
               (normalized_title in rec_track or rec_track in normalized_title):
                is_dup = True
                if "Download History" not in sources:
                    sources.append("Download History (Artist/Title)")
                break
    except Exception as e:
        logger.error(f"Error checking duplicate in download history: {e}")

    # 4. Check Local Singles Directory (/uploads/Singles)
    try:
        singles_dir = settings.SINGLES_PATH
        if os.path.exists(singles_dir):
            for filename in os.listdir(singles_dir):
                file_lower = filename.lower()
                # Check if both artist and title are present in the filename
                if normalized_artist in file_lower and normalized_title in file_lower:
                    is_dup = True
                    sources.append("Local Singles Folder")
                    break
    except Exception as e:
        logger.error(f"Error checking duplicate in local singles folder: {e}")

    warning_msg = ""
    if is_dup:
        warning_msg = f"Already present in library (Detected in: {', '.join(sources)})"

    return {
        "is_duplicate": is_dup,
        "sources": sources,
        "warning_message": warning_msg
    }
