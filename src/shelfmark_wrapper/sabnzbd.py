"""SABnzbd-compatible API for download management.

This implements a subset of the SABnzbd API that allows applications
like Readarr to add downloads and check their status.

Reference: https://sabnzbd.org/wiki/advanced/api
"""

import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, Dict
from dataclasses import dataclass, field

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Request
from fastapi.responses import JSONResponse, Response

from shelfmark_wrapper.config import SERVER_API_KEY, INGEST_DIR, TMP_DIR

logger = logging.getLogger("shelfmark_wrapper.sabnzbd")


router = APIRouter(tags=["sabnzbd"])


class DownloadStatus(str, Enum):
    """Download status values matching SABnzbd."""

    QUEUED = "Queued"
    DOWNLOADING = "Downloading"
    COMPLETED = "Completed"
    FAILED = "Failed"
    PAUSED = "Paused"


@dataclass
class DownloadItem:
    """Represents a download in the queue."""

    nzo_id: str  # SABnzbd uses nzo_id for downloads
    source_id: str  # Our internal ID (e.g., MD5 hash)
    source: str  # Source type (direct_download, irc, etc.)
    title: str
    category: str = "*"
    status: DownloadStatus = DownloadStatus.QUEUED
    progress: float = 0.0
    size: int = 0
    downloaded: int = 0
    speed: float = 0.0
    eta: str = "0:00:00"
    error_message: str = ""
    download_path: Optional[str] = None
    added_time: float = field(default_factory=lambda: datetime.now().timestamp())


# In-memory download queue (in production, use shelfmark's queue)
_download_queue: Dict[str, DownloadItem] = {}


def _verify_api_key(apikey: str) -> bool:
    """Verify the API key matches configuration."""
    return not SERVER_API_KEY or apikey == SERVER_API_KEY


@router.get("/sabnzbd/api")
@router.post("/sabnzbd/api")
async def sabnzbd_api(
    request: Request,
    background_tasks: BackgroundTasks,
    mode: str = Query(..., description="API mode/function"),
    apikey: str = Query("", description="API key"),
    output: str = Query("json", description="Output format"),
    name: Optional[str] = Query(None, description="Download URL or ID"),
    nzo_ids: Optional[str] = Query(None, description="Comma-separated NZO IDs"),
    value: Optional[str] = Query(None, description="Value for operations"),
    cat: Optional[str] = Query(None, description="Category"),
    nzbname: Optional[str] = Query(None, description="NZB name (for addfile)"),
):
    """SABnzbd-compatible API endpoint.

    Supports the following modes:
    - version: Get API version
    - auth: Check authentication
    - get_config: Get configuration
    - queue: Get queue status
    - history: Get download history
    - addurl: Add download by URL/ID
    - addfile: Add download by NZB file upload
    - delete: Delete from queue
    - pause: Pause download
    - resume: Resume download
    - retry: Retry failed download
    """
    if mode not in ("version", "auth"):
        if not _verify_api_key(apikey):
            return JSONResponse(content={"status": False, "error": "API Key Incorrect"})

    logger.debug(
        "sabnzbd_api: mode=%s name=%s nzo_ids=%s cat=%s queue=%d",
        mode,
        name,
        nzo_ids,
        cat,
        len(_download_queue),
    )

    if mode == "version":
        return _handle_version()
    elif mode == "auth":
        return _handle_auth(apikey)
    elif mode == "get_config":
        return _handle_get_config()
    elif mode == "queue":
        return _handle_queue()
    elif mode == "history":
        return _handle_history()
    elif mode == "addurl":
        return await _handle_addurl(name, nzbname, cat, background_tasks)
    elif mode == "addfile":
        return await _handle_addfile(request, nzbname, cat, background_tasks)
    elif mode == "delete":
        return _handle_delete(nzo_ids, value)
    elif mode == "pause":
        return _handle_pause(nzo_ids)
    elif mode == "resume":
        return _handle_resume(nzo_ids)
    elif mode == "retry":
        return _handle_retry(nzo_ids)
    else:
        return JSONResponse(content={"status": False, "error": f"Unknown mode: {mode}"})


def _handle_version() -> JSONResponse:
    """Return API version."""
    return JSONResponse(content={"version": "4.0.0"})


def _handle_auth(apikey: str) -> JSONResponse:
    """Check if API key is valid."""
    if _verify_api_key(apikey):
        return JSONResponse(content={"auth": "ok", "status": True})
    return JSONResponse(content={"auth": "failed", "status": False})


