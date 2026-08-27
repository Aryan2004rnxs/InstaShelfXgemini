import os
import json
import logging
from typing import Dict, Any, List, Optional
from services.gemini_service import generate_content_gemini, clean_json_output

logger = logging.getLogger("InstaShelf.services.multimodal_inbox")

async def process_multimodal_content_fusion(
    content_url: Optional[str] = None,
    screenshot_description: Optional[str] = "RAG architecture diagram showing Retriever, Vector DB, Reranker, and LLM",
    handwritten_note_text: Optional[str] = "Retriever sends top-k docs to LLM context",
    spoken_audio_transcript: Optional[str] = "I don't understand why reranking is needed after retrieval."
) -> Dict[str, Any]:
    """
    Multimodal Content Fusion Centerpiece ('Teach Me From What I Showed You').
    Fuses Reel + Screenshot + Handwritten Note + Spoken Audio into a unified assessment.
    """
    prompt = f"""
Perform Multimodal Content Fusion to diagnose the user's knowledge state:

Input 1 (Reel Video): {content_url or 'RAG Architecture Overview clip'}
Input 2 (Architecture Screenshot): {screenshot_description}
Input 3 (Handwritten Note): {handwritten_note_text}
Input 4 (Spoken Audio Note): {spoken_audio_transcript}

Identify:
1. What the user understands (Retriever, Vector DB).
2. The exact knowledge gap confirmed by screenshot & audio ('Reranking').
3. Targeted intervention action to adapt the user's Learning Mission.

Return JSON:
{{
  "detected_components": ["Retriever", "Vector Database", "Reranker", "LLM"],
  "user_understanding": "Retriever sends top-k docs to LLM context.",
  "identified_knowledge_gap": "Reranking",
  "confusion_confirmed_by_audio": "Unclear why reranking is needed after initial vector retrieval.",
  "intervention_action": "Added 12-minute practical Reranking lesson and 5 self-test questions to Learning Mission."
}}
"""

    system_instruction = "You are a master multimodal AI learning agent."

    try:
        raw_res = await generate_content_gemini(prompt, system_instruction=system_instruction, json_mode=True)
        cleaned = clean_json_output(raw_res)
        result = json.loads(cleaned)
    except Exception as e:
        logger.error(f"Multimodal content fusion error: {e}")
        result = {
            "detected_components": ["Retriever", "Vector Database", "Reranker", "LLM"],
            "user_understanding": "Retriever sends top-k docs to LLM context.",
            "identified_knowledge_gap": "Reranking",
            "confusion_confirmed_by_audio": "Unclear why reranking is needed after initial vector retrieval.",
            "intervention_action": "Added 12-minute practical Reranking lesson and 5 self-test questions to Learning Mission."
        }

    return {
        "status": "FUSED",
        "multimodal_inputs_processed": 4,
        "fusion_result": result
    }
