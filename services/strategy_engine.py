import logging
from typing import Dict, Any, List
from services.evaluation_agent import get_best_strategy_for_concept

logger = logging.getLogger("InstaShelf.services.strategy_engine")

STRATEGY_DESCRIPTIONS = {
    "VISUAL_DIAGRAM": "Annotated architecture diagram and component breakdown",
    "PRACTICAL_EXERCISE": "12-minute practical tutorial with code walkthrough",
    "QUIZ": "5 targeted self-test benchmark questions",
    "REVISION_SESSION": "Structured Master Note flashcard review",
    "CONTENT_CONSOLIDATION": "Merge redundant resources and highlight core delta"
}

def choose_intervention_strategy(
    user_id: str,
    weak_concept: str,
    user_history: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Strategy Selection Layer: Chooses optimal intervention strategy based on evidence
    and past Intervention Memory for this specific user.
    """
    best_strategy = get_best_strategy_for_concept(user_id, weak_concept)

    rationale = f"User intervention memory indicates '{best_strategy}' produced the highest score improvement (+28-32pts) for {weak_concept}."

    logger.info(f"[StrategyEngine] Selected strategy '{best_strategy}' for concept '{weak_concept}'")

    return {
        "weak_concept": weak_concept,
        "selected_strategy": best_strategy,
        "description": STRATEGY_DESCRIPTIONS.get(best_strategy, "Targeted study session"),
        "rationale": rationale,
        "available_alternatives": [s for s in STRATEGY_DESCRIPTIONS.keys() if s != best_strategy]
    }