def _handle_get_config() -> JSONResponse:
    """Return configuration."""
    return JSONResponse(
        content={
            "config": {
                "misc": {
                    "complete_dir": str(INGEST_DIR),
                    "download_dir": str(TMP_DIR),
                }
            },
            "status": True,
        }
    )


def _handle_queue() -> JSONResponse:
    """Return current download queue."""
    slots = []
    idx = 0

    for nzo_id, item in _download_queue.items():
        if item.status in (
            DownloadStatus.QUEUED,
            DownloadStatus.DOWNLOADING,
            DownloadStatus.PAUSED,
        ):
            slots.append(
                {
                    "index": idx,
                    "nzo_id": item.nzo_id,
                    "filename": item.title,
                    "status": item.status.value,
                    "percentage": str(int(item.progress)),
                    "size": str(item.size),
                    "sizeleft": str(item.size - item.downloaded) if item.size else "0",
                    "mb": str(item.size / (1024 * 1024)) if item.size else "0",
                    "mbleft": str((item.size - item.downloaded) / (1024 * 1024))
                    if item.size
                    else "0",
                    "timeleft": item.eta,
                    "cat": item.category,
                }
            )
            idx += 1

    logger.debug(
        "queue: %d slots (total=%d ids=%s)",
        len(slots),
        len(_download_queue),
        [s["nzo_id"] for s in slots],
    )

    total_speed = sum(
        item.speed
        for item in _download_queue.values()
        if item.status == DownloadStatus.DOWNLOADING
    )
    if total_speed > 0:
        speed_kbs = total_speed / 1024
        if speed_kbs >= 1024:
            speed_str = f"{speed_kbs / 1024:.1f} M"
        else:
            speed_str = f"{speed_kbs:.1f} K"
    else:
        speed_str = "0"

    return JSONResponse(
        content={
            "queue": {
                "slots": slots,
                "noofslots": len(slots),
                "status": "Downloading"
                if any(s["status"] == "Downloading" for s in slots)
                else "Idle",
                "speed": speed_str,
                "paused": False,
            },
            "status": True,
        }
    )


def _handle_history() -> JSONResponse:
    """Return download history."""
    slots = []

    for nzo_id, item in _download_queue.items():
        if item.status in (DownloadStatus.COMPLETED, DownloadStatus.FAILED):
            slots.append(
                {
                    "nzo_id": item.nzo_id,
                    "name": item.title,
                    "status": item.status.value,
                    "storage": item.download_path or "",
                    "fail_message": item.error_message,
                    "completed": int(item.added_time),
                    "bytes": item.size,
                    "category": item.category,
                }
            )

    return JSONResponse(
        content={
            "history": {
                "slots": slots,
                "noofslots": len(slots),
            },
            "status": True,
        }
    )


