from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class DiscoveredEntity(BaseModel):
    entity_id: str
    canonical_name: str
    entity_type: str  # MOVIE, ANIME, BOOK, ARTICLE, VIDEO, PERSON, ORGANIZATION, TECHNOLOGY, CONCEPT
    aliases: List[str] = Field(default_factory=list)
    confidence_score: float = 0.95
    external_ids: Dict[str, str] = Field(default_factory=dict)  # youtube_id, tmdb_id, isbn, doi
    needs_verification: bool = False
    embedding: Optional[List[float]] = None

class SourceCandidate(BaseModel):
    candidate_id: str
    entity_id: str
    title: str
    url: str
    source_type: str  # YOUTUBE, TMDB, ARTICLE, BOOK
    scores: Dict[str, float] = Field(default_factory=dict)  # relevance, authority, depth, reception, popularity, recency
    overall_score: float = 85.0
    is_primary: bool = False
    designation: str = "MOST LIKELY PRIMARY SOURCE"  # VERIFIED PRIMARY SOURCE, MOST LIKELY PRIMARY SOURCE, BEST MATCHING SOURCE
    rejection_reason: Optional[str] = None
    evidence: List[str] = Field(default_factory=list)

class DiscoveryContainer(BaseModel):
    container_id: str
    input_url: str
    input_type: str = "REEL"  # REEL, POST, YOUTUBE_SHORT, ARTICLE, PDF, AUDIO
    raw_text: Optional[str] = ""
    media_refs: List[str] = Field(default_factory=list)
    status: str = "DISCOVERED"  # DISCOVERED, RESOLVING, RESEARCHING, EVALUATED, LINKED, COMPLETE
    entities: List[DiscoveredEntity] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

class MapEvolutionEvent(BaseModel):
    event_id: str
    cluster_id: str
    event_type: str  # CREATE, LINK, MERGE, SPLIT, MOVE, ARCHIVE
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    description: str
    evidence: List[str] = Field(default_factory=list)
    affected_nodes: List[str] = Field(default_factory=list)

class KnowledgeCluster(BaseModel):
    cluster_id: str
    name: str
    parent_cluster_id: Optional[str] = None
    entities: List[str] = Field(default_factory=list)
    subclusters: List[str] = Field(default_factory=list)
    version: int = 1
    embedding: Optional[List[float]] = None

class ConsumptionPathNode(BaseModel):
    step: int
    entity_id: str
    title: str
    url: str
    purpose: str = "CORE"  # FOUNDATION, INTUITION, CORE, PRACTICAL, APPLIED, DEEP_DIVE, REFERENCE
    difficulty: str = "INTERMEDIATE"
    prerequisites: List[str] = Field(default_factory=list)
    justification: str
    estimated_minutes: int = 15
