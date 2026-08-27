import logging
from typing import Dict, Any, Tuple, List
from scraper import scrape_instagram_content

logger = logging.getLogger("InstaShelf.tools.instagram")

async def extract_instagram_content_tool(url: str) -> Dict[str, Any]:
    """
    Tool: extract_instagram_content
    Input: Instagram Reel or Post URL
    Output: Scraped caption, media paths, source type (REEL or POST), and temporary dir.
    """
    logger.info(f"Executing tool: extract_instagram_content for URL: {url}")
    try:
        source_type, caption, image_paths, temp_dir = await scrape_instagram_content(url)
        return {
            "success": True,
            "source_type": source_type,
            "caption": caption,
            "image_paths": image_paths,
            "temp_dir": temp_dir,
            "message": f"Successfully extracted {source_type} content."
        }
    except Exception as e:
        logger.error(f"Tool extract_instagram_content failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "caption": "",
            "image_paths": [],
            "temp_dir": None
        }
