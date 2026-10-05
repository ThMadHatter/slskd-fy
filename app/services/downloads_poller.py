import os
import shutil
import logging
import asyncio
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.config import settings
from app.models import DownloadHistory, Wishlist
from app.services.slskd import SlskdClient
from app.services.duplicate_detector import calculate_file_hash

logger = logging.getLogger("track_portal.poller")

# Memory tracker: {download_id: {"last_bytes": int, "last_progress_time": datetime}} [RSL-002]
STALL_TRACKER: Dict[int, Dict[str, Any]] = {}
GHOST_PEER_TIMEOUT_SEC = int(os.getenv("GHOST_PEER_TIMEOUT_SEC", "300"))

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

async def import_with_beets(src_path: str, target_dir: str, download_record: Optional[DownloadHistory] = None) -> Optional[str]:
    """
    Imports downloaded audio files using Beets engine.
    If Beets autotags and imports the files into target_dir (/music), returns the destination file path.
    If Beets skips import because user intervention is required, transitions the download status to 'review_required',
    preserves the BeetsReviewItem conflict metadata, leaves source files untouched in /downloads, and returns None.
    """
    if not os.path.exists(src_path):
        return None

    # If src_path is inside a subfolder under DOWNLOADS_PATH, import the parent directory to trigger album-level autotagging
    parent_dir = os.path.dirname(src_path)
    is_in_subfolder = (
        os.path.normpath(parent_dir) != os.path.normpath(settings.DOWNLOADS_PATH)
        and os.path.isdir(parent_dir)
    )
    target_import_path = parent_dir if is_in_subfolder else src_path

    # Check if this file path or download is already pending review or skipped/ignored in BeetsReviewItem
    try:
        db_check = SessionLocal()
        from app.models import BeetsReviewItem
        from sqlalchemy import or_

        filter_conds = [
            BeetsReviewItem.downloaded_path == src_path,
            BeetsReviewItem.downloaded_path == target_import_path,
        ]
        if download_record and download_record.id:
            filter_conds.append(BeetsReviewItem.download_id == download_record.id)

        existing_item = db_check.query(BeetsReviewItem).filter(
            or_(*filter_conds),
            BeetsReviewItem.status.in_(["review_required", "open", "skipped", "ignored"])
        ).first()

        if existing_item:
            logger.info(f"Skipping repeated Beets import attempt for file already in ReviewQueue: '{src_path}'")
            if download_record and download_record.status == "downloading":
                download_record.status = "review_required"
                db_check.merge(download_record)
                db_check.commit()
            db_check.close()
            return None
        db_check.close()
    except Exception as e:
        logger.debug(f"Error checking existing BeetsReviewItem for '{src_path}': {e}")

    logger.info(f"Triggering Beets import for downloaded file/directory: '{target_import_path}'")
    logger.debug(f"[AUDIT_POLLER] BEETS IMPORT START - src={src_path!r}, target_import_path={target_import_path!r}")

    try:
        os.makedirs("/config/beets", exist_ok=True)
        os.makedirs(target_dir, exist_ok=True)
    except Exception as e:
        logger.debug(f"Could not create directories: {e}")

    from app.config import resolve_beets_config_path
    config_path = resolve_beets_config_path()

    import uuid
    from app.services.beets_worker import run_beets_import_task
    job_id = str(uuid.uuid4())
    download_id_val = download_record.id if download_record else None

    try:
        logger.info(f"Executing Beets import task job_id '{job_id}' for path: '{target_import_path}'")
        await asyncio.to_thread(
            run_beets_import_task,
            job_id,
            target_import_path,
            config_path,
            None,
            None,
            None,
            download_id_val,
        )
    except Exception as e:
        logger.error(f"Error executing Beets import task for '{target_import_path}': {e}")

    # Check if Beets moved the file to target_dir (/music)
    filename = os.path.basename(src_path)
    found_in_target = find_file_recursively(target_dir, filename)
    if found_in_target and os.path.exists(found_in_target):
        logger.info(f"Beets import succeeded and file was moved to target: '{found_in_target}'")
        return found_in_target

    # If Beets skipped import (0 files imported), transition to 'review_required' and leave source path untouched
    logger.info(f"Beets import for '{target_import_path}' completed without moving files; transitioning download record to review_required state.")
    if download_record:
        try:
            db_up = SessionLocal()
            rec = db_up.query(DownloadHistory).filter(DownloadHistory.id == download_record.id).first()
            if rec:
                rec.status = "review_required"
                db_up.commit()
            db_up.close()
        except Exception as e:
            logger.error(f"Error updating DownloadHistory status to review_required: {e}")

    return None

