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

def seed_initial_shelf_items():
    """Populates 25 rich seed items across all 5 knowledge domains into local database."""
    items = [
        # Domain 1: Storytelling, Communication & Worldbuilding
        {
            "saved_at": "2026-08-27T10:00:00",
            "source_type": "YOUTUBE",
            "content_type": "VIDEO",
            "title": "Speaking Articulately & Master Public Speaking",
            "creator": "Julian Treasure",
            "url": "https://www.youtube.com/watch?v=eIho2S0ZahI",
            "thumbnail_url": "https://img.youtube.com/vi/eIho2S0ZahI/hqdefault.jpg",
            "confidence": 0.98,
            "instagram_url": "",
            "raw_context": "How to speak so that people want to listen. Vocal warmups and pacing.",
            "ai_summary": "7 habits to avoid and 4 cornerstone principles for powerful public speaking and articulation.",
            "content_hash": "SEED-STORY-001",
            "status": "COMPLETED",
            "gemini_notes": "Key takeaway: HAIL - Honesty, Authenticity, Integrity, Love in vocal delivery.",
            "tags": "Storytelling,Public Speaking,Communication,Voice"
        },
        {
            "saved_at": "2026-08-27T10:30:00",
            "source_type": "ARTICLE",
            "content_type": "READING",
            "title": "Pixar's 22 Rules of Storytelling & Narrative Structure",
            "creator": "Pixar Animation Studio",
            "url": "https://www.storygrid.com/pixars-22-rules-of-storytelling/",
            "thumbnail_url": "",
            "confidence": 0.96,
            "instagram_url": "",
            "raw_context": "Core principles behind Pixar's emotional resonance and character arcs.",
            "ai_summary": "Guide to building stakes, emotional character growth, and narrative clarity.",
            "content_hash": "SEED-STORY-002",
            "status": "IN_PROGRESS",
            "gemini_notes": "Key takeaway: You admire a character for trying more than for their successes.",
            "tags": "Storytelling,Narrative,Worldbuilding,Creative Writing"
        },
        {
            "saved_at": "2026-08-27T11:00:00",
            "source_type": "INSTAGRAM",
            "content_type": "REEL",
            "title": "The Art of Storytelling in Tech & Product Demos",
            "creator": "Designcraft",
            "url": "https://www.instagram.com/reel/C-sample1",
            "thumbnail_url": "",
            "confidence": 0.94,
            "instagram_url": "https://www.instagram.com/reel/C-sample1",
            "raw_context": "How narrative structure drives user engagement and product adoption.",
            "ai_summary": "Breakdown of hero's journey framing in developer UI/UX and product demos.",
            "content_hash": "SEED-STORY-003",
            "status": "UNREAD",
            "gemini_notes": "Key takeaway: Good UX tells a cohesive story with clear progressive disclosure.",
            "tags": "Storytelling,UX Design,Communication"
        },
        {
            "saved_at": "2026-08-27T11:15:00",
            "source_type": "BOOK",
            "content_type": "READING",
            "title": "Wired for Story: The Writer's Guide to Brain Science",
            "creator": "Lisa Cron",
            "url": "https://www.amazon.com/Wired-Story-Writers-Science-Storytelling/dp/1607742454",
            "thumbnail_url": "",
            "confidence": 0.95,
            "instagram_url": "",
            "raw_context": "Neurological basis of narrative comprehension and emotional connection.",
            "ai_summary": "How the brain processes story as an evolutionary survival mechanism.",
            "content_hash": "SEED-STORY-004",
            "status": "COMPLETED",
            "gemini_notes": "Key takeaway: Stories help us simulate high-stakes situations safely.",
            "tags": "Storytelling,Psychology,Communication"
        },
        {
            "saved_at": "2026-08-27T11:45:00",
            "source_type": "YOUTUBE",
            "content_type": "VIDEO",
            "title": "Worldbuilding Craft: Designing Immersive Sci-Fi & Fantasy Settings",
            "creator": "Hello Future Me",
            "url": "https://www.youtube.com/watch?v=J-V942J29fA",
            "thumbnail_url": "https://img.youtube.com/vi/J-V942J29fA/hqdefault.jpg",
            "confidence": 0.97,
            "instagram_url": "",
            "raw_context": "Hard vs soft worldbuilding systems, magic rules, and cultural depth.",
            "ai_summary": "Comprehensive guide to setting rules, internal consistency, and environmental storytelling.",
            "content_hash": "SEED-STORY-005",
            "status": "UNREAD",
            "gemini_notes": "Key takeaway: Worldbuilding should serve character internal conflict.",
            "tags": "Storytelling,Worldbuilding,Creative Writing"
        },

        # Domain 2: Philosophy, Ethics & Intellectual Thought
        {
            "saved_at": "2026-08-27T12:00:00",
            "source_type": "BOOK",
            "content_type": "READING",
            "title": "Stoicism & Engineering Discipline: Discourses of Epictetus",
            "creator": "Epictetus",
            "url": "https://en.wikipedia.org/wiki/Discourses_of_Epictetus",
            "thumbnail_url": "",
            "confidence": 0.96,
            "instagram_url": "",
            "raw_context": "Classical philosophy applied to focus, control, and resilience in complex engineering projects.",
            "ai_summary": "Explores the dichotomy of control and maintaining emotional stability during technical challenges.",
            "content_hash": "SEED-PHIL-001",
            "status": "COMPLETED",
            "gemini_notes": "Key takeaway: Focus strictly on what is within your direct control.",
            "tags": "Philosophy,Stoicism,Discipline,Mindset"
        },
        {
            "saved_at": "2026-08-27T12:30:00",
            "source_type": "ARTICLE",
            "content_type": "READING",
            "title": "Deep Literacy & Critical Thinking in the Age of AI",
            "creator": "The Atlantic",
            "url": "https://www.theatlantic.com/magazine/archive/2008/07/is-google-making-us-stupid/306868/",
            "thumbnail_url": "",
            "confidence": 0.93,
            "instagram_url": "",
            "raw_context": "Nicholas Carr on neuroplasticity, deep reading, and cognitive endurance.",
            "ai_summary": "Examining how digital skimming alters neural pathways and the importance of deep reading habits.",
            "content_hash": "SEED-PHIL-002",
            "status": "IN_PROGRESS",
            "gemini_notes": "Key takeaway: Deep reading builds contemplative focus and linear logic.",
            "tags": "Philosophy,Literacy,Cognition,Reading"
        },
        {
            "saved_at": "2026-08-27T13:00:00",
            "source_type": "YOUTUBE",
            "content_type": "VIDEO",
            "title": "Ethics of Autonomous AI Agents & Alignment Problem",
            "creator": "Computerphile",
            "url": "https://www.youtube.com/watch?v=PqrPz6S-77g",
            "thumbnail_url": "https://img.youtube.com/vi/PqrPz6S-77g/hqdefault.jpg",
            "confidence": 0.95,
            "instagram_url": "",
            "raw_context": "Orthogonality thesis, instrumental convergence, and AI safety guardrails.",
            "ai_summary": "Analysis of goal specification, agentic autonomy, and safe model execution.",
            "content_hash": "SEED-PHIL-003",
            "status": "UNREAD",
            "gemini_notes": "Key takeaway: Alignment requires formal verification of agent tool capabilities.",
            "tags": "Philosophy,Ethics,AI Safety,Agents"
        },
        {
            "saved_at": "2026-08-27T13:30:00",
            "source_type": "BOOK",
            "content_type": "READING",
            "title": "Meditations by Marcus Aurelius: Rationality & Duty",
            "creator": "Marcus Aurelius",
            "url": "https://en.wikipedia.org/wiki/Meditations",
            "thumbnail_url": "",
            "confidence": 0.97,
            "instagram_url": "",
            "raw_context": "Personal journal of Roman Emperor on stoic duties, leadership, and impermanence.",
            "ai_summary": "Practical reflections on clarity of thought, emotional regulation, and service to community.",
            "content_hash": "SEED-PHIL-004",
            "status": "COMPLETED",
            "gemini_notes": "Key takeaway: The obstacle is the way; turn difficulty into fuel for growth.",
            "tags": "Philosophy,Stoicism,Leadership"
        },
        {
            "saved_at": "2026-08-27T14:00:00",
            "source_type": "ARTICLE",
            "content_type": "READING",
            "title": "Epistemology of Synthetic Knowledge & LLM Hallucinations",
            "creator": "Stanford AI Lab",
            "url": "https://ai.stanford.edu/blog/synthetic-epistemology/",
            "thumbnail_url": "",
            "confidence": 0.94,
            "instagram_url": "",
            "raw_context": "Epistemological limits of probabilistic text generation vs grounded empirical truth.",
            "ai_summary": "Mathematical formulation of ground truth verification in agent memory stores.",
            "content_hash": "SEED-PHIL-005",
            "status": "UNREAD",
            "gemini_notes": "Key takeaway: Grounding agent claims in external evidence graphs is non-negotiable.",
            "tags": "Philosophy,Epistemology,AI Alignment"
        },

        # Domain 3: Technology, AI & Finance
        {
            "saved_at": "2026-08-27T14:30:00",
            "source_type": "YOUTUBE",
            "content_type": "VIDEO",
            "title": "Building Autonomous Agents with Google ADK & Gemini 3.5",
            "creator": "Google DeepMind",
            "url": "https://www.youtube.com/watch?v=upbh9dmrRRQ",
            "thumbnail_url": "https://img.youtube.com/vi/upbh9dmrRRQ/hqdefault.jpg",
            "confidence": 0.99,
            "instagram_url": "",
            "raw_context": "Deep dive into Google ADK multi-agent architecture and Gemini 3.5 Flash integration.",
            "ai_summary": "Masterclass on building background autonomous AI agents using Google ADK, tool gateways, and Gemini 3.5 Flash reasoning.",
            "content_hash": "SEED-TECH-001",
            "status": "COMPLETED",
            "gemini_notes": "Key takeaway: Google ADK decouples orchestrator logic from tool gateways, enabling multi-agent sub-delegation.",
            "tags": "Technology,Google ADK,Gemini 3.5,Agents,Python"
        },
        {
            "saved_at": "2026-08-27T15:00:00",
            "source_type": "ARTICLE",
            "content_type": "READING",
            "title": "RAG Architecture & Vector Indexing Masterclass",
            "creator": "Pinecone Labs",
            "url": "https://www.pinecone.io/learn/vector-database/",
            "thumbnail_url": "",
            "confidence": 0.96,
            "instagram_url": "",
            "raw_context": "Comprehensive guide to dense vector embeddings, HNSW indexing, and hybrid retrieval.",
            "ai_summary": "Covers embedding distance metrics, ANN search, and reranking strategies for low-latency RAG pipelines.",
            "content_hash": "SEED-TECH-002",
            "status": "IN_PROGRESS",
            "gemini_notes": "Key takeaway: Use HNSW for sub-10ms retrieval with cosine distance on 1536-dim embeddings.",
            "tags": "Technology,RAG,Vector Database,Embeddings,Architecture"
        },
        {
            "saved_at": "2026-08-27T15:30:00",
            "source_type": "YOUTUBE",
            "content_type": "VIDEO",
            "title": "System Design of Distributed AI Databases & Real-time Pipelines",
            "creator": "ByteByteGo",
            "url": "https://www.youtube.com/watch?v=HHex4xS_yA",
            "thumbnail_url": "https://img.youtube.com/vi/HHex4xS_yA/hqdefault.jpg",
            "confidence": 0.95,
            "instagram_url": "",
            "raw_context": "Sharding, replication, and CDC event streams for high-throughput AI backends.",
            "ai_summary": "Architectural breakdown of distributed caching, message queues (Kafka/PubSub), and horizontal scaling.",
            "content_hash": "SEED-TECH-003",
            "status": "UNREAD",
            "gemini_notes": "Key takeaway: Decouple write path from async background indexing workers.",
            "tags": "Technology,System Design,Architecture,Distributed Systems"
        },
        {
            "saved_at": "2026-08-27T16:00:00",
            "source_type": "ARTICLE",
            "content_type": "READING",
            "title": "Algorithmic Trading & Quantitative Portfolio Optimization",
            "creator": "QuantConnect",
            "url": "https://www.quantconnect.com/tutorials/",
            "thumbnail_url": "",
            "confidence": 0.92,
            "instagram_url": "",
            "raw_context": "Sharpe ratio maximization, mean-variance optimization, and risk management.",
            "ai_summary": "Mathematical walkthrough of portfolio backtesting, alpha signal generation, and draw-down limits.",
            "content_hash": "SEED-TECH-004",
            "status": "UNREAD",
            "gemini_notes": "Key takeaway: Backtest robustness requires out-of-sample forward validation.",
            "tags": "Finance,Algorithmic Trading,Quantitative Finance,Money"
        },
        {
            "saved_at": "2026-08-27T16:30:00",
            "source_type": "YOUTUBE",
            "content_type": "VIDEO",
            "title": "Transformer Neural Networks & Self-Attention Explained Visually",
            "creator": "3Blue1Brown",
            "url": "https://www.youtube.com/watch?v=eMlx5fFNoYc",
            "thumbnail_url": "https://img.youtube.com/vi/eMlx5fFNoYc/hqdefault.jpg",
            "confidence": 0.99,
            "instagram_url": "",
            "raw_context": "Query, Key, Value matrix operations and multi-head attention visual math.",
            "ai_summary": "Intuitive mathematical visualization of transformer layer mechanics and token vector transformations.",
            "content_hash": "SEED-TECH-005",
            "status": "COMPLETED",
            "gemini_notes": "Key takeaway: Attention computes dynamic context-dependent weighted averages of token embeddings.",
            "tags": "Technology,Machine Learning,Transformers,Deep Learning"
        },

        # Domain 4: Mindset & Discipline
        {
            "saved_at": "2026-08-27T17:00:00",
            "source_type": "BOOK",
            "content_type": "READING",
            "title": "Deep Work: Rules for Focused Success in a Distracted World",
            "creator": "Cal Newport",
            "url": "https://www.calnewport.com/books/deep-work/",
            "thumbnail_url": "",
            "confidence": 0.97,
            "instagram_url": "",
            "raw_context": "Cognitive intensity, ritualized focus sessions, and eliminating low-value shallow tasks.",
            "ai_summary": "Actionable rules for cultivating intense concentration and building rare valuable skills.",
            "content_hash": "SEED-MIND-001",
            "status": "COMPLETED",
            "gemini_notes": "Key takeaway: Deep work capacity is the superpower of the 21st-century knowledge economy.",
            "tags": "Mindset,Discipline,Deep Work,Productivity"
        },
        {
            "saved_at": "2026-08-27T17:30:00",
            "source_type": "ARTICLE",
            "content_type": "READING",
            "title": "Atomic Habits: The Compound Interest of Self-Improvement",
            "creator": "James Clear",
            "url": "https://jamesclear.com/atomic-habits",
            "thumbnail_url": "",
            "confidence": 0.96,
            "instagram_url": "",
            "raw_context": "Identity-based habits, cue-craving-response-reward feedback loops, and friction reduction.",
            "ai_summary": "Framework for making small 1% daily improvements that compound into massive long-term results.",
            "content_hash": "SEED-MIND-002",
            "status": "IN_PROGRESS",
            "gemini_notes": "Key takeaway: You do not rise to the level of your goals; you fall to the level of your systems.",
            "tags": "Mindset,Discipline,Habits,Growth"
        },
        {
            "saved_at": "2026-08-27T18:00:00",
            "source_type": "INSTAGRAM",
            "content_type": "REEL",
            "title": "Overcoming Excuses & Building High-Velocity Execution",
            "creator": "Mindset Hub",
            "url": "https://www.instagram.com/reel/C-mindset1",
            "thumbnail_url": "",
            "confidence": 0.91,
            "instagram_url": "https://www.instagram.com/reel/C-mindset1",
            "raw_context": "Short motivational clip on reframing fear into immediate action.",
            "ai_summary": "Tactical advice on breaking paralysis by analysis through immediate micro-commitments.",
            "content_hash": "SEED-MIND-003",
            "status": "UNREAD",
            "gemini_notes": "Key takeaway: Speed of implementation is the ultimate competitive advantage.",
            "tags": "Mindset,Discipline,Resilience,Execution"
        },
        {
            "saved_at": "2026-08-27T18:30:00",
            "source_type": "BOOK",
            "content_type": "READING",
            "title": "Can't Hurt Me: Master Your Mind and Defy the Odds",
            "creator": "David Goggins",
            "url": "https://davidgoggins.com/book/",
            "thumbnail_url": "",
            "confidence": 0.95,
            "instagram_url": "",
            "raw_context": "The 40% rule, accountability mirror, and callous your mind technique.",
            "ai_summary": "Inspirational memoir and mental toughness protocol for pushing past perceived physical and mental limits.",
            "content_hash": "SEED-MIND-004",
            "status": "COMPLETED",
            "gemini_notes": "Key takeaway: When your brain tells you that you are done, you are actually only at 40% capability.",
            "tags": "Mindset,Discipline,Resilience,Mental Toughness"
        },
        {
            "saved_at": "2026-08-27T19:00:00",
            "source_type": "YOUTUBE",
            "content_type": "VIDEO",
            "title": "Dopamine Detox & Reclaiming Neuro-Focus",
            "creator": "Andrew Huberman",
            "url": "https://www.youtube.com/watch?v=qmHub123",
            "thumbnail_url": "https://img.youtube.com/vi/qmHub123/hqdefault.jpg",
            "confidence": 0.94,
            "instagram_url": "",
            "raw_context": "Neurobiology of dopamine baselines, reward prediction error, and motivation protocols.",
            "ai_summary": "Science-backed strategies for regulating baseline dopamine and maintaining intrinsic drive.",
            "content_hash": "SEED-MIND-005",
            "status": "UNREAD",
            "gemini_notes": "Key takeaway: Attach dopamine to the effort process itself rather than only the final result.",
            "tags": "Mindset,Neuroscience,Focus,Discipline"
        },

        # Domain 5: Digital Culture & Modern Essays
        {
            "saved_at": "2026-08-27T19:30:00",
            "source_type": "ARTICLE",
            "content_type": "READING",
            "title": "Digital Culture, Attention Economy & Algorithmic Velocity",
            "creator": "Substack Essay",
            "url": "https://substack.com/culture-essay",
            "thumbnail_url": "",
            "confidence": 0.90,
            "instagram_url": "",
            "raw_context": "Analysis of short-form media impact on long-form focus and knowledge retention.",
            "ai_summary": "Discusses how modern feeds fragment attention and why curated knowledge shelves are essential.",
            "content_hash": "SEED-CULT-001",
            "status": "UNREAD",
            "gemini_notes": "Key takeaway: Active curation counters feed-driven passive consumption.",
            "tags": "Digital Culture,Attention,Productivity,Social Media"
        },
        {
            "saved_at": "2026-08-27T20:00:00",
            "source_type": "YOUTUBE",
            "content_type": "VIDEO",
            "title": "Internet Sincerity & The Fall of Post-Ironic Memes",
            "creator": "Nerdwriter1",
            "url": "https://www.youtube.com/watch?v=nerd123",
            "thumbnail_url": "",
            "confidence": 0.92,
            "instagram_url": "",
            "raw_context": "Cultural shift from detached irony to earnest online creation and storytelling.",
            "ai_summary": "Explores how digital communities are embracing authenticity over cynical meme culture.",
            "content_hash": "SEED-CULT-002",
            "status": "COMPLETED",
            "gemini_notes": "Key takeaway: Earnestness is becoming the new cultural currency online.",
            "tags": "Digital Culture,Memes,Modern Society"
        },
        {
            "saved_at": "2026-08-27T20:30:00",
            "source_type": "INSTAGRAM",
            "content_type": "REEL",
            "title": "The Evolution of Short-Form Video & Algorithmic Curation",
            "creator": "Culture Lab",
            "url": "https://www.instagram.com/reel/C-cult1",
            "thumbnail_url": "",
            "confidence": 0.89,
            "instagram_url": "https://www.instagram.com/reel/C-cult1",
            "raw_context": "How recommendation algorithms shape consumer tastes and creative expression.",
            "ai_summary": "Analysis of feed algorithms in driving viral phenomena and niche micro-trends.",
            "content_hash": "SEED-CULT-003",
            "status": "UNREAD",
            "gemini_notes": "Key takeaway: Algorithmic curation creates echo chambers unless counterbalanced with deliberate shelf management.",
            "tags": "Digital Culture,Algorithms,Social Media"
        },
        {
            "saved_at": "2026-08-27T21:00:00",
            "source_type": "ARTICLE",
            "content_type": "READING",
            "title": "Human-AI Symbiosis: Co-Creation in the 21st Century",
            "creator": "MIT Technology Review",
            "url": "https://www.technologyreview.com/human-ai-symbiosis/",
            "thumbnail_url": "",
            "confidence": 0.95,
            "instagram_url": "",
            "raw_context": "Collaborative intelligence workflows between human creators and generative agents.",
            "ai_summary": "How AI tools amplify creative output when framed as collaborative partners rather than automation replacements.",
            "content_hash": "SEED-CULT-004",
            "status": "IN_PROGRESS",
            "gemini_notes": "Key takeaway: The future belongs to hybrid human-AI teams with high domain judgment.",
            "tags": "Digital Culture,AI Symbiosis,Collaboration,Future of Work"
        },
        {
            "saved_at": "2026-08-27T21:30:00",
            "source_type": "BOOK",
            "content_type": "READING",
            "title": "The Shallows: What the Internet Is Doing to Our Brains",
            "creator": "Nicholas Carr",
            "url": "https://www.amazon.com/Shallows-What-Internet-Doing-Brains/dp/0393339750",
            "thumbnail_url": "",
            "confidence": 0.94,
            "instagram_url": "",
            "raw_context": "Pulitzer finalist examining intellectual and cultural consequences of perpetual online connectivity.",
            "ai_summary": "Deep dive into cognitive trade-offs of hyperlinking, multitasking, and digital information overload.",
            "content_hash": "SEED-CULT-005",
            "status": "COMPLETED",
            "gemini_notes": "Key takeaway: Protect spaces for uninterrupted deep thought and structural reading.",
            "tags": "Digital Culture,Cognition,Reading,Technology"
        }
    ]
    for item in items:
        save_local_shelf_row(item)

def get_local_shelf_rows() -> List[dict]:
    """Retrieves all rows stored in local_shelf_items."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS local_shelf_items (content_hash TEXT PRIMARY KEY, row_data TEXT, saved_at TEXT)")
        cursor.execute("SELECT row_data FROM local_shelf_items ORDER BY saved_at DESC")
        rows = cursor.fetchall()
        conn.close()
        
        parsed = [json.loads(r[0]) for r in rows if r[0]]
        if not parsed:
            seed_initial_shelf_items()
            return get_local_shelf_rows()
            
        return parsed
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
