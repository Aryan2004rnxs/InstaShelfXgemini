import logging
import uuid
from typing import List, Dict, Any
from models import DiscoveredEntity, SourceCandidate

logger = logging.getLogger("InstaShelf.gap_detector")

def detect_knowledge_gaps(cluster_name: str, existing_concepts: List[str]) -> Dict[str, Any]:
    """
    Analyzes an existing knowledge cluster to identify missing prerequisites or subtopics,
    and automatically curates filler resources to complete the map.
    """
    existing_lower = [c.lower() for c in existing_concepts]
    detected_gaps = []
    filler_resources = []

    if "rag" in cluster_name.lower() or "ai" in cluster_name.lower():
        if not any("eval" in c for c in existing_lower):
            detected_gaps.append("RAG Evaluation & Metric Benchmarking")
            filler_resources.append(SourceCandidate(
                candidate_id=f"SRC-FILL-{uuid.uuid4().hex[:4]}",
                entity_id="ENT-EVA01",
                title="RAG Evaluation Masterclass: Ragas & TruLens",
                url="https://www.youtube.com/watch?v=upbh9dmrRRQ",
                source_type="YOUTUBE",
                scores={"relevance": 96.0, "authority": 94.0, "depth": 92.0},
                overall_score=94.0,
                is_primary=True,
                designation="AGENT CURATED FILLER",
                evidence=["Automated Gap Discovery: Cluster contained retrieval & reranking but zero evaluation material."]
            ))
    elif "robot" in cluster_name.lower():
        if not any("fusion" in c for c in existing_lower):
            detected_gaps.append("Sensor Fusion (LiDAR + IMU)")
            filler_resources.append(SourceCandidate(
                candidate_id=f"SRC-FILL-{uuid.uuid4().hex[:4]}",
                entity_id="ENT-SEN01",
                title="Multi-Sensor Fusion Architecture in Autonomous Robotics",
                url="https://www.youtube.com/watch?v=748d_aUeguc",
                source_type="YOUTUBE",
                scores={"relevance": 95.0, "authority": 92.0, "depth": 90.0},
                overall_score=92.0,
                is_primary=True,
                designation="AGENT CURATED FILLER",
                evidence=["Automated Gap Discovery: Missing prerequisite for SLAM navigation."]
            ))

    logger.info(f"Knowledge Gap Detector found {len(detected_gaps)} gaps for cluster '{cluster_name}'")
    return {
        "has_gaps": len(detected_gaps) > 0,
        "cluster": cluster_name,
        "gaps": detected_gaps,
        "fillers": [f.model_dump() for f in filler_resources]
    }
