import logging
from typing import Dict, Any, List, Optional
from models.task import CandidateSource
from tools.youtube_tools import search_youtube_candidates_tool, evaluate_source_candidate_tool

logger = logging.getLogger("InstaShelf.agents.research_agent")

class ResearchAgent:
    """
    Research Agent: Responsible for source discovery, long-form video candidate search,
    candidate evaluation, confidence scoring, and candidate selection explanation.
    """
    def __init__(self, name: str = "ResearchAgent"):
        self.name = name

    async def execute_research(
        self,
        extracted_info: Dict[str, Any],
        search_query_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes autonomous research pipeline:
        1. Generates search queries based on extracted titles/topics.
        2. Searches YouTube for candidate long-form videos.
        3. Evaluates candidates using Gemini matching.
        4. Ranks candidates by confidence score.
        5. Selects top candidate and provides natural language explanation.
        """
        logger.info(f"[{self.name}] Beginning source discovery and validation...")
        
        caption = extracted_info.get("caption", "")
        summary = extracted_info.get("summary", "")
        extracted_videos = extracted_info.get("youtube_videos", [])

        # Step 1: Formulate search query
        query = search_query_override
        if not query:
            if extracted_videos and len(extracted_videos) > 0:
                v = extracted_videos[0]
                query = v.get("search_query") or v.get("title")
            else:
                # Use summary or first line of caption
                query = summary or caption[:100].split("\n")[0]

        if not query:
            query = "Educational technology architecture"

        logger.info(f"[{self.name}] Formulated search query: '{query}'")

        # Step 2: Discover YouTube candidates
        raw_candidates = await search_youtube_candidates_tool(query, max_results=4)
        logger.info(f"[{self.name}] Discovered {len(raw_candidates)} YouTube source candidates.")

        # Step 3: Evaluate candidates with Gemini
        evaluated_sources: List[CandidateSource] = []
        best_candidate: Optional[CandidateSource] = None
        highest_confidence = 0.0

        for cand in raw_candidates:
            eval_result = await evaluate_source_candidate_tool(extracted_info, cand)
            source_model = CandidateSource(
                title=eval_result["title"],
                channel=eval_result["channel"],
                url=eval_result["url"],
                thumbnail_url=eval_result["thumbnail_url"],
                confidence=eval_result["confidence"],
                reasoning=eval_result["reasoning"],
                speaker_match=eval_result["speaker_match"],
                topic_match=eval_result["topic_match"]
            )
            evaluated_sources.append(source_model)

            if source_model.confidence > highest_confidence:
                highest_confidence = source_model.confidence
                best_candidate = source_model

        if not best_candidate and evaluated_sources:
            best_candidate = evaluated_sources[0]

        logger.info(f"[{self.name}] Selected candidate '{best_candidate.title if best_candidate else 'None'}' with confidence {highest_confidence*100:.0f}%")

        return {
            "success": True,
            "query_used": query,
            "candidate_sources": evaluated_sources,
            "selected_source": best_candidate,
            "confidence": highest_confidence,
            "explanation": best_candidate.reasoning if best_candidate else "No candidates found."
        }