async def _handle_stalled_download(download: DownloadHistory, db: Session):
    """
    [RSL-002] Autonomously cancels a stalled download and requests the next best choice seamlessly.
    """
    logger.warning(f"Ghost Peer detected! Download for '{download.track}' is stalled (0 bytes or queue not moving). Autonomously cancelling.")
    logger.debug(f"[AUDIT_POLLER] STALLED TRIGGERED! {download.track}")

    slskd_client = SlskdClient()
    try:
        # Fetch active slskd downloads to locate file ID and cancel it
        transfers = await slskd_client.get_downloads()
        flat_transfers = []
        if isinstance(transfers, list):
            flat_transfers = transfers
        elif isinstance(transfers, dict):
            if "transfers" in transfers:
                flat_transfers = transfers["transfers"]
            elif "directories" in transfers:
                for d in transfers["directories"]:
                    flat_transfers.extend(d.get("files", []))

        target_basename = os.path.basename(download.filename.replace("\\", "/")).lower()
        for t in flat_transfers:
            t_filename = t.get("filename", "").replace("\\", "/").lower()
            t_username = t.get("username", "").lower().strip()
            if download.source_user.lower().strip() == t_username and \
               (t_filename.endswith(target_basename) or target_basename in t_filename):
                t_id = t.get("id") or t.get("id_")
                if t_id:
                    await slskd_client.cancel_download(t_username, t_id)
                    logger.info(f"Cancelled stalled download '{t_filename}' in slskd.")
                    break
    except Exception as e:
        logger.error(f"Failed to cancel stalled download in slskd: {e}")

    # Update state to 'stalled'
    download.status = "stalled"
    db.commit()

    # Query next best choice candidate [RSL-002]
    try:
        from app.services.search_ranking_service import SearchRankingService
        from app.contracts.schemas import SearchQuery, SlskdResult

        logger.info(f"Autonomously searching and enqueuing next best choice peer for '{download.track}'")
        search_query = f"{download.artist} {download.track}"
        search_obj = await slskd_client.search(search_query)
        search_id = search_obj.get("id")
        if not search_id:
            return

        # Poll brief responses
        await asyncio.sleep(2.0)
        responses = await slskd_client.get_search_responses(search_id)

        candidates = []
        for resp in responses:
            username = resp.get("username", "")
            # Skip the stalled peer to prevent loop re-attempts
            if username.lower().strip() == download.source_user.lower().strip():
                continue
            for f in resp.get("files", []):
                filename = f.get("filename", "")
                ext = os.path.splitext(filename)[1].lstrip(".").lower()
                size = f.get("size", 0)
                bitrate = f.get("bitRate", 0) or f.get("bitrate", 0) or 0

                if SearchRankingService.should_reject_result(filename, ext):
                    continue

                res_model = SlskdResult(
                    filename=filename,
                    size=size,
                    username=username,
                    format=ext,
                    bitrate=bitrate
                )
                query_model = SearchQuery(artist=download.artist, track=download.track)
                diag = SearchRankingService().score_result(res_model, query_model)
                candidates.append((diag["final_score"], username, filename, size, ext, bitrate))

        # Sort based on ranking quality score
        candidates.sort(key=lambda x: x[0], reverse=True)
        if candidates:
            best_score, next_user, next_file, next_size, next_ext, next_bitrate = candidates[0]
            logger.info(f"Ghost Peer Fallback: Found next candidate score={best_score} from peer '{next_user}'. Enqueuing.")
            success = await slskd_client.enqueue_download(next_user, next_file, next_size)
            if success:
                new_download = DownloadHistory(
                    search_query=download.search_query,
                    artist=download.artist,
                    track=download.track,
                    album=download.album,
                    filename=os.path.basename(next_file),
                    source_user=next_user,
                    format=next_ext,
                    bitrate=next_bitrate,
                    size_bytes=next_size,
                    status="downloading",
                    downloaded_at=datetime.utcnow()
                )
                db.add(new_download)
                db.commit()
                logger.info("Successfully enqueued next best candidate.")
    except Exception as e:
        logger.error(f"Failed to trigger auto-selected peer fallback for stalled download: {e}")

