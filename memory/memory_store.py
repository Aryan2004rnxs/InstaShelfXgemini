import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from utils import get_db_connection

logger = logging.getLogger("InstaShelf.memory.memory_store")

def is_sqlite(conn) -> bool:
    return "sqlite" in type(conn).__module__.lower()

def init_memory_table():
    """Initializes table for user agent memory across sessions."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if is_sqlite(conn):
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_agent_memory (
                    user_id TEXT PRIMARY KEY,
                    studied_topics TEXT NOT NULL DEFAULT '[]',
                    completed_missions TEXT NOT NULL DEFAULT '[]',
                    preferred_difficulty TEXT DEFAULT 'Intermediate',
                    memory_summary TEXT DEFAULT '',
                    last_updated TEXT NOT NULL
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_agent_memory (
                    user_id TEXT PRIMARY KEY,
                    studied_topics JSONB NOT NULL DEFAULT '[]'::jsonb,
                    completed_missions JSONB NOT NULL DEFAULT '[]'::jsonb,
                    preferred_difficulty TEXT DEFAULT 'Intermediate',
                    memory_summary TEXT DEFAULT '',
                    last_updated TEXT NOT NULL
                )
            """)
        conn.commit()
        conn.close()
        logger.info("User agent memory table initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize user_agent_memory table: {e}")

try:
    init_memory_table()
except Exception:
    pass

_LOCAL_MEMORY_CACHE: Dict[str, Dict[str, Any]] = {}

def get_user_memory(user_id: str = "default_user") -> Dict[str, Any]:
    if user_id in _LOCAL_MEMORY_CACHE:
        return _LOCAL_MEMORY_CACHE[user_id]

    default_mem = {
        "user_id": user_id,
        "studied_topics": [],
        "completed_missions": [],
        "preferred_difficulty": "Intermediate",
        "memory_summary": "User prefers concise explanations with practical examples.",
        "last_updated": ""
    }

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "?" if is_sqlite(conn) else "%s"
        cursor.execute(f"SELECT studied_topics, completed_missions, preferred_difficulty, memory_summary FROM user_agent_memory WHERE user_id = {param}", (user_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            topics = row[0] if isinstance(row[0], list) else json.loads(row[0]) if isinstance(row[0], str) else []
            missions = row[1] if isinstance(row[1], list) else json.loads(row[1]) if isinstance(row[1], str) else []
            mem = {
                "user_id": user_id,
                "studied_topics": topics,
                "completed_missions": missions,
                "preferred_difficulty": row[2] or "Intermediate",
                "memory_summary": row[3] or "",
                "last_updated": ""
            }
            _LOCAL_MEMORY_CACHE[user_id] = mem
            return mem
    except Exception as e:
        logger.warning(f"Failed to load user memory from DB: {e}")

    _LOCAL_MEMORY_CACHE[user_id] = default_mem
    return default_mem

def add_studied_topic(topic: str, user_id: str = "default_user"):
    mem = get_user_memory(user_id)
    if topic not in mem["studied_topics"]:
        mem["studied_topics"].append(topic)
        save_user_memory(mem, user_id)

def save_user_memory(mem: Dict[str, Any], user_id: str = "default_user") -> bool:
    now_str = datetime.utcnow().isoformat() + "Z"
    mem["last_updated"] = now_str
    _LOCAL_MEMORY_CACHE[user_id] = mem

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if is_sqlite(conn):
            cursor.execute("""
                INSERT OR REPLACE INTO user_agent_memory (user_id, studied_topics, completed_missions, preferred_difficulty, memory_summary, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                json.dumps(mem["studied_topics"]),
                json.dumps(mem["completed_missions"]),
                mem["preferred_difficulty"],
                mem["memory_summary"],
                now_str
            ))
        else:
            cursor.execute("""
                INSERT INTO user_agent_memory (user_id, studied_topics, completed_missions, preferred_difficulty, memory_summary, last_updated)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    studied_topics = EXCLUDED.studied_topics,
                    completed_missions = EXCLUDED.completed_missions,
                    preferred_difficulty = EXCLUDED.preferred_difficulty,
                    memory_summary = EXCLUDED.memory_summary,
                    last_updated = EXCLUDED.last_updated
            """, (
                user_id,
                json.dumps(mem["studied_topics"]),
                json.dumps(mem["completed_missions"]),
                mem["preferred_difficulty"],
                mem["memory_summary"],
                now_str
            ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to save user memory: {e}")
        return False
