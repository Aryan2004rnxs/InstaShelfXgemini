import json
import logging
from typing import Dict, Any, Optional
from services.gemini_service import generate_content_gemini, clean_json_output
from models.knowledge import MasterNoteContent

logger = logging.getLogger("InstaShelf.tools.study")

async def generate_study_material_tool(
    topic: str,
    knowledge_map: Dict[str, Any],
    source_context: str = "",
    learning_goal: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: generate_study_material
    Input: Topic, knowledge map, original source context, and optional user learning goal (e.g. 'Prepare me for an interview')
    Output: Structured MasterNoteContent with core ideas, detailed study guide, flashcards, revision & interview questions.
    """
    logger.info(f"Executing tool: generate_study_material for topic '{topic}' (Goal: '{learning_goal}')")

    goal_prompt_addition = ""
    if learning_goal:
        goal_prompt_addition = f"\nSPECIAL USER LEARNING GOAL: '{learning_goal}'\nTailor the study guide and emphasize interview-level questions, trade-offs, edge cases, and real-world implementation traps."

    prompt = f"""
You are an elite study coach and lead software architect. 
Generate a comprehensive study resource for the topic: "{topic}".

KNOWLEDGE MAP:
{json.dumps(knowledge_map)}

SOURCE CONTEXT:
"{source_context}"
{goal_prompt_addition}

Return a JSON object matching this structure:
{{
  "title": "Master Study Guide: {topic}",
  "core_idea": "Synthesized 2-sentence summary of the core thesis.",
  "detailed_notes": "A high-impact Markdown study guide. Include section headers, bullet points, Markdown code blocks, ascii diagrams/tables, and practical examples.",
  "key_takeaways": [
    "Takeaway 1",
    "Takeaway 2",
    "Takeaway 3"
  ],
  "flashcards": [
    {{"front": "Question/Prompt", "back": "Clear concise answer"}}
  ],
  "revision_questions": [
    "Self-test revision question 1",
    "Self-test revision question 2"
  ],
  "interview_questions": [
    {{"question": "Interview Question?", "answer": "Model Answer with trade-offs"}}
  ],
  "things_to_remember": [
    "Critical caveat or performance tip"
  ]
}}
"""

    system_instruction = "You are a master educator. Create visually rich, rigorous, and highly engaging study materials."

    try:
        raw_res = await generate_content_gemini(prompt, system_instruction=system_instruction, json_mode=True)
        cleaned = clean_json_output(raw_res)
        parsed = json.loads(cleaned)
        master_note = MasterNoteContent(**parsed)
        return master_note.model_dump()
    except Exception as e:
        logger.error(f"Failed to generate study material via Gemini: {e}")
        return {
            "title": f"Master Study Guide: {topic}",
            "core_idea": f"Study resource for {topic}.",
            "detailed_notes": f"### {topic}\n\nKey principles and overview derived from content.",
            "key_takeaways": [f"Understand core principles of {topic}"],
            "flashcards": [{"front": f"What is {topic}?", "back": "See study notes for details."}],
            "revision_questions": [f"Explain how {topic} works in production."],
            "interview_questions": [{"question": f"What are the main trade-offs in {topic}?", "answer": "Performance vs complexity."}],
            "things_to_remember": ["Always benchmark before optimizing."]
        }
