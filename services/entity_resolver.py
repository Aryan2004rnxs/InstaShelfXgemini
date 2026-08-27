import logging
from typing import List
from models import DiscoveredEntity

logger = logging.getLogger("InstaShelf.entity_resolver")

# Canonical Alias Mapping Dictionary
CANONICAL_DICTIONARY = {
    "gpt 4": ("GPT-4", "TECHNOLOGY"),
    "gpt-4": ("GPT-4", "TECHNOLOGY"),
    "openai gpt-4": ("GPT-4", "TECHNOLOGY"),
    "rag": ("Retrieval-Augmented Generation (RAG)", "TECHNOLOGY"),
    "retrieval augmented generation": ("Retrieval-Augmented Generation (RAG)", "TECHNOLOGY"),
    "psycho pass": ("Psycho-Pass", "ANIME"),
    "psycho-pass": ("Psycho-Pass", "ANIME"),
    "2001 a space odyssey": ("2001: A Space Odyssey", "MOVIE"),
    "vector search": ("Vector Search & Embeddings", "CONCEPT"),
    "cross encoder": ("Cross-Encoder Reranking", "CONCEPT"),
    "reranking": ("Cross-Encoder Reranking", "CONCEPT"),
    "rag evaluation": ("RAG Evaluation & Benchmarking", "CONCEPT"),
}

def resolve_entities(entities: List[DiscoveredEntity]) -> List[DiscoveredEntity]:
    """
    Normalizes extracted raw entities into canonical representations
    and sets verification flags for low-confidence matches.
    """
    resolved_list = []
    for ent in entities:
        key = ent.canonical_name.strip().lower()
        if key in CANONICAL_DICTIONARY:
            canon_name, canon_type = CANONICAL_DICTIONARY[key]
            ent.aliases.append(ent.canonical_name)
            ent.canonical_name = canon_name
            ent.entity_type = canon_type
            ent.confidence_score = min(1.0, ent.confidence_score + 0.05)
            ent.needs_verification = False
        else:
            if ent.confidence_score < 0.8:
                ent.needs_verification = True
                logger.info(f"Entity '{ent.canonical_name}' flagged for human verification (confidence={ent.confidence_score}).")
        resolved_list.append(ent)
    return resolved_list