async def _handle_addurl(
    name: Optional[str],
    nzbname: Optional[str],
    cat: Optional[str],
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """Add a download by URL or ID."""
    if not name:
        return JSONResponse(content={"status": False, "error": "No URL/ID provided"})

    source_id = name
    if "/download/" in name:
        source_id = name.split("/download/")[-1].split("?")[0]

    nzo_id = f"SABnzbd_nzo_{uuid.uuid4().hex[:12]}"

    title = nzbname or f"Download {source_id[:8]}..."

    item = DownloadItem(
        nzo_id=nzo_id,
        source_id=source_id,
        source="direct_download",
        title=title,
        category=cat if cat else "*",
    )

    _download_queue[nzo_id] = item

    logger.info(
        "addurl: created nzo_id=%s name=%s cat=%s queue_size=%d",
        nzo_id,
        item.title,
        item.category,
        len(_download_queue),
    )

    background_tasks.add_task(_execute_download, nzo_id, source_id)

    return JSONResponse(
        content={
            "status": True,
            "nzo_ids": [nzo_id],
        }
    )


async def _handle_addfile(
    request: Request,
    nzbname: Optional[str],
    cat: Optional[str],
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """Handle addfile mode - receives NZB file upload from Chaptarr/Readarr."""
    import re

    form = await request.form()
    nzb_file = form.get("name")
    if not nzb_file:
        return JSONResponse(content={"status": False, "error": "No NZB file provided"})

    if hasattr(nzb_file, "read"):
        content = await nzb_file.read()
        nzb_text = content.decode("utf-8", errors="replace")
    else:
        nzb_text = str(nzb_file)

    match = re.search(r'<meta\s+type="id">([^<]+)</meta>', nzb_text)
    if not match:
        return JSONResponse(
            content={"status": False, "error": "Could not extract source ID from NZB"}
        )

    source_id = match.group(1)
    title = nzbname or f"Download {source_id[:8]}..."

    nzo_id = f"SABnzbd_nzo_{uuid.uuid4().hex[:12]}"

    item = DownloadItem(
        nzo_id=nzo_id,
        source_id=source_id,
        source="direct_download",
        title=title,
        category=cat if cat else "*",
    )

    _download_queue[nzo_id] = item
    logger.info(
        "addfile: created nzo_id=%s name=%s cat=%s nzbname=%s queue_size=%d",
        nzo_id,
        item.title,
        item.category,
        nzbname,
        len(_download_queue),
    )
    background_tasks.add_task(_execute_download, nzo_id, source_id)

    return JSONResponse(content={"status": True, "nzo_ids": [nzo_id]})


async def _execute_download(nzo_id: str, source_id: str) -> None:
    """Execute the actual download using shelfmark.

    All blocking I/O is offloaded to a thread pool via asyncio.to_thread
    so that Readarr's queue/history polling is never starved.
    """
    import asyncio
    import time
    from threading import Event

    item = _download_queue.get(nzo_id)
    if not item:
        logger.warning("execute_download: nzo_id=%s not found in queue", nzo_id)
        return

    _item = item  # narrowed alias for use inside callbacks

    logger.info(
        "execute_download: starting nzo_id=%s source_id=%s",
        nzo_id,
        source_id,
    )
    try:
        from shelfmark.release_sources.direct_download import (
            get_book_info,
            DirectDownloadHandler,
        )
        from shelfmark.core.models import DownloadTask

        book_info = await asyncio.to_thread(
            get_book_info,
            source_id,
            fetch_download_count=False,
        )
        item.title = book_info.title
        from shelfmark_wrapper.newznab import _parse_size_to_bytes

        item.size = _parse_size_to_bytes(book_info.size)

        logger.info(
            "execute_download: nzo_id=%s status=DOWNLOADING title=%s size=%d",
            nzo_id,
            item.title,
            item.size,
        )

        task = DownloadTask(
            task_id=source_id,
            source="direct_download",
            title=book_info.title,
            author=book_info.author,
            year=book_info.year,
            format=book_info.format,
            size=book_info.size,
            preview=book_info.preview,
        )

        # Progress callback with speed/ETA tracking
        _last_progress = [0.0]
        _last_time = [time.time()]

        def progress_callback(progress: float) -> None:
            now = time.time()
            _item.progress = progress
            if _item.size > 0:
                _item.downloaded = int((progress / 100.0) * _item.size)
                dt = now - _last_time[0]
                if dt >= 0.5:
                    dp = progress - _last_progress[0]
                    if dp > 0:
                        bytes_downloaded = (dp / 100.0) * _item.size
                        _item.speed = bytes_downloaded / dt
                        remaining = _item.size - _item.downloaded
                        if _item.speed > 0:
                            eta_sec = int(remaining / _item.speed)
                            m, s = divmod(eta_sec, 60)
                            h, m = divmod(m, 60)
                            _item.eta = f"{h}:{m:02d}:{s:02d}"
                    _last_progress[0] = progress
                    _last_time[0] = now

        # Status callback — drives QUEUED → DOWNLOADING → FAILED transitions
        def status_callback(status: str, message: Optional[str] = None) -> None:
            st = status.lower()
            if st == "downloading":
                _item.status = DownloadStatus.DOWNLOADING
            elif st == "error":
                _item.status = DownloadStatus.FAILED
                _item.error_message = message or "Download failed"
            elif st == "cancelled":
                _item.status = DownloadStatus.FAILED
                _item.error_message = message or "Cancelled"

        handler = DirectDownloadHandler()
        cancel_flag = Event()

        result_path = await asyncio.to_thread(
            handler.download,
            task,
            cancel_flag,
            progress_callback,
            status_callback,
        )

        if not result_path:
            if item.status != DownloadStatus.FAILED:
                item.status = DownloadStatus.FAILED
                item.error_message = "Download returned no path"
                logger.warning(
                    "execute_download: nzo_id=%s FAILED (no result path)",
                    nzo_id,
                )
            return

        from pathlib import Path
        from shelfmark.download.postprocess.router import post_process_download

        task.staged_path = result_path
        status_callback("resolving", "Post-processing download")

        final_path = await asyncio.to_thread(
            post_process_download,
            Path(result_path),
            task,
            cancel_flag,
            status_callback,
            preserve_source_on_failure=False,
        )

        if not final_path or cancel_flag.is_set():
            if item.status != DownloadStatus.FAILED:
                item.status = DownloadStatus.FAILED
                item.error_message = "Post-processing failed"
                logger.warning(
                    "execute_download: nzo_id=%s FAILED (post-process)",
                    nzo_id,
                )
            return

        item.status = DownloadStatus.COMPLETED
        item.download_path = final_path
        item.progress = 100.0
        logger.info(
            "execute_download: nzo_id=%s COMPLETED path=%s",
            nzo_id,
            final_path,
        )

    except Exception as e:
        item.status = DownloadStatus.FAILED
        item.error_message = str(e)
        logger.error(
            "execute_download: nzo_id=%s FAILED error=%s",
            nzo_id,
            str(e),
            exc_info=True,
        )


def _handle_delete(nzo_ids: Optional[str], value: Optional[str]) -> JSONResponse:
    """Delete downloads from queue or history."""
    ids_to_delete = []

    if nzo_ids:
        ids_to_delete = [id.strip() for id in nzo_ids.split(",")]
    elif value:
        ids_to_delete = [value]

    deleted = []
    for nzo_id in ids_to_delete:
        if nzo_id in _download_queue:
            del _download_queue[nzo_id]
            deleted.append(nzo_id)

    return JSONResponse(
        content={
            "status": True,
            "nzo_ids": deleted,
        }
    )


def _handle_pause(nzo_ids: Optional[str]) -> JSONResponse:
    """Pause downloads."""
    if not nzo_ids:
        return JSONResponse(content={"status": False, "error": "No NZO IDs provided"})

    ids = [id.strip() for id in nzo_ids.split(",")]
    paused = []

    for nzo_id in ids:
        item = _download_queue.get(nzo_id)
        if item and item.status == DownloadStatus.DOWNLOADING:
            item.status = DownloadStatus.PAUSED
            paused.append(nzo_id)

    return JSONResponse(content={"status": True, "nzo_ids": paused})


def _handle_resume(nzo_ids: Optional[str]) -> JSONResponse:
    """Resume paused downloads."""
    if not nzo_ids:
        return JSONResponse(content={"status": False, "error": "No NZO IDs provided"})

    ids = [id.strip() for id in nzo_ids.split(",")]
    resumed = []

    for nzo_id in ids:
        item = _download_queue.get(nzo_id)
        if item and item.status == DownloadStatus.PAUSED:
            item.status = DownloadStatus.DOWNLOADING
            resumed.append(nzo_id)

    return JSONResponse(content={"status": True, "nzo_ids": resumed})


def _handle_retry(nzo_ids: Optional[str]) -> JSONResponse:
    """Retry failed downloads."""
    if not nzo_ids:
        return JSONResponse(content={"status": False, "error": "No NZO IDs provided"})

    ids = [id.strip() for id in nzo_ids.split(",")]
    retried = []

    for nzo_id in ids:
        item = _download_queue.get(nzo_id)
        if item and item.status == DownloadStatus.FAILED:
            item.status = DownloadStatus.QUEUED
            item.progress = 0.0
            item.error_message = ""
            retried.append(nzo_id)

    return JSONResponse(content={"status": True, "nzo_ids": retried})


# Additional endpoint for direct file download
@router.get("/api/v1/download/{source_id}")
async def download_file(
    source_id: str,
    apikey: str = Query("", description="API key"),
):
    """Direct download endpoint.

    This is called by Readarr/etc. to actually fetch the file.
    Returns the NZB-like response that triggers the download.
    """
    if not _verify_api_key(apikey):
        raise HTTPException(status_code=401, detail="Invalid API key")

    nzb_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE nzb PUBLIC "-//newzBin//DTD NZB 1.1//EN" "http://www.newzbin.com/DTD/nzb/nzb-1.1.dtd">
<nzb xmlns="http://www.newzbin.com/DTD/2003/nzb">
  <head>
    <meta type="source">shelfmark-wrapper</meta>
    <meta type="id">{source_id}</meta>
  </head>
  <file poster="shelfmark@wrapper" date="0" subject="{source_id}">
    <groups>
      <group>alt.binaries.ebooks</group>
    </groups>
    <segments>
      <segment bytes="0" number="1">{source_id}</segment>
    </segments>
  </file>
</nzb>
"""

    return Response(
        content=nzb_content,
        media_type="application/x-nzb",
        headers={"Content-Disposition": f'attachment; filename="{source_id}.nzb"'},
    )
