import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from models import ShelfRow
import sheets
import dedup

logger = logging.getLogger("InstaShelf.tools.storage")

async def save_to_shelf_tool(
    title: Optional[str] = None,
    creator: Optional[str] = None,
    url: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    confidence: Optional[float] = 0.85,
    instagram_url: Optional[str] = None,
    raw_context: Optional[str] = None,
    ai_summary: Optional[str] = None,
    content_type: str = "YOUTUBE",
    source_type: str = "REEL",
    tags: str = "#tech",
    task: Optional[Dict[str, Any]] = None,
    selected_source: Optional[Dict[str, Any]] = None,
    master_note: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Tool: save_to_shelf
    Input: Metadata of item or task dictionary
    Output: Saved status, content hash, sync status
    """
    if task:
        if selected_source:
            title = title or selected_source.get("title", "Discovered Source")
            url = url or selected_source.get("url", task.get("content_url", "https://youtube.com"))
            creator = creator or selected_source.get("channel", "YouTube")
            confidence = confidence or selected_source.get("confidence", 0.85)
        else:
            title = title or task.get("learning_goal", "Saved Study Topic")
            url = url or task.get("content_url", "https://youtube.com")
            creator = creator or "InstaShelf Agent"

        instagram_url = instagram_url or task.get("content_url", "https://instagram.com")
        raw_context = raw_context or task.get("learning_goal", "Study Context")
        ai_summary = ai_summary or (master_note.get("summary") if master_note else "Autonomous Agent Learning Resource")
        thumbnail_url = thumbnail_url or "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=800&q=80"

    title = title or "Educational Content"
    url = url or "https://youtube.com"
    creator = creator or "Educational Source"
    instagram_url = instagram_url or url
    raw_context = raw_context or title
    ai_summary = ai_summary or title
    thumbnail_url = thumbnail_url or ""
    confidence = confidence or 0.85

    logger.info(f"Executing tool: save_to_shelf for '{title}'")
    ts_suffix = str(datetime.utcnow().timestamp())
    content_hash = dedup.compute_youtube_hash(url, f"{title}_{ts_suffix}")

    row = ShelfRow(
        saved_at=datetime.utcnow().isoformat() + "Z",
        source_type=source_type,
        content_type=content_type,
        title=title,
        creator=creator,
        url=url,
        thumbnail_url=thumbnail_url,
        confidence=float(confidence),
        instagram_url=instagram_url,
        raw_context=raw_context,
        ai_summary=ai_summary,
        content_hash=content_hash,
        status="UNREAD",
        gemini_notes=f"Processed by InstaShelf Agent (Source Match Score: {int(confidence*100)}%)",
        tags=tags
    )

    # Save to local database store instantly
    import utils
    utils.save_local_shelf_row(row.model_dump())

    try:
        new_count, dup_count = await sheets.save_rows_to_shelf([row])
        return {
            "success": True,
            "saved": True,
            "content_hash": content_hash,
            "message": f"Saved '{title}' to shelf and synced to database."
        }
    except Exception as e:
        logger.error(f"Failed to save item to Google Sheets: {e}")
        return {
            "success": True,
            "saved": True,
            "content_hash": content_hash,
            "message": f"Saved '{title}' to local database."
        }
