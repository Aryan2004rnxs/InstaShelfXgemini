import logging
import math
from typing import List, Dict, Any, Tuple
from models import DiscoveredEntity

logger = logging.getLogger("InstaShelf.vector_retriever")

# Simple local deterministic embedding generator for local dev fallback
def generate_deterministic_embedding(text: str) -> List[float]:
    """Generates a normalized 16-dimensional vector embedding for text."""
    seed = sum(ord(c) for c in text)
    raw = [math.sin(seed + i) for i in range(16)]
    norm = math.sqrt(sum(x * x for x in raw)) or 1.0
    return [x / norm for x in raw]

def compute_cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Computes cosine similarity between two 16-dim vectors (0.0 to 1.0)."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.5
    dot = sum(a * b for a, b in zip(vec1, vec2))
    return max(0.0, min(1.0, dot))

def evaluate_similarity_and_novelty(
    new_entity: DiscoveredEntity, 
    existing_entities: List[DiscoveredEntity]
) -> Tuple[float, float, bool, str]:
    """
    Computes Similarity and Novelty scores for a new entity against existing knowledge.
    Returns: (similarity_score, novelty_score, is_suppressed, suppression_reason)
    """
    if not new_entity.embedding:
        new_entity.embedding = generate_deterministic_embedding(new_entity.canonical_name)

    max_sim = 0.0
    matching_entity_name = None

    for existing in existing_entities:
        if not existing.embedding:
            existing.embedding = generate_deterministic_embedding(existing.canonical_name)
        
        sim = compute_cosine_similarity(new_entity.embedding, existing.embedding)
        # Exact title string match boost
        if new_entity.canonical_name.lower() == existing.canonical_name.lower():
            sim = 0.96
        
        if sim > max_sim:
            max_sim = sim
            matching_entity_name = existing.canonical_name

    similarity_score = round(max_sim * 100, 1)
    novelty_score = round((1.0 - max_sim) * 100, 1)

    # Intelligent Duplicate Suppression Logic ("Agent Says NO")
    # If Similarity >= 90% and Novelty < 15%, suppress as duplicate!
    is_suppressed = similarity_score >= 90.0 and novelty_score < 15.0
    suppression_reason = None

    if is_suppressed:
        suppression_reason = (
            f"AGENT DECISION — NOT ADDED (Suppressed): Similarity: {similarity_score}%, Novelty: {novelty_score}%. "
            f"Existing knowledge cluster already covers '{matching_entity_name}' with high mastery."
        )
        logger.info(f"Duplicate suppressed: {new_entity.canonical_name} ({suppression_reason})")
    else:
        logger.info(f"Entity accepted: {new_entity.canonical_name} (Similarity: {similarity_score}%, Novelty: {novelty_score}%)")

    return similarity_score, novelty_score, is_suppressed, suppression_reason
