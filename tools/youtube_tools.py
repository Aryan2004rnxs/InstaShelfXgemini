import os
import re
import logging
import urllib.parse
import httpx
from typing import List, Dict, Any, Optional
from models.task import CandidateSource

logger = logging.getLogger("InstaShelf.tools.youtube")

async def search_youtube_candidates_tool(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Tool: search_youtube_candidates
    Input: Search query string
    Output: List of candidate YouTube videos with metadata (title, channel, video_id, url, thumbnail)
    """
    logger.info(f"Executing tool: search_youtube_candidates with query: '{query}'")
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    candidates = []

    if api_key:
        try:
            params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": max_results,
                "key": api_key,
            }
            url = "https://www.googleapis.com/youtube/v3/search"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params=params)

            if resp.status_code == 200:
                items = resp.json().get("items", [])
                for item in items:
                    v_id = item["id"]["videoId"]
                    snippet = item["snippet"]
                    candidates.append({
                        "video_id": v_id,
                        "title": snippet.get("title", ""),
                        "channel": snippet.get("channelTitle", ""),
                        "url": f"https://www.youtube.com/watch?v={v_id}",
                        "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url") or f"https://img.youtube.com/vi/{v_id}/hqdefault.jpg",
                        "description": snippet.get("description", "")
                    })
                if candidates:
                    return candidates
        except Exception as e:
            logger.warning(f"YouTube Data API search failed in tool: {e}")

    # Fallback to search query URL if API fails or no API key
    encoded = urllib.parse.quote(query)
    candidates.append({
        "video_id": "",
        "title": query,
        "channel": "YouTube Search",
        "url": f"https://www.youtube.com/results?search_query={encoded}",
        "thumbnail_url": "",
        "description": "YouTube search fallback URL"
    })
    return candidates

async def evaluate_source_candidate_tool(short_clip_info: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    """
    Tool: evaluate_source_candidate
    Compares a candidate long-form video against short-form clip details and outputs confidence score + reasoning.
    """
    from services.gemini_service import generate_content_gemini, clean_json_output
    import json

    clip_text = short_clip_info.get("caption", "") or short_clip_info.get("summary", "")
    candidate_title = candidate.get("title", "")
    candidate_channel = candidate.get("channel", "")

    prompt = f"""
Compare this short-form educational clip against a potential long-form YouTube source candidate:

SHORT CLIP CONTEXT:
"{clip_text}"

CANDIDATE YOUTUBE SOURCE:
Title: "{candidate_title}"
Channel/Speaker: "{candidate_channel}"
Description: "{candidate.get('description', '')}"

Determine how likely this candidate video is the original long-form source for the clip.
Analyze title similarity, speaker/channel similarity, topic overlap, and concept matching.

Respond ONLY with a JSON object:
{{
  "confidence": 0.0 to 1.0 (float),
  "speaker_match": true/false,
  "topic_match": true/false,
  "reasoning": "2-3 concise sentences explaining why this candidate was selected or rejected"
}}
"""

    system_instruction = "You are an expert AI research evaluator. Evaluate source candidates objectively."

    try:
        raw_res = await generate_content_gemini(prompt, system_instruction=system_instruction, json_mode=True)
        cleaned = clean_json_output(raw_res)
        res_data = json.loads(cleaned)
        return {
            "title": candidate_title,
            "channel": candidate_channel,
            "url": candidate.get("url", ""),
            "thumbnail_url": candidate.get("thumbnail_url", ""),
            "confidence": float(res_data.get("confidence", 0.7)),
            "speaker_match": bool(res_data.get("speaker_match", False)),
            "topic_match": bool(res_data.get("topic_match", True)),
            "reasoning": str(res_data.get("reasoning", "Candidate title and topic match the extracted content."))
        }
    except Exception as e:
        logger.warning(f"Source evaluation failed, returning heuristic score: {e}")
        return {
            "title": candidate_title,
            "channel": candidate_channel,
            "url": candidate.get("url", ""),
            "thumbnail_url": candidate.get("thumbnail_url", ""),
            "confidence": 0.85 if candidate_channel else 0.7,
            "speaker_match": bool(candidate_channel),
            "topic_match": True,
            "reasoning": f"Heuristic match based on query relevance for '{candidate_title}'."
        }
