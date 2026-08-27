import json
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("InstaShelf.services.goal_engine")

class SuccessContract(BaseModel):
    required_coverage_pct: float = Field(default=90.0, description="Minimum concept coverage percentage required")
    max_weak_concepts: int = Field(default=1, description="Maximum allowed unresolved weak concepts")
    min_benchmark_score: float = Field(default=80.0, description="Minimum benchmark test score percentage")
    max_unresolved_conflicts: int = Field(default=0, description="Maximum allowed unverified claim conflicts")

class MissionGoalEvaluation(BaseModel):
    goal_statement: str
    distance_to_goal: float = Field(description="Percentage distance to complete goal (0.0 = complete, 100.0 = not started)")
    achievement_percentage: float = Field(description="Percentage progress toward goal achievement (0.0 to 100.0%)")
    criteria_met: Dict[str, bool]
    weak_concepts: List[str]
    missing_prerequisites: List[str]
    recommended_interventions: List[str]
    is_achieved: bool = False
    stopping_statement: str = ""

def evaluate_mission_goal(
    goal_statement: str,
    completed_concepts: List[str],
    pending_concepts: List[str],
    quiz_benchmark_score: float = 75.0,
    unresolved_conflicts: int = 0,
    contract: Optional[SuccessContract] = None
) -> MissionGoalEvaluation:
    """
    Formally evaluates a Learning Mission's progress against its Goal Achievement Contract.
    Calculates exact Distance to Goal, checks criteria completion, and issues explicit stopping conditions.
    """
    if contract is None:
        contract = SuccessContract()

    total_concepts = max(len(completed_concepts) + len(pending_concepts), 1)
    coverage_pct = (len(completed_concepts) / total_concepts) * 100.0

    # Determine weak concepts
    weak_concepts = [c for c in pending_concepts if "evaluation" in c.lower() or "reranking" in c.lower()]
    if not weak_concepts and pending_concepts:
        weak_concepts = pending_concepts[:2]

    # Evaluate formal success criteria contract
    c1 = coverage_pct >= contract.required_coverage_pct
    c2 = len(weak_concepts) <= contract.max_weak_concepts
    c3 = quiz_benchmark_score >= contract.min_benchmark_score
    c4 = unresolved_conflicts <= contract.max_unresolved_conflicts

    criteria_met = {
        "concept_coverage_90_pct": c1,
        "weak_concepts_under_threshold": c2,
        "benchmark_score_80_pct": c3,
        "zero_claim_conflicts": c4
    }

    # Calculate overall achievement score
    achievement_pct = round(
        (coverage_pct * 0.4) + (min(quiz_benchmark_score, 100.0) * 0.4) + (100.0 if c2 and c4 else 50.0) * 0.2,
        1
    )
    distance_to_goal = round(100.0 - achievement_pct, 1)
    is_achieved = all(criteria_met.values()) or achievement_pct >= 85.0

    stopping = ""
    if is_achieved:
        stopping = "I consider your goal achieved. I'll continue monitoring for meaningful changes, but I won't keep generating material unnecessarily."

    interventions = []
    if not c1:
        interventions.append("Add foundational concept resources to complete curriculum coverage.")
    if not c2:
        interventions.append(f"Execute targeted practice session for weak concepts: {', '.join(weak_concepts)}")
    if not c3:
        interventions.append(f"Generate self-test benchmark quiz to raise score from {quiz_benchmark_score}% to 80%+")
    if not c4:
        interventions.append("Execute Claim Verification to resolve conflicting source claims.")

    return MissionGoalEvaluation(
        goal_statement=goal_statement,
        distance_to_goal=distance_to_goal,
        achievement_percentage=achievement_pct,
        criteria_met=criteria_met,
        weak_concepts=weak_concepts,
        missing_prerequisites=pending_concepts,
        recommended_interventions=interventions,
        is_achieved=is_achieved,
        stopping_statement=stopping
    )
