import asyncio
import logging
import sys
from datetime import datetime

# Setup sys.path
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("CartographerBenchmark")

from services.entity_extractor import extract_discovery_container
from services.entity_resolver import resolve_entities
from services.source_evaluator import evaluate_and_rank_candidates
from services.vector_retriever import evaluate_similarity_and_novelty
from services.knowledge_graph import mutate_graph, get_living_map, initialize_default_graph
from services.prerequisite_engine import infer_prerequisites
from services.path_engine import generate_consumption_path
from services.gap_detector import detect_knowledge_gaps
from services.proactive_scheduler import run_proactive_background_cartography
from models import DiscoveredEntity

async def run_20_cartography_scenarios():
    logger.info("=" * 70)
    logger.info("STARTING INSTASHELF AUTONOMOUS CARTOGRAPHER BENCHMARK (20 SCENARIOS)")
    logger.info("=" * 70)

    passed_count = 0
    total_scenarios = 20

    # Scenario 1: Multi-entity container extraction
    try:
        container = await extract_discovery_container("https://www.youtube.com/watch?v=upbh9dmrRRQ", "RAG & Vector Search")
        assert len(container.entities) >= 3
        logger.info("[PASS] Scenario 1: Multi-entity container extraction succeeded.")
        passed_count += 1
    except Exception as e:
        logger.error(f"[FAIL] Scenario 1: {e}")

    # Scenario 2: Canonical entity resolution
    try:
        raw_ent = DiscoveredEntity(entity_id="E1", canonical_name="GPT 4", entity_type="TECHNOLOGY")
        resolved = resolve_entities([raw_ent])[0]
        assert resolved.canonical_name == "GPT-4"
        logger.info("[PASS] Scenario 2: Canonical entity resolution succeeded.")
        passed_count += 1
    except Exception as e:
        logger.error(f"[FAIL] Scenario 2: {e}")

    # Scenario 3: Source candidate ranking
    try:
        primary, alts = evaluate_and_rank_candidates(resolved)
        assert primary.overall_score >= alts[0].overall_score
        logger.info("[PASS] Scenario 3: Source candidate ranking succeeded.")
        passed_count += 1
    except Exception as e:
        logger.error(f"[FAIL] Scenario 3: {e}")

    # Scenario 4: Similarity vs Novelty score calculation
    try:
        ent1 = DiscoveredEntity(entity_id="E1", canonical_name="Vector Search", entity_type="CONCEPT")
        ent2 = DiscoveredEntity(entity_id="E2", canonical_name="Vector Search", entity_type="CONCEPT")
        sim, nov, supp, reason = evaluate_similarity_and_novelty(ent1, [ent2])
        assert sim >= 90.0 and supp == True
        logger.info("[PASS] Scenario 4: Similarity vs Novelty score calculation succeeded.")
        passed_count += 1
    except Exception as e:
        logger.error(f"[FAIL] Scenario 4: {e}")

    # Scenario 5: Duplicate suppression ("Agent Says NO")
    try:
        assert supp == True and "AGENT DECISION" in reason
        logger.info("[PASS] Scenario 5: Duplicate suppression ('Agent Says NO') succeeded.")
        passed_count += 1
    except Exception as e:
        logger.error(f"[FAIL] Scenario 5: {e}")

    # Scenario 6: Graph CREATE mutation
    try:
        evt = mutate_graph("CREATE", "CLUST-NEW", "Created domain", ["Benchmark test"])
        assert evt.event_type == "CREATE"
        logger.info("[PASS] Scenario 6: Graph CREATE mutation succeeded.")
        passed_count += 1
    except Exception as e:
        logger.error(f"[FAIL] Scenario 6: {e}")

    # Scenario 7: Graph LINK mutation
    try:
        evt = mutate_graph("LINK", "CLUST-RAG", "Linked node", ["Benchmark test"])
        assert evt.event_type == "LINK"
        logger.info("[PASS] Scenario 7: Graph LINK mutation succeeded.")
        passed_count += 1
    except Exception as e:
        logger.error(f"[FAIL] Scenario 7: {e}")

    # Scenario 8: Graph MERGE mutation
    try:
        evt = mutate_graph("MERGE", "CLUST-RAG", "Merged clusters", ["Benchmark test"])
        assert evt.event_type == "MERGE"
        logger.info("[PASS] Scenario 8: Graph MERGE mutation succeeded.")
        passed_count += 1
    except Exception as e:
        logger.error(f"[FAIL] Scenario 8: {e}")

    # Scenario 9: Graph SPLIT mutation
    try:
        evt = mutate_graph("SPLIT", "CLUST-ROBOTICS", "Split cluster", ["Benchmark test"])
        assert evt.event_type == "SPLIT"
        logger.info("[PASS] Scenario 9: Graph SPLIT mutation succeeded.")
        passed_count += 1
    except Exception as e:
        logger.error(f"[FAIL] Scenario 9: {e}")

    # Scenario 10: Graph MOVE mutation
    try:
        evt = mutate_graph("MOVE", "CLUST-RAG", "Moved entity", ["Benchmark test"])
        assert evt.event_type == "MOVE"
        logger.info("[PASS] Scenario 10: Graph MOVE mutation succeeded.")
        passed_count += 1
    except Exception as e:
        logger.error(f"[FAIL] Scenario 10: {e}")

    # Scenario 11: Graph ARCHIVE mutation
    try:
        evt = mutate_graph("ARCHIVE", "CLUST-RAG", "Archived duplicate", ["Benchmark test"])
        assert evt.event_type == "ARCHIVE"
        logger.info("[PASS] Scenario 11: Graph ARCHIVE mutation succeeded.")
        passed_count += 1
    except Exception as e:
        logger.error(f"[FAIL] Scenario 11: {e}")

    # Scenario 12: Prerequisite DAG inference
    try:
        prereqs, just = infer_prerequisites("Cross-Encoder Reranking")
        assert len(prereqs) > 0
        logger.info("[PASS] Scenario 12: Prerequisite DAG inference succeeded.")
        passed_count += 1
    except Exception as e:
        logger.error(f"[FAIL] Scenario 12: {e}")

    # Scenario 13: Purpose-driven path generation (BALANCED)
    try:
        path = generate_consumption_path("RAG Architecture", mode="BALANCED")
        assert len(path) >= 3 and path[0].purpose == "FOUNDATION"
        logger.info("[PASS] Scenario 13: Purpose-driven path generation (BALANCED) succeeded.")
        passed_count += 1
    except Exception as e:
        logger.error(f"[FAIL] Scenario 13: {e}")

    # Scenario 14: Consumption path variant (DEEP)
    try:
        deep_path = generate_consumption_path("RAG Architecture", mode="DEEP")
        assert deep_path[-1].purpose == "REFERENCE"
        logger.info("[PASS] Scenario 14: Consumption path variant (DEEP) succeeded.")
        passed_count += 1
    except Exception as e:
        logger.error(f"[FAIL] Scenario 14: {e}")

    # Scenario 15: Knowledge gap detection
    try:
        gap_res = detect_knowledge_gaps("RAG", ["Vector Search"])
        assert gap_res["has_gaps"] == True
        logger.info("[PASS] Scenario 15: Knowledge gap detection succeeded.")
        passed_count += 1
    except Exception as e:
        logger.error(f"[FAIL] Scenario 15: {e}")

    # Scenario 16: Automated filler curation
    try:
        assert len(gap_res["fillers"]) > 0
        logger.info("[PASS] Scenario 16: Automated filler curation succeeded.")
        passed_count += 1
    except Exception as e:
        logger.error(f"[FAIL] Scenario 16: {e}")

    # Scenario 17: Proactive background cartography check
    try:
        pro_res = await run_proactive_background_cartography()
        assert pro_res["status"] == "success"
        logger.info("[PASS] Scenario 17: Proactive background cartography check succeeded.")
        passed_count += 1
    except Exception as e:
        logger.error(f"[FAIL] Scenario 17: {e}")

    # Scenario 18: Proactive source upgrade ("Agent found something better")
    try:
        assert pro_res["source_upgrade"]["new_score"] == 93
        logger.info("[PASS] Scenario 18: Proactive source upgrade succeeded.")
        passed_count += 1
    except Exception as e:
        logger.error(f"[FAIL] Scenario 18: {e}")

    # Scenario 19: Living map state fetch
    try:
        map_state = get_living_map()
        assert len(map_state["clusters"]) > 0 and len(map_state["history"]) > 0
        logger.info("[PASS] Scenario 19: Living map state fetch succeeded.")
        passed_count += 1
    except Exception as e:
        logger.error(f"[FAIL] Scenario 19: {e}")

    # Scenario 20: Full end-to-end cartographer workflow
    try:
        c = await extract_discovery_container("https://www.youtube.com/watch?v=upbh9dmrRRQ", "RAG & Vector Search")
        r = resolve_entities(c.entities)
        p, a = evaluate_and_rank_candidates(r[0])
        sim, nov, supp, reas = evaluate_similarity_and_novelty(r[0], [])
        evt = mutate_graph("LINK", "CLUST-RAG", "End to end test", ["Verification"])
        path = generate_consumption_path("RAG")
        assert len(path) > 0
        logger.info("[PASS] Scenario 20: Full end-to-end cartographer workflow succeeded.")
        passed_count += 1
    except Exception as e:
        logger.error(f"[FAIL] Scenario 20: {e}")

    logger.info("=" * 70)
    logger.info(f"BENCHMARK COMPLETED: {passed_count}/{total_scenarios} SCENARIOS PASSED ({int((passed_count/total_scenarios)*100)}%)")
    logger.info("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_20_cartography_scenarios())
