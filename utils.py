import os
import logging
import asyncio
import json
import psycopg2
import psycopg2.extras

# Force native gRPC DNS resolution to fix macOS DNS lookup failures
os.environ["GRPC_DNS_RESOLVER"] = "native"

# Fix SSL CA Bundle paths overridden by Hugging Face Spaces (causes SSLError in containers)
for var in ["CURL_CA_BUNDLE", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"]:
    if var in os.environ:
        del os.environ[var]
from datetime import datetime
from functools import wraps
from typing import Callable, Any, Type, Tuple, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

# Configure logging
LOG_LEVEL_STR = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger("InstaShelf")

# DB Configuration path
SUPABASE_DATABASE_URL = os.getenv("SUPABASE_DATABASE_URL")

db_pool = None
if SUPABASE_DATABASE_URL:
    try:
        from psycopg2.pool import ThreadedConnectionPool
        # Pool size min 1, max 20 connections
        db_pool = ThreadedConnectionPool(1, 20, SUPABASE_DATABASE_URL)
        logger.info("Created PostgreSQL ThreadedConnectionPool")
    except Exception as e:
        logger.error(f"Failed to create database connection pool: {e}")

class PooledConnection:
    def __init__(self, pool):
        self._pool = pool
        self._conn = pool.getconn()
    
    def __getattr__(self, item):
        return getattr(self._conn, item)
    
    def close(self):
        self._pool.putconn(self._conn)

def get_db_connection():
    if db_pool:
        try:
            return PooledConnection(db_pool)
        except Exception as pool_err:
            logger.warning(f"ThreadedConnectionPool error, falling back to sqlite: {pool_err}")
    if SUPABASE_DATABASE_URL:
        try:
            return psycopg2.connect(SUPABASE_DATABASE_URL)
        except Exception as pg_err:
            logger.warning(f"PostgreSQL connection error, falling back to local SQLite: {pg_err}")
    # Local fallback to SQLite database file
    import sqlite3
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect("data/instashelf.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the Supabase PostgreSQL database for quota tracking and offline fallback cache."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Table for tracking Gemini daily requests quota
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gemini_quota (
                date TEXT PRIMARY KEY,
                count INTEGER NOT NULL DEFAULT 0
            )
        """)
        
        # Table for tracking Groq daily requests quota
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS groq_quota (
                date TEXT PRIMARY KEY,
                count INTEGER NOT NULL DEFAULT 0
            )
        """)
        
        # Table for storing offline google sheets cache rows when writes fail
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_rows (
                id SERIAL PRIMARY KEY,
                row_data TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # Table for storing user interaction progress (YouTube watch time, read status)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_progress (
                content_hash TEXT PRIMARY KEY,
                progress_seconds INTEGER NOT NULL DEFAULT 0,
                is_completed BOOLEAN NOT NULL DEFAULT FALSE,
                last_updated TEXT NOT NULL
            )
        """)
        
        # Table for storing user video timestamp notes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS video_notes (
                id SERIAL PRIMARY KEY,
                content_hash TEXT NOT NULL,
                timestamp_seconds INTEGER NOT NULL,
                note_text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info("Supabase PostgreSQL database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL database: {e}")

# Call init_db on import
if SUPABASE_DATABASE_URL:
    init_db()

def get_current_date() -> str:
    """Returns today's date formatted as YYYY-MM-DD."""
    return datetime.utcnow().strftime("%Y-%m-%d")

# Gemini Quota Tracking Functions
def get_gemini_usage(date_str: str = None) -> int:
    """Gets the Gemini request count for a given date."""
    if date_str is None:
        date_str = get_current_date()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "?" if is_sqlite(conn) else "%s"
        cursor.execute(f"SELECT count FROM gemini_quota WHERE date = {param}", (date_str,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 0
    except Exception as e:
        logger.warning(f"Error reading Gemini usage from database: {e}")
        return 0

def increment_gemini_usage(date_str: str = None) -> int:
    """Increments and returns the Gemini request count for a given date."""
    if date_str is None:
        date_str = get_current_date()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if is_sqlite(conn):
            cursor.execute("INSERT INTO gemini_quota (date, count) VALUES (?, 1) ON CONFLICT(date) DO UPDATE SET count = count + 1", (date_str,))
            cursor.execute("SELECT count FROM gemini_quota WHERE date = ?", (date_str,))
            row = cursor.fetchone()
        else:
            cursor.execute("INSERT INTO gemini_quota (date, count) VALUES (%s, 1) ON CONFLICT(date) DO UPDATE SET count = gemini_quota.count + 1 RETURNING count", (date_str,))
            row = cursor.fetchone()
        conn.commit()
        conn.close()
        new_count = row[0] if row else 1
        logger.info(f"Gemini daily quota usage: {new_count}/20 for {date_str}")
        return new_count
    except Exception as e:
        logger.warning(f"Error incrementing Gemini usage in database: {e}")
        return 0

# Groq Quota Tracking Functions
def get_groq_usage(date_str: str = None) -> int:
    """Gets the Groq request count for a given date."""
    if date_str is None:
        date_str = get_current_date()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "?" if is_sqlite(conn) else "%s"
        cursor.execute(f"SELECT count FROM groq_quota WHERE date = {param}", (date_str,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else 0
    except Exception as e:
        logger.warning(f"Error reading Groq usage from database: {e}")
        return 0

def increment_groq_usage(date_str: str = None) -> int:
    """Increments and returns the Groq request count for a given date."""
    if date_str is None:
        date_str = get_current_date()
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if is_sqlite(conn):
            cursor.execute("INSERT INTO groq_quota (date, count) VALUES (?, 1) ON CONFLICT(date) DO UPDATE SET count = count + 1", (date_str,))
            cursor.execute("SELECT count FROM groq_quota WHERE date = ?", (date_str,))
            row = cursor.fetchone()
        else:
            cursor.execute("INSERT INTO groq_quota (date, count) VALUES (%s, 1) ON CONFLICT(date) DO UPDATE SET count = groq_quota.count + 1 RETURNING count", (date_str,))
            row = cursor.fetchone()
        conn.commit()
        conn.close()
        new_count = row[0] if row else 1
        logger.info(f"Groq daily quota usage: {new_count}/1000 for {date_str}")
        return new_count
    except Exception as e:
        logger.warning(f"Error incrementing Groq usage in database: {e}")
        return 0

def is_sqlite(conn) -> bool:
    return "sqlite" in type(conn).__module__.lower()

# Local Shelf Storage Functions
def save_local_shelf_row(row_dict: dict) -> bool:
    """Saves a row to the local database store for instant UI rendering."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "?" if is_sqlite(conn) else "%s"
        
        # Create table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS local_shelf_items (
                content_hash TEXT PRIMARY KEY,
                row_data TEXT,
                saved_at TEXT
            )
        """)
        
        data_str = json.dumps(row_dict)
        content_hash = row_dict.get("content_hash", str(datetime.utcnow().timestamp()))
        now_str = datetime.utcnow().isoformat()
        
        if is_sqlite(conn):
            cursor.execute(
                "INSERT OR REPLACE INTO local_shelf_items (content_hash, row_data, saved_at) VALUES (?, ?, ?)",
                (content_hash, data_str, now_str)
            )
        else:
            cursor.execute(
                "INSERT INTO local_shelf_items (content_hash, row_data, saved_at) VALUES (%s, %s, %s) ON CONFLICT (content_hash) DO UPDATE SET row_data = EXCLUDED.row_data",
                (content_hash, data_str, now_str)
            )
        conn.commit()
        conn.close()
        logger.info(f"Saved row '{row_dict.get('title')}' to local_shelf_items database.")
        return True
    except Exception as e:
        logger.warning(f"Failed to save local shelf row: {e}")
        return False

def get_local_shelf_rows() -> List[dict]:
    """Retrieves all rows stored in local_shelf_items."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS local_shelf_items (content_hash TEXT PRIMARY KEY, row_data TEXT, saved_at TEXT)")
        cursor.execute("SELECT row_data FROM local_shelf_items ORDER BY saved_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [json.loads(r[0]) for r in rows if r[0]]
    except Exception as e:
        logger.warning(f"Failed to fetch local_shelf_items: {e}")
        return []

# Sheets Caching Functions
def cache_pending_row(row_dict: dict) -> bool:
    """Saves a row to the offline database queue to retry writing to Google Sheets later."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        data_str = json.dumps(row_dict)
        now_str = datetime.utcnow().isoformat()
        param = "?" if is_sqlite(conn) else "%s"
        cursor.execute(
            f"INSERT INTO pending_rows (row_data, created_at) VALUES ({param}, {param})",
            (data_str, now_str)
        )
        conn.commit()
        conn.close()
        logger.info("Saved row to offline pending_rows cache.")
        return True
    except Exception as e:
        logger.warning(f"Failed to cache pending row to database: {e}")
        return True

def get_pending_rows() -> List[Tuple[int, dict]]:
    """Retrieves all pending rows from the offline Postgres queue."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, row_data FROM pending_rows ORDER BY id ASC")
        rows = cursor.fetchall()
        conn.close()
        
        parsed_rows = []
        for row_id, data_str in rows:
            try:
                parsed_rows.append((row_id, json.loads(data_str)))
            except Exception as pe:
                logger.error(f"Failed to parse offline row {row_id}: {pe}")
        return parsed_rows
    except Exception as e:
        logger.error(f"Failed to get pending rows from Postgres: {e}")
        return []

def delete_pending_row(row_id: int) -> bool:
    """Deletes a successfully synced row from the offline database queue."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        param = "?" if is_sqlite(conn) else "%s"
        cursor.execute(f"DELETE FROM pending_rows WHERE id = {param}", (row_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to delete pending row {row_id} from database: {e}")
        return False

# Async Retry Decorator
def retry_async(
    retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,)
):
    """Decorator to retry asynchronous functions with exponential backoff."""
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            for attempt in range(1, retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == retries:
                        logger.error(f"Function {func.__name__} failed after {retries} attempts. Exception: {e}")
                        raise
                    logger.warning(
                        f"Attempt {attempt}/{retries} for {func.__name__} failed: {e}. "
                        f"Retrying in {current_delay:.2f} seconds..."
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator
