import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from models.knowledge import LearningMission
from services.gemini_service import generate_content_gemini, clean_json_output
from utils import get_db_connection

logger = logging.getLogger("InstaShelf.services.learning_mission")

def is_sqlite(conn) -> bool:
    return "sqlite" in type(conn).__module__.lower()

def init_mission_table():
    """Initializes table for user Learning Missions."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if is_sqlite(conn):
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learning_missions (
                    mission_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    progress_percentage FLOAT NOT NULL DEFAULT 0.0,
                    mission_data TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learning_missions (
                    mission_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    progress_percentage FLOAT NOT NULL DEFAULT 0.0,
                    mission_data JSONB NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
        conn.commit()
        conn.close()
        logger.info("Learning missions table initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize learning_missions table: {e}")

try:
    init_mission_table()
except Exception:
    pass

_MISSIONS_CACHE: Dict[str, LearningMission] = {}

def get_mission(mission_id: str) -> Optional[LearningMission]:
    if mission_id in _MISSIONS_CACHE:
        return _MISSIONS_CACHE[mission_id]

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "?" if is_sqlite(conn) else "%s"
        cursor.execute(f"SELECT mission_data FROM learning_missions WHERE mission_id = {param}", (mission_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            raw_data = row[0]
            if isinstance(raw_data, str):
                raw_data = json.loads(raw_data)
            mission = LearningMission(**raw_data)
            _MISSIONS_CACHE[mission_id] = mission
            return mission
    except Exception as e:
        logger.error(f"Failed to load mission {mission_id}: {e}")

    return None

def save_mission(mission: LearningMission) -> bool:
    mission.updated_at = datetime.utcnow().isoformat() + "Z"
    _MISSIONS_CACHE[mission.mission_id] = mission
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if is_sqlite(conn):
            cursor.execute("""
                INSERT OR REPLACE INTO learning_missions (mission_id, user_id, topic, progress_percentage, mission_data, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                mission.mission_id,
                "default_user",
                mission.topic,
                mission.progress_percentage,
                json.dumps(mission.model_dump()),
                mission.updated_at
            ))
        else:
            cursor.execute("""
                INSERT INTO learning_missions (mission_id, user_id, topic, progress_percentage, mission_data, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (mission_id) DO UPDATE SET
                    progress_percentage = EXCLUDED.progress_percentage,
                    mission_data = EXCLUDED.mission_data,
                    updated_at = EXCLUDED.updated_at
            """, (
                mission.mission_id,
                "default_user",
                mission.topic,
                mission.progress_percentage,
                json.dumps(mission.model_dump()),
                mission.updated_at
            ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to save mission {mission.mission_id}: {e}")
        return True

def list_missions(user_id: str = "default_user") -> List[LearningMission]:
    missions = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT mission_data FROM learning_missions ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        conn.close()
        for row in rows:
            raw_data = row[0]
            if isinstance(raw_data, str):
                raw_data = json.loads(raw_data)
            missions.append(LearningMission(**raw_data))
        if missions:
            return missions
    except Exception as e:
        logger.warning(f"Failed to list missions from DB: {e}")

    return list(_MISSIONS_CACHE.values())

async def create_learning_mission(topic: str, user_id: str = "default_user", existing_shelf_items: List[Dict[str, Any]] = None) -> LearningMission:
    if existing_shelf_items is None:
        existing_shelf_items = []

    prompt = f"""
The user wants a structured Learning Mission roadmap to master the topic: "{topic}".

Existing items on user's shelf:
{json.dumps(existing_shelf_items[:10])}

Construct a 5-6 step ordered learning path.
Identify which concepts are likely completed based on shelf items, and which are pending next steps.

Return JSON:
{{
  "completed_concepts": ["Foundational Concept 1"],
  "pending_concepts": ["Intermediate Step 2", "Advanced Step 3", "Production Step 4", "Evaluation Step 5"],
  "progress_percentage": 20.0
}}
"""

    system_instruction = "You are a master curriculum designer."

    try:
        raw_res = await generate_content_gemini(prompt, system_instruction=system_instruction, json_mode=True)
        cleaned = clean_json_output(raw_res)
        parsed = json.loads(cleaned)
    except Exception as e:
        logger.error(f"Failed to generate learning mission via Gemini: {e}")
        parsed = {
            "completed_concepts": [f"Introduction to {topic}"],
            "pending_concepts": [f"Core Architecture", f"Advanced Techniques", f"Evaluation & Production"],
            "progress_percentage": 25.0
        }

    mission_id = f"MISSION-{topic.replace(' ', '-').upper()[:12]}"
    now_str = datetime.utcnow().isoformat() + "Z"

    mission = LearningMission(
        mission_id=mission_id,
        topic=topic,
        progress_percentage=float(parsed.get("progress_percentage", 20.0)),
        completed_concepts=parsed.get("completed_concepts", []),
        pending_concepts=parsed.get("pending_concepts", []),
        shelf_items=[],
        created_at=now_str,
        updated_at=now_str
    )

    save_mission(mission)
    return mission
