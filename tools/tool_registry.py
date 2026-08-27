import logging
from typing import Dict, Any, Callable
from tools.instagram_tools import extract_instagram_content_tool
from tools.youtube_tools import search_youtube_candidates_tool, evaluate_source_candidate_tool
from tools.knowledge_tools import generate_knowledge_map_tool
from tools.study_tools import generate_study_material_tool
from tools.storage_tools import save_to_shelf_tool
from tools.notification_tools import notify_user_tool

logger = logging.getLogger("InstaShelf.tools.registry")

AGENT_TOOLS: Dict[str, Callable] = {
    "extract_instagram_content": extract_instagram_content_tool,
    "search_youtube_candidates": search_youtube_candidates_tool,
    "evaluate_source_candidate": evaluate_source_candidate_tool,
    "generate_knowledge_map": generate_knowledge_map_tool,
    "generate_study_material": generate_study_material_tool,
    "save_to_shelf": save_to_shelf_tool,
    "notify_user": notify_user_tool
}

def get_tool(tool_name: str) -> Callable:
    if tool_name not in AGENT_TOOLS:
        raise ValueError(f"Unknown agent tool: {tool_name}")
    return AGENT_TOOLS[tool_name]
