import logging
from typing import Dict, Any, Optional
from tools.study_tools import generate_study_material_tool

logger = logging.getLogger("InstaShelf.agents.study_agent")

class StudyAgent:
    """
    Study Agent: Generates Master Notes, flashcards, self-assessment questions,
    and goal-tailored interview preparation.
    """
    def __init__(self, name: str = "StudyAgent"):
        self.name = name

    async def generate_study_resources(
        self,
        topic: str,
        knowledge_map: Dict[str, Any],
        source_context: str = "",
        learning_goal: Optional[str] = None
    ) -> Dict[str, Any]:
        logger.info(f"[{self.name}] Generating Master Notes & Flashcards for '{topic}'...")

        master_note = await generate_study_material_tool(
            topic=topic,
            knowledge_map=knowledge_map,
            source_context=source_context,
            learning_goal=learning_goal
        )

        logger.info(f"[{self.name}] Master Notes & Study Material created. Flashcards: {len(master_note.get('flashcards', []))}, Revision Qs: {len(master_note.get('revision_questions', []))}")

        return {
            "success": True,
            "master_note": master_note
        }
