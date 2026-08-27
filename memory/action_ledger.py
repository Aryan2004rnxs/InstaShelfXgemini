import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from utils import get_db_connection

logger = logging.getLogger("InstaShelf.memory.action_ledger")

class ActionLedgerEntry(BaseModel):
    action_id: str
    task_id: str
    mission_id: Optional[str] = None
    agent: str
    tool: str
    timestamp: str
    input_summary: Dict[str, Any]
    output_summary: str
    risk_level: str = "LOW"
    approval_status: str = "AUTOMATIC"
    verification_status: str = "VERIFIED"
    idempotency_key: str

_IN_MEMORY_LEDGER: List[ActionLedgerEntry] = []

def is_sqlite(conn) -> bool:
    return "sqlite" in type(conn).__module__.lower()

def init_ledger_table():
    """Initializes persistent append-only action ledger table in DB."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if is_sqlite(conn):
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS action_ledger (
                    action_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    mission_id TEXT,
                    agent TEXT NOT NULL,
                    tool TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    input_summary TEXT NOT NULL,
                    output_summary TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    approval_status TEXT NOT NULL,
                    verification_status TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE NOT NULL
                )
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS action_ledger (
                    action_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    mission_id TEXT,
                    agent TEXT NOT NULL,
                    tool TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    input_summary JSONB NOT NULL,
                    output_summary TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    approval_status TEXT NOT NULL,
                    verification_status TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE NOT NULL
                )
            """)
        conn.commit()
        conn.close()
        logger.info("Append-only action ledger table initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize action_ledger table: {e}")

try:
    init_ledger_table()
except Exception:
    pass

def record_action(
    task_id: str,
    agent: str,
    tool: str,
    input_summary: Dict[str, Any],
    output_summary: str,
    idempotency_key: str,
    mission_id: Optional[str] = None,
    risk_level: str = "LOW",
    approval_status: str = "AUTOMATIC",
    verification_status: str = "VERIFIED"
) -> ActionLedgerEntry:
    """Records an operational action in the append-only Action Ledger."""
    action_id = f"ACT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{os.urandom(2).hex()}"
    timestamp = datetime.utcnow().isoformat() + "Z"

    entry = ActionLedgerEntry(
        action_id=action_id,
        task_id=task_id,
        mission_id=mission_id,
        agent=agent,
        tool=tool,
        timestamp=timestamp,
        input_summary=input_summary,
        output_summary=output_summary,
        risk_level=risk_level,
        approval_status=approval_status,
        verification_status=verification_status,
        idempotency_key=idempotency_key
    )
    _IN_MEMORY_LEDGER.append(entry)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param_str = "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?" if is_sqlite(conn) else "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s"
        cursor.execute(f"""
            INSERT INTO action_ledger (action_id, task_id, mission_id, agent, tool, timestamp, input_summary, output_summary, risk_level, approval_status, verification_status, idempotency_key)
            VALUES ({param_str})
        """, (
            action_id,
            task_id,
            mission_id or "",
            agent,
            tool,
            timestamp,
            json.dumps(input_summary),
            output_summary,
            risk_level,
            approval_status,
            verification_status,
            idempotency_key
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Note: Saved action {action_id} to in-memory ledger ({e})")

    return entry

def get_action_ledger(limit: int = 50) -> List[ActionLedgerEntry]:
    """Retrieves recent entries from the append-only action ledger."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "?" if is_sqlite(conn) else "%s"
        cursor.execute(f"SELECT action_id, task_id, mission_id, agent, tool, timestamp, input_summary, output_summary, risk_level, approval_status, verification_status, idempotency_key FROM action_ledger ORDER BY timestamp DESC LIMIT {param}", (limit,))
        rows = cursor.fetchall()
        conn.close()

        entries = []
        for r in rows:
            inp = r[6] if isinstance(r[6], dict) else json.loads(r[6]) if isinstance(r[6], str) else {}
            entries.append(ActionLedgerEntry(
                action_id=r[0],
                task_id=r[1],
                mission_id=r[2],
                agent=r[3],
                tool=r[4],
                timestamp=r[5],
                input_summary=inp,
                output_summary=r[7],
                risk_level=r[8],
                approval_status=r[9],
                verification_status=r[10],
                idempotency_key=r[11]
            ))
        if entries:
            return entries
    except Exception as e:
        logger.warning(f"Failed to fetch action ledger from DB: {e}")

    return sorted(_IN_MEMORY_LEDGER, key=lambda x: x.timestamp, reverse=True)[:limit]