async def poll_downloads():
    """
    Background polling loop to check slskd, move files, and calculate hashes.
    Enforces Ghost Peer download monitoring [RSL-002].
    """
    global STALL_TRACKER
    slskd_client = SlskdClient()

    while True:
        try:
            db = SessionLocal()
            active_downloads = db.query(DownloadHistory).filter(
                DownloadHistory.status == "downloading"
            ).all()
            logger.debug(f"[AUDIT_POLLER] Loop Step: active downloads found count={len(active_downloads)}")

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

            # Unpack files from slskd_downloads for global inspection
            all_slskd_files = []
            for item in flat_transfers:
                username = item.get("username") or ""
                if "directories" in item:
                    for d in item.get("directories", []):
                        for f in d.get("files", []):
                            all_slskd_files.append({"username": username, **f})
                elif "files" in item:
                    for f in item.get("files", []):
                        all_slskd_files.append({"username": username, **f})
                else:
                    all_slskd_files.append(item)

            # 1. Process tracked active_downloads first
            for download in active_downloads:
                matching_transfer = None
                target_filename = download.filename.replace("\\", "/").lower()
                target_basename = os.path.basename(target_filename)

                for t in all_slskd_files:
                    t_filename = t.get("filename", "").replace("\\", "/").lower()
                    t_username = t.get("username", "").lower().strip()

                    if download.source_user.lower().strip() == t_username and \
                       (t_filename.endswith(target_basename) or target_basename in t_filename):
                        matching_transfer = t
                        break

                logger.debug(f"[AUDIT_POLLER] download={download.track}, matching transfer={matching_transfer is not None}")

                if matching_transfer:
                    # [RSL-002] Monitor stalled transfers
                    bytes_transferred = matching_transfer.get("bytes_transferred", 0) or matching_transfer.get("bytesTransferred", 0) or 0
                    now = datetime.utcnow()

                    if download.id not in STALL_TRACKER:
                        STALL_TRACKER[download.id] = {
                            "bytes": bytes_transferred,
                            "time": now
                        }
                    else:
                        tracker = STALL_TRACKER[download.id]
                        if bytes_transferred > tracker["bytes"]:
                            STALL_TRACKER[download.id] = {
                                "bytes": bytes_transferred,
                                "time": now
                            }
                        else:
                            elapsed = (now - tracker["time"]).total_seconds()
                            if elapsed >= GHOST_PEER_TIMEOUT_SEC:
                                await _handle_stalled_download(download, db)
                                STALL_TRACKER.pop(download.id, None)
                                continue

                    state = matching_transfer.get("state", "")
                    logger.info(f"Track '{download.track}' has slskd state: {state}")

                    if "succeeded" in state.lower() or "complete" in state.lower():
                        found_file_path = find_file_recursively(settings.DOWNLOADS_PATH, download.filename)

                        if found_file_path and os.path.exists(found_file_path):
                            target_music_repo = settings.MUSIC_LIBRARY_PATH
                            try:
                                dest_file_path = await import_with_beets(found_file_path, target_music_repo, download_record=download)
                                if dest_file_path and os.path.exists(dest_file_path):
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

                                    logger.info(f"Track '{download.track}' successfully imported via Beets and marked completed at '{dest_file_path}'.")
                            except Exception as e:
                                logger.error(f"Failed to process/import completed file {found_file_path}: {e}")
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
                        target_music_repo = settings.MUSIC_LIBRARY_PATH
                        try:
                            logger.info(f"Found orphaned completed file on disk: {found_file_path}. Processing via Beets.")
                            dest_file_path = await import_with_beets(found_file_path, target_music_repo, download_record=None)
                            if dest_file_path and os.path.exists(dest_file_path):
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
                            logger.error(f"Failed to process orphaned file: {e}")

            # 2. Check for completed files in slskd even if not tracked in active_downloads
            from app.models import BeetsReviewItem
            for sf in all_slskd_files:
                state = sf.get("state", "")
                if "succeeded" in state.lower() or "complete" in state.lower():
                    s_fn = sf.get("filename", "")
                    found_file_path = find_file_recursively(settings.DOWNLOADS_PATH, s_fn)
                    if found_file_path and os.path.exists(found_file_path):
                        # Avoid repeating import if review item already exists
                        review_exists = db.query(BeetsReviewItem).filter(
                            BeetsReviewItem.downloaded_path == found_file_path,
                            BeetsReviewItem.status.in_(["review_required", "open", "skipped", "ignored"])
                        ).first()
                        if not review_exists:
                            logger.info(f"Processing completed slskd transfer found on disk via Beets: {found_file_path}")
                            await import_with_beets(found_file_path, settings.MUSIC_LIBRARY_PATH)

            db.commit()
            clean_empty_directories(settings.DOWNLOADS_PATH)
            db.close()
        except Exception as e:
            logger.exception(f"Error in background polling task: {e}")

        await asyncio.sleep(10)

def start_background_poller():
    logger.info("Startup step 4a: Getting event loop...")
    loop = asyncio.get_event_loop()
    logger.info("Startup step 4b: Creating task for poll_downloads...")
    loop.create_task(poll_downloads())
    logger.info("Startup step 4c: Background download poller started successfully.")
