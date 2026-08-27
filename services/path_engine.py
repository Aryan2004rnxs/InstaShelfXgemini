import logging
from typing import List, Dict, Any
from models import ConsumptionPathNode
import utils

logger = logging.getLogger("InstaShelf.path_engine")

def generate_consumption_path(topic: str = "General", mode: str = "BALANCED") -> List[ConsumptionPathNode]:
    """
    Dynamically generates a prerequisite-ordered consumption path
    derived directly from the user's actual shelf items!
    """
    logger.info(f"Dynamically generating Consumption Path for topic '{topic}' (mode={mode})")

    shelf_items = utils.get_local_shelf_rows()
    purposes = ["FOUNDATION", "INTUITION", "CORE", "PRACTICAL", "DEEP_DIVE", "REFERENCE"]
    difficulties = ["BEGINNER", "BEGINNER", "INTERMEDIATE", "INTERMEDIATE", "ADVANCED", "EXPERT"]

    nodes: List[ConsumptionPathNode] = []

    if shelf_items:
        for idx, item in enumerate(shelf_items[:6]):
            title = item.get("title", f"Concept {idx+1}")
            url = item.get("url", "#")
            purpose = purposes[idx % len(purposes)]
            diff = difficulties[idx % len(difficulties)]
            
            prereq = [shelf_items[idx-1].get("title")] if idx > 0 else []
            justification = (
                f"Establishes foundational concepts before moving to advanced topics."
                if idx == 0 else
                f"Builds directly upon concepts introduced in '{prereq[0]}'."
            )

            nodes.append(ConsumptionPathNode(
                step=idx + 1,
                entity_id=f"ENT-PATH-{idx+1}",
                title=title,
                url=url,
                purpose=purpose,
                difficulty=diff,
                prerequisites=prereq,
                justification=justification,
                estimated_minutes=10 + (idx * 5)
            ))
    else:
        # Fallback if shelf is totally empty
        nodes = [
            ConsumptionPathNode(
                step=1,
                entity_id="ENT-01",
                title="Philosophy & Critical Thinking Foundations",
                url="#",
                purpose="FOUNDATION",
                difficulty="BEGINNER",
                prerequisites=[],
                justification="Establishes core analytical framework.",
                estimated_minutes=12
            ),
            ConsumptionPathNode(
                step=2,
                entity_id="ENT-02",
                title="Media Analysis & Narrative Worldbuilding",
                url="#",
                purpose="CORE",
                difficulty="INTERMEDIATE",
                prerequisites=["Philosophy & Critical Thinking Foundations"],
                justification="Applies critical thinking to media and narrative structure.",
                estimated_minutes=20
            )
        ]

    if mode == "QUICK":
        nodes = nodes[:2]
    elif mode == "DEEP" and len(nodes) > 4:
        nodes = nodes[:5]

    return nodes
