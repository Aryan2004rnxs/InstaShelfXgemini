import json
import logging
from typing import Dict, Any
from services.gemini_service import generate_content_gemini, clean_json_output
from models.knowledge import KnowledgeMap

logger = logging.getLogger("InstaShelf.tools.knowledge")

async def generate_knowledge_map_tool(content_summary: str, full_context: str = "") -> Dict[str, Any]:
    """
    Tool: generate_knowledge_map
    Input: Content summary and raw context
    Output: Structured KnowledgeMap dictionary (topic, category, difficulty, prerequisites, core concepts, knowledge gaps)
    """
    logger.info("Executing tool: generate_knowledge_map")
    
    prompt = f"""
Analyze this educational content and construct a structured Knowledge Map:

CONTENT SUMMARY:
"{content_summary}"

FULL CONTEXT:
"{full_context}"

Return a JSON object matching this structure:
{{
  "topic": "Primary topic name (e.g. Retrieval Augmented Generation)",
  "category": "Main tag category (e.g. #tech, #ai, #finance, #productivity)",
  "difficulty": "Beginner | Intermediate | Advanced",
  "prerequisites": ["prerequisite 1", "prerequisite 2"],
  "core_concepts": [
    {{
      "name": "Concept name",
      "description": "Clear 1-sentence definition",
      "importance": "HIGH",
      "parent_concept": null
    }}
  ],
  "knowledge_gaps": ["topic to explore next for complete understanding"],
  "common_misconceptions": ["common mistake or trap people fall into"],
  "recommended_next_steps": ["suggested next step or paper to read"]
}}
"""

    system_instruction = "You are an expert Knowledge Architect. Extract precise pedagogical knowledge maps."

    try:
        raw_res = await generate_content_gemini(prompt, system_instruction=system_instruction, json_mode=True)
        cleaned = clean_json_output(raw_res)
        parsed = json.loads(cleaned)
        k_map = KnowledgeMap(**parsed)
        return k_map.model_dump()
    except Exception as e:
        logger.error(f"Failed to generate knowledge map via Gemini: {e}")
        return {
            "topic": "Educational Content",
            "category": "#tech",
            "difficulty": "Intermediate",
            "prerequisites": ["Foundational knowledge"],
            "core_concepts": [
                {"name": "Core Concept", "description": content_summary, "importance": "HIGH", "parent_concept": None}
            ],
            "knowledge_gaps": ["Deep implementation details"],
            "common_misconceptions": ["Confusing theoretical concepts with implementation"],
            "recommended_next_steps": ["Explore original documentation"]
        }
