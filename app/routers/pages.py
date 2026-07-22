import os
import logging
import asyncio
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from app.config import settings
from app.contracts.schemas import SearchQuery, SlskdResult
from app.contracts.services import SlskdClientContract, SearchExecutorContract
from app.dependencies import get_slskd_client, get_search_executor

logger = logging.getLogger("track_portal.pages")
router = APIRouter()

class SearchRequest(BaseModel):
    artist: str
    track_or_album: str

class DownloadRequest(BaseModel):
    artist: str
    track: str
    album: Optional[str] = ""
    filename: str
    size: int
    username: str
    format: str
    bitrate: Optional[int] = 0

@router.get("/", response_class=HTMLResponse)
async def get_spa(request: Request):
    """
    Renders the Single Page Application index page.
    """
    from app.main import templates
    return templates.TemplateResponse(request=request, name="index.html", context={})

@router.post("/api/search", response_class=JSONResponse)
async def api_search(
    payload: SearchRequest,
    search_executor: SearchExecutorContract = Depends(get_search_executor)
):
    """
    Triggers progressive fallback query generation, executes on slskd,
    merges & deduplicates results, parses filenames, enriches with Beets,
    ranks, and returns the sorted candidates.
    """
    artist = payload.artist.strip()
    track_or_album = payload.track_or_album.strip()

    if not artist and not track_or_album:
        raise HTTPException(status_code=400, detail="Artist or Track/Album must be provided")

    query_obj = SearchQuery(artist=artist, track=track_or_album)
    results = await search_executor.execute_search(query_obj)

    # Serialize results list of SlskdResult Pydantic models
    serialized_results = [r.model_dump() for r in results]

    return JSONResponse(content={"results": serialized_results})

@router.post("/api/download", response_class=JSONResponse)
async def api_download(
    payload: DownloadRequest,
    slskd_client: SlskdClientContract = Depends(get_slskd_client)
):
    """
    Enqueues a file download via slskd.
    """
    # Log exact required log keyword: DOWNLOAD_REQUESTED
    logger.info(f"DOWNLOAD_REQUESTED - Username: '{payload.username}', Filename: '{payload.filename}'")

    success = await slskd_client.enqueue_download(payload.username, payload.filename, payload.size)

    if success:
        # Log exact required log keyword: DOWNLOAD_COMPLETED (enqueue successful)
        logger.info(f"DOWNLOAD_COMPLETED - Filename: '{payload.filename}'")
        return {"status": "success", "message": "Download enqueued successfully"}
    else:
        logger.error(f"Download request failed for file: '{payload.filename}'")
        raise HTTPException(status_code=500, detail="Failed to enqueue download in slskd")
