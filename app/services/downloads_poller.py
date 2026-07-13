import os
import shutil
import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.config import settings
from app.models import DownloadHistory, Wishlist
from app.services.slskd import SlskdClient
from app.services.duplicate_detector import calculate_file_hash

logger = logging.getLogger("track_portal.poller")

def find_file_recursively(base_dir: str, target_filename_part: str) -> Optional[str]:
    """
    Recursively searches for a file in base_dir whose path contains target_filename_part.
    """
    if not os.path.exists(base_dir):
        return None

    normalized_target = target_filename_part.replace("\\", "/").lower()
    target_basename = os.path.basename(normalized_target)

    for root, _, files in os.walk(base_dir):
        for f in files:
            if f.lower() == target_basename:
                return os.path.join(root, f)

    for root, _, files in os.walk(base_dir):
        for f in files:
            if target_basename in f.lower() or f.lower() in target_basename:
                return os.path.join(root, f)

    return None

def clean_empty_directories(base_dir: str):
    """Deletes empty directories left behind by downloads."""
    if not os.path.exists(base_dir):
        return
    for root, dirs, _ in os.walk(base_dir, topdown=False):
        for d in dirs:
            dir_path = os.path.join(root, d)
            try:
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    logger.info(f"Cleaned up empty directory: {dir_path}")
            except Exception as e:
                logger.debug(f"Could not delete directory {dir_path}: {e}")

async def poll_downloads():
    """
    Background polling loop to check slskd, move files, and calculate hashes.
    Completed tracks are set to state 'completed'.
    """
    slskd_client = SlskdClient()

    while True:
        try:
            db = SessionLocal()
            active_downloads = db.query(DownloadHistory).filter(
                DownloadHistory.status == "downloading"
            ).all()

            if active_downloads:
                logger.info(f"Polling status for {len(active_downloads)} active downloads...")
                slskd_downloads = await slskd_client.get_downloads()

                flat_transfers: List[Dict[str, Any]] = []
                if isinstance(slskd_downloads, list):
                    flat_transfers = slskd_downloads
                elif isinstance(slskd_downloads, dict):
                    if "transfers" in slskd_downloads:
                        flat_transfers = slskd_downloads["transfers"]
                    elif "directories" in slskd_downloads:
                        for d in slskd_downloads["directories"]:
                            flat_transfers.extend(d.get("files", []))
                    else:
                        for key, val in slskd_downloads.items():
                            if isinstance(val, list):
                                flat_transfers.extend(val)

                for download in active_downloads:
                    matching_transfer = None
                    target_filename = download.filename.replace("\\", "/").lower()
                    target_basename = os.path.basename(target_filename)

                    for t in flat_transfers:
                        t_filename = t.get("filename", "").replace("\\", "/").lower()
                        t_username = t.get("username", "").lower().strip()

                        if download.source_user.lower().strip() == t_username and \
                           (t_filename.endswith(target_basename) or target_basename in t_filename):
                            matching_transfer = t
                            break

                    if matching_transfer:
                        state = matching_transfer.get("state", "")
                        logger.info(f"Track '{download.track}' has slskd state: {state}")

                        if "succeeded" in state.lower() or state.lower() == "completed":
                            # Use DOWNLOADS_PATH to locate completed track
                            found_file_path = find_file_recursively(settings.DOWNLOADS_PATH, download.filename)

                            if found_file_path and os.path.exists(found_file_path):
                                os.makedirs(settings.SINGLES_PATH, exist_ok=True)
                                dest_file_path = os.path.join(settings.SINGLES_PATH, os.path.basename(found_file_path))

                                try:
                                    logger.info(f"Moving completed single track: {found_file_path} -> {dest_file_path}")
                                    shutil.move(found_file_path, dest_file_path)

                                    # Calculate file hash for duplicate detection
                                    f_hash = calculate_file_hash(dest_file_path)

                                    # Update database state to 'completed'
                                    download.status = "completed"
                                    download.downloaded_at = datetime.utcnow()
                                    download.filename = os.path.basename(dest_file_path)
                                    download.file_hash = f_hash

                                    # Update corresponding wishlist item status
                                    wishlist_item = db.query(Wishlist).filter(
                                        Wishlist.artist == download.artist,
                                        Wishlist.track == download.track,
                                        Wishlist.status != "imported"
                                    ).first()
                                    if wishlist_item:
                                        wishlist_item.status = "downloaded"
                                        wishlist_item.fulfilled_at = datetime.utcnow()

                                    logger.info(f"Track '{download.track}' successfully organized and marked completed.")
                                except Exception as e:
                                    logger.error(f"Failed to move completed file {found_file_path}: {e}")
                            else:
                                logger.warning(f"File {download.filename} completed in slskd, but could not be found under {settings.DOWNLOADS_PATH}")

                        elif any(failed_state in state.lower() for failed_state in ["cancelled", "errored", "rejected", "aborted", "timedout"]):
                            logger.error(f"slskd download failed with state: {state}")
                            download.status = "failed"

                            wishlist_item = db.query(Wishlist).filter(
                                Wishlist.artist == download.artist,
                                Wishlist.track == download.track,
                                Wishlist.status != "imported"
                            ).first()
                            if wishlist_item:
                                wishlist_item.status = "failed"
                    else:
                        # Fallback for finished orphaned files
                        found_file_path = find_file_recursively(settings.DOWNLOADS_PATH, download.filename)
                        if found_file_path and os.path.exists(found_file_path):
                            os.makedirs(settings.SINGLES_PATH, exist_ok=True)
                            dest_file_path = os.path.join(settings.SINGLES_PATH, os.path.basename(found_file_path))
                            try:
                                logger.info(f"Found orphaned completed file on disk: {found_file_path}. Moving to singles.")
                                shutil.move(found_file_path, dest_file_path)
                                f_hash = calculate_file_hash(dest_file_path)

                                download.status = "completed"
                                download.downloaded_at = datetime.utcnow()
                                download.filename = os.path.basename(dest_file_path)
                                download.file_hash = f_hash

                                wishlist_item = db.query(Wishlist).filter(
                                    Wishlist.artist == download.artist,
                                    Wishlist.track == download.track,
                                    Wishlist.status != "imported"
                                ).first()
                                if wishlist_item:
                                    wishlist_item.status = "downloaded"
                                    wishlist_item.fulfilled_at = datetime.utcnow()
                            except Exception as e:
                                logger.error(f"Failed to move orphaned file: {e}")

                db.commit()
                clean_empty_directories(settings.DOWNLOADS_PATH)

            db.close()
        except Exception as e:
            logger.error(f"Error in background polling task: {e}")

        await asyncio.sleep(10)

def start_background_poller():
    loop = asyncio.get_event_loop()
    loop.create_task(poll_downloads())
    logger.info("Background download poller started successfully.")
