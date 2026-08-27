import logging
from typing import Dict, Any
from tools.knowledge_tools import generate_knowledge_map_tool

logger = logging.getLogger("InstaShelf.agents.knowledge_agent")

class KnowledgeCuratorAgent:
    """
    Knowledge Curator Agent: Extracts topic hierarchy, difficulty rating, prerequisites,
    core concepts, knowledge gaps, and misconceptions.
    """
    def __init__(self, name: str = "KnowledgeCuratorAgent"):
        self.name = name

    async def curating_knowledge(
        self,
        summary: str,
        full_context: str = "",
        selected_source_title: str = ""
    ) -> Dict[str, Any]:
        logger.info(f"[{self.name}] Building structured knowledge map...")

        context = f"{full_context}\nSelected Source: {selected_source_title}".strip()
        knowledge_map = await generate_knowledge_map_tool(summary, context)

        logger.info(f"[{self.name}] Knowledge Map created for topic '{knowledge_map.get('topic')}' with {len(knowledge_map.get('core_concepts', []))} core concepts.")

        return {
            "success": True,
            "topic": knowledge_map.get("topic", "Educational Resource"),
            "knowledge_map": knowledge_map
        }
