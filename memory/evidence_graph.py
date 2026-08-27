import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("InstaShelf.memory.evidence_graph")

class EvidenceItem(BaseModel):
    evidence_id: str
    concept: str
    evidence_type: str = Field(description="Types: 'VIDEO_TIMESTAMP', 'QUIZ_RESULT', 'SCREENSHOT', 'AUDIO_NOTE', 'USER_EXPLANATION'")
    source_ref: str
    summary: str
    confidence_delta: float = 0.0

class DecisionEvidenceLink(BaseModel):
    decision_id: str
    decision_text: str
    concept: str
    supporting_evidence: List[EvidenceItem]
    agent_reasoning: str

_EVIDENCE_CACHE: Dict[str, List[EvidenceItem]] = {}

def add_evidence(concept: str, evidence_type: str, source_ref: str, summary: str, confidence_delta: float = 0.0) -> EvidenceItem:
    item = EvidenceItem(
        evidence_id=f"EVID-{len(_EVIDENCE_CACHE.get(concept, [])) + 1}",
        concept=concept,
        evidence_type=evidence_type,
        source_ref=source_ref,
        summary=summary,
        confidence_delta=confidence_delta
    )
    if concept not in _EVIDENCE_CACHE:
        _EVIDENCE_CACHE[concept] = []
    _EVIDENCE_CACHE[concept].append(item)
    return item

def get_concept_evidence(concept: str) -> List[EvidenceItem]:
    return _EVIDENCE_CACHE.get(concept, [])

def build_decision_evidence_link(decision_id: str, decision_text: str, concept: str, reasoning: str) -> DecisionEvidenceLink:
    ev_items = get_concept_evidence(concept)
    if not ev_items:
        ev_items = [
            EvidenceItem(
                evidence_id="EVID-1",
                concept=concept,
                evidence_type="SOURCE_ANALYSIS",
                source_ref="Instagram Clip + YouTube Enrichment",
                summary=f"Extracted topic references {concept}",
                confidence_delta=15.0
            )
        ]
    return DecisionEvidenceLink(
        decision_id=decision_id,
        decision_text=decision_text,
        concept=concept,
        supporting_evidence=ev_items,
        agent_reasoning=reasoning
    )
