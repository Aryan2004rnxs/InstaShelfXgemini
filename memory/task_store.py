import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from models.task import AgentTask, AgentState, TaskDecision, CandidateSource
from utils import get_db_connection

logger = logging.getLogger("InstaShelf.memory.task_store")

_IN_MEMORY_TASKS: Dict[str, AgentTask] = {}

def is_sqlite(conn) -> bool:
    return "sqlite" in type(conn).__module__.lower()

def init_task_table():
    """Initializes table for storing persistent agent task states."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if is_sqlite(conn):
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_tasks (
                    task_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    content_url TEXT NOT NULL,
                    learning_goal TEXT,
                    state TEXT NOT NULL,
                    current_step TEXT,
                    task_data TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_tasks (
                    task_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    content_url TEXT NOT NULL,
                    learning_goal TEXT,
                    state TEXT NOT NULL,
                    current_step TEXT,
                    task_data JSONB NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
        conn.commit()
        conn.close()
        logger.info("Agent tasks table initialized in database.")
    except Exception as e:
        logger.error(f"Failed to initialize agent_tasks table: {e}")

try:
    init_task_table()
except Exception:
    pass

def save_task(task: AgentTask) -> bool:
    """Saves or updates an AgentTask in persistent state (DB & in-memory cache)."""
    task.updated_at = datetime.utcnow().isoformat() + "Z"
    _IN_MEMORY_TASKS[task.task_id] = task

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        task_data_json = json.dumps(task.model_dump())
        state_str = task.state.value if isinstance(task.state, AgentState) else str(task.state)

        if is_sqlite(conn):
            cursor.execute("""
                INSERT OR REPLACE INTO agent_tasks (task_id, user_id, content_url, learning_goal, state, current_step, task_data, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.task_id,
                task.user_id,
                task.content_url,
                task.learning_goal or "",
                state_str,
                task.current_step,
                task_data_json,
                task.updated_at
            ))
        else:
            cursor.execute("""
                INSERT INTO agent_tasks (task_id, user_id, content_url, learning_goal, state, current_step, task_data, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (task_id) DO UPDATE SET
                    state = EXCLUDED.state,
                    current_step = EXCLUDED.current_step,
                    task_data = EXCLUDED.task_data,
                    updated_at = EXCLUDED.updated_at
            """, (
                task.task_id,
                task.user_id,
                task.content_url,
                task.learning_goal or "",
                state_str,
                task.current_step,
                task_data_json,
                task.updated_at
            ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning(f"Failed to save agent task to DB: {e}")
        return True

def get_task(task_id: str) -> Optional[AgentTask]:
    """Retrieves an AgentTask by ID from in-memory cache or DB."""
    if task_id in _IN_MEMORY_TASKS:
        return _IN_MEMORY_TASKS[task_id]

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "?" if is_sqlite(conn) else "%s"
        cursor.execute(f"SELECT task_data FROM agent_tasks WHERE task_id = {param}", (task_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            raw_data = row[0]
            if isinstance(raw_data, str):
                raw_data = json.loads(raw_data)
            task = AgentTask(**raw_data)
            _IN_MEMORY_TASKS[task_id] = task
            return task
    except Exception as e:
        logger.error(f"Failed to retrieve agent task {task_id} from DB: {e}")

    return None

def list_recent_tasks(limit: int = 20) -> List[AgentTask]:
    """Lists the most recent agent tasks."""
    tasks: List[AgentTask] = []
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "?" if is_sqlite(conn) else "%s"
        cursor.execute(f"SELECT task_data FROM agent_tasks ORDER BY updated_at DESC LIMIT {param}", (limit,))
        rows = cursor.fetchall()
        conn.close()

        for row in rows:
            raw_data = row[0]
            if isinstance(raw_data, str):
                raw_data = json.loads(raw_data)
            tasks.append(AgentTask(**raw_data))
        
        if tasks:
            return tasks
    except Exception as e:
        logger.warning(f"Failed to fetch recent tasks from DB: {e}")

    sorted_mem = sorted(_IN_MEMORY_TASKS.values(), key=lambda t: t.updated_at, reverse=True)
    return sorted_mem[:limit]

def add_task_decision(
    task_id: str,
    agent: str,
    action: str,
    reasoning: str,
    tool_input: Optional[Dict[str, Any]] = None,
    tool_output_summary: Optional[str] = None
):
    task = get_task(task_id)
    if not task:
        logger.error(f"Cannot add decision to missing task_id: {task_id}")
        return

    decision = TaskDecision(
        timestamp=datetime.utcnow().isoformat() + "Z",
        agent=agent,
        action=action,
        reasoning=reasoning,
        tool_input=tool_input,
        tool_output_summary=tool_output_summary
    )
    task.decisions.append(decision)
    save_task(task)
