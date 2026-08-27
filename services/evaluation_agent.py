import json
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("InstaShelf.services.evaluation_agent")

class InterventionRecord(BaseModel):
    intervention_id: str
    concept: str
    strategy_type: str  # VISUAL_DIAGRAM, PRACTICAL_EXERCISE, QUIZ, REVISION_SESSION, CONSOLIDATION
    before_score: float
    after_score: float
    score_delta: float
    effective: bool
    timestamp: str

_INTERVENTION_MEMORY: Dict[str, List[InterventionRecord]] = {}

def record_intervention_memory(
    user_id: str,
    concept: str,
    strategy_type: str,
    before_score: float,
    after_score: float
) -> InterventionRecord:
    delta = round(after_score - before_score, 1)
    effective = delta > 0.0

    record = InterventionRecord(
        intervention_id=f"INT-{len(_INTERVENTION_MEMORY.get(user_id, [])) + 1}",
        concept=concept,
        strategy_type=strategy_type,
        before_score=before_score,
        after_score=after_score,
        score_delta=delta,
        effective=effective,
        timestamp=""
    )

    if user_id not in _INTERVENTION_MEMORY:
        _INTERVENTION_MEMORY[user_id] = []
    _INTERVENTION_MEMORY[user_id].append(record)
    logger.info(f"[EvaluationAgent] Recorded intervention memory: {strategy_type} for '{concept}' delta: +{delta}pts (Effective: {effective})")
    return record

def get_best_strategy_for_concept(user_id: str, concept: str) -> str:
    """Queries Intervention Memory to select the strategy that produced the highest positive delta."""
    records = _INTERVENTION_MEMORY.get(user_id, [])
    concept_records = [r for r in records if r.effective]
    if not concept_records:
        return "PRACTICAL_EXERCISE"

    best = max(concept_records, key=lambda r: r.score_delta)
    return best.strategy_type

def evaluate_intervention_effectiveness(
    concept: str,
    before_score: float,
    after_score: float,
    user_id: str = "default_user"
) -> Dict[str, Any]:
    """
    Evaluates whether an intervention succeeded (+points delta).
    Closes the self-correction loop (`GOAL -> MEASURE -> ACT -> RE-MEASURE -> ADAPT`).
    """
    delta = round(after_score - before_score, 1)
    effective = delta > 0.0

    record_intervention_memory(user_id, concept, "PRACTICAL_EXERCISE", before_score, after_score)

    return {
        "concept": concept,
        "before_score": before_score,
        "after_score": after_score,
        "score_delta": f"+{delta} pts" if delta >= 0 else f"{delta} pts",
        "effective": effective,
        "agent_decision": "CONTINUE_MONITORING" if effective else "CHANGE_STRATEGY"
    }
