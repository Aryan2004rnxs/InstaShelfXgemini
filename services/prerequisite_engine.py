import logging
from typing import List, Dict, Any

logger = logging.getLogger("InstaShelf.prerequisite_engine")

class Tuple_Prereq:
    def __init__(self, prereqs: List[str], justification: str):
        self.prereqs = prereqs
        self.justification = justification

def infer_prerequisites(concept_name: str) -> Tuple_Prereq:
    key = concept_name.lower()

    if "rerank" in key:
        return (
            ["Vector Search & Embeddings", "Document Chunking"],
            "Cross-encoder reranking operates on candidates retrieved by foundational Vector Search."
        )
    elif "evaluation" in key or "eval" in key:
        return (
            ["Cross-Encoder Reranking", "Retrieval-Augmented Generation (RAG)"],
            "RAG evaluation metrics (Ragas/TruLens) assess precision of both retrieval and reranking stages."
        )
    elif "slam" in key or "navigation" in key:
        return (
            ["Sensor Fusion", "Robot Kinematics"],
            "Simultaneous Localization and Mapping (SLAM) requires sensor fusion inputs from IMU and LiDAR."
        )
    elif "sensor" in key:
        return (
            ["Robotics Fundamentals"],
            "Understanding raw sensor data streams is a prerequisite for multi-sensor data fusion."
        )
    else:
        return (
            ["Foundational Principles"],
            f"Core concepts must be understood before applying {concept_name} in complex systems."
        )

class Tuple_Prereq:
    def __init__(self, prereqs: List[str], justification: str):
        self.prereqs = prereqs
        self.justification = justification
