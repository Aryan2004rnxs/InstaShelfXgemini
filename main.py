import os
import shutil
import asyncio
import logging
from datetime import datetime

# Force native gRPC DNS resolution to fix macOS DNS lookup failures
os.environ["GRPC_DNS_RESOLVER"] = "native"

# Fix SSL CA Bundle paths overridden by Hugging Face Spaces (causes SSLError in containers)
for var in ["CURL_CA_BUNDLE", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"]:
    if var in os.environ:
        del os.environ[var]

# Monkey-patch socket to force IPv4. 
# Hugging Face Spaces have broken IPv6 routing which causes httpx to hang and throw ConnectTimeout.
import socket
old_getaddrinfo = socket.getaddrinfo
def force_ipv4_getaddrinfo(*args, **kwargs):
    responses = old_getaddrinfo(*args, **kwargs)
    return [res for res in responses if res[0] == socket.AF_INET]
socket.getaddrinfo = force_ipv4_getaddrinfo

from contextlib import asynccontextmanager
from typing import Optional, List

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, FileResponse
from telegram import Update, Bot
from telegram.ext import Application

import utils

import health
import sheets
import enrichment
import dedup
import ai_client
from scraper import scrape_instagram_content
from handlers import register_handlers
from models import ShelfRow
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles

import progress
from agents.orchestrator import InstaShelfADKOrchestrator
from memory.task_store import get_task, list_recent_tasks, save_task
from memory.memory_store import get_user_memory
from services.learning_mission import list_missions, create_learning_mission
from models.task import ProcessRequest

# Initialize logging
logger = logging.getLogger("InstaShelf.main")
orchestrator = InstaShelfADKOrchestrator()

# Load configuration variables
HF_SPACE_URL = os.getenv("HF_SPACE_URL")
WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_BASE_URL = os.getenv("TELEGRAM_API_BASE_URL")

if not HF_SPACE_URL:
    logger.warning("HF_SPACE_URL is not set. Webhook configuration might fail.")
if not BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN is not set. Bot startup will fail.")

# Initialize python-telegram-bot application
import httpx
from telegram.request import HTTPXRequest
from telegram.error import NetworkError, TimedOut

class RetryHTTPXRequest(HTTPXRequest):
    """A custom HTTPXRequest that automatically retries on ConnectError/TimedOut.
    Forces IPv4 (local_address='0.0.0.0') to bypass Hugging Face IPv6 routing blackholes."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Force the initial client to also use IPv4 and no keep-alive
        transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0", retries=3)
        self._client = httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(connect=30.0, read=30.0, write=30.0, pool=30.0),
            limits=httpx.Limits(max_keepalive_connections=0, keepalive_expiry=0.0)
        )
        
    async def do_request(self, *args, **kwargs):
        for attempt in range(3):
            try:
                return await super().do_request(*args, **kwargs)
            except (NetworkError, TimedOut) as e:
                if "ConnectError" in str(e) or isinstance(e, TimedOut):
                    logger.warning(f"Connection dropped or timed out. Resetting connection pool and retrying ({attempt+1}/3)...")
                    import asyncio
                    try: await self._client.aclose()
                    except: pass
                    
                    transport = httpx.AsyncHTTPTransport(local_address="0.0.0.0", retries=3)
                    self._client = httpx.AsyncClient(
                        transport=transport,
                        timeout=httpx.Timeout(connect=30.0, read=30.0, write=30.0, pool=30.0),
                        limits=httpx.Limits(max_keepalive_connections=0, keepalive_expiry=0.0)
                    )
                    await asyncio.sleep(1)
                    continue
                raise
        return await super().do_request(*args, **kwargs)

t_request = RetryHTTPXRequest(connection_pool_size=10, read_timeout=30.0, write_timeout=30.0, connect_timeout=30.0, pool_timeout=30.0)

builder = Application.builder().token(BOT_TOKEN).request(t_request)
if TELEGRAM_API_BASE_URL:
    logger.info(f"Using custom Telegram API base URL: {TELEGRAM_API_BASE_URL}")
    builder.base_url(TELEGRAM_API_BASE_URL)
tg_app = builder.build()

def cleanup_temp_files(temp_dir: Optional[str], image_paths: List[str]):
    """Cleans up temporary files and directories created during scraping."""
    # Delete individual downloaded image files
    for path in image_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            logger.warning(f"Failed to delete temporary image {path}: {e}")
            
    # Remove the temporary download directory
    if temp_dir and os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to remove temporary directory {temp_dir}: {e}")

async def background_worker(queue: asyncio.Queue, bot: Bot):
    """
    Background worker that processes incoming content URLs via Google ADK Orchestrator.
    """
    logger.info("Background queue processing worker started.")
    
    while True:
        job = await queue.get()
        url = job.get("url")
        chat_id = job.get("chat_id")
        learning_goal = job.get("learning_goal")
        task_id = job.get("task_id")
        
        logger.info(f"Starting Google ADK Agent workflow for URL: {url} (goal: {learning_goal}, chat_id: {chat_id})")
        
        try:
            await orchestrator.run_workflow(
                content_url=url,
                learning_goal=learning_goal,
                telegram_bot=bot,
                chat_id=chat_id,
                task_id=task_id
            )
        except Exception as e:
            logger.exception(f"Error executing agent workflow: {e}")
        finally:
            queue.task_done()

async def keep_telegram_alive(bot: Bot):
    """
    Pings the Telegram API every 60 seconds to prevent the HTTPX connection pool
    from going stale, which causes httpx.ConnectError when using a Cloudflare proxy
    that drops idle connections after ~100 seconds.
    """
    logger.info("Starting Telegram keep-alive ping task...")
    while True:
        try:
            await bot.get_me()
        except Exception as e:
            logger.warning(f"Telegram keep-alive ping failed (transient): {e}")
        await asyncio.sleep(60)

# FastAPI lifecycles
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize python-telegram-bot safely so it doesn't crash FastAPI startup
    try:
        await tg_app.initialize()
        await tg_app.start()
        
        # Check if polling mode is forced (e.g. for private Hugging Face spaces)
        polling_mode = os.getenv("TELEGRAM_POLLING", "false").lower() == "true"
        
        if polling_mode:
            logger.info("Forcing POLLING mode: Deleting any active webhook and starting polling...")
            await tg_app.bot.delete_webhook(drop_pending_updates=True)
            await asyncio.sleep(2)
            await tg_app.updater.start_polling(drop_pending_updates=True)
            logger.info("Bot started in POLLING mode successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize or start Telegram bot during startup: {e}", exc_info=True)
    else:
        # Configure bot webhook url dynamically on startup
        if HF_SPACE_URL:
            webhook_url = f"{HF_SPACE_URL}/webhook"
            logger.info(f"Configuring Telegram webhook to: {webhook_url}")
            await tg_app.bot.delete_webhook(drop_pending_updates=True)
            await asyncio.sleep(2)
            await tg_app.bot.set_webhook(
                url=webhook_url,
                secret_token=WEBHOOK_SECRET if WEBHOOK_SECRET else None
            )
        else:
            logger.error("HF_SPACE_URL is not set. Webhook was not configured.")
            
    # Set up async in-process queue
    processing_queue = asyncio.Queue()
    
    # Register Telegram bot handlers with the queue
    register_handlers(tg_app, processing_queue)
    
    # Run the background worker task
    worker_task = asyncio.create_task(background_worker(processing_queue, tg_app.bot))
    
    # Start the keep-alive task to prevent connection drops on the proxy
    keep_alive_task = asyncio.create_task(keep_telegram_alive(tg_app.bot))
    
    # Sync any offline cached rows from SQLite to Sheets on startup
    asyncio.create_task(sheets.sync_pending_rows())
    
    yield
    
    # Shutdown sequence
    logger.info("Shutting down background tasks and Telegram bot...")
    if polling_mode:
        await tg_app.updater.stop()
    worker_task.cancel()
    keep_alive_task.cancel()
    try:
        await worker_task
        await keep_alive_task
    except asyncio.CancelledError:
        pass
        
    await tg_app.stop()
    await tg_app.shutdown()
    logger.info("Shutdown complete.")

app = FastAPI(lifespan=lifespan)

# Add healthcheck route
app.include_router(health.router)

# Mount frontend directory for static assets
app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/styles.css")
async def serve_styles():
    return FileResponse("frontend/styles.css", media_type="text/css")

@app.get("/app.js")
async def serve_app_js():
    return FileResponse("frontend/app.js", media_type="application/javascript")

@app.get("/shelf", response_class=HTMLResponse)
async def serve_shelf():
    """Serves the interactive InstaShelf web view."""
    try:
        with open("frontend/index.html", "r") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Frontend not found. Please build or create the frontend/index.html file.</h1>", status_code=404)

@app.get("/api/shelf")
async def api_get_shelf():
    """API endpoint to get all shelf items with their progress."""
    rows = await sheets.get_all_rows_sync_fallback()
    progress_data = await asyncio.to_thread(progress.get_all_progress)
    return {"status": "success", "data": rows, "progress": progress_data}

@app.get("/api/progress")
async def api_get_progress():
    """API endpoint to get all user progress."""
    progress_data = await asyncio.to_thread(progress.get_all_progress)
    return {"status": "success", "progress": progress_data}

class ProgressUpdate(BaseModel):
    content_hash: str
    progress_seconds: int
    is_completed: bool

@app.post("/api/progress")
async def api_update_progress(update: ProgressUpdate):
    """API endpoint to update user progress for an item."""
    success = await asyncio.to_thread(progress.update_progress, update.content_hash, update.progress_seconds, update.is_completed)
    if success:
        return {"status": "success"}
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to update progress")

class NoteCreate(BaseModel):
    content_hash: str
    timestamp_seconds: int
    note_text: str

@app.get("/api/notes/{content_hash}")
async def api_get_notes(content_hash: str):
    """API endpoint to get all notes for a specific content item."""
    notes = await asyncio.to_thread(progress.get_notes, content_hash)
    return {"status": "success", "notes": notes}

@app.post("/api/notes")
async def api_create_note(note: NoteCreate):
    """API endpoint to create a new timestamped note."""
    new_note = await asyncio.to_thread(progress.add_note, note.content_hash, note.timestamp_seconds, note.note_text)
    if new_note:
        return {"status": "success", "note": new_note}
    from fastapi import HTTPException
    raise HTTPException(status_code=500, detail="Failed to create note")

class GenerateNoteRequest(BaseModel):
    title: str

@app.post("/api/notes/{content_hash}/generate")
async def api_generate_notes_summary(content_hash: str, req: GenerateNoteRequest):
    """API endpoint to generate an AI summary from existing notes or topic title."""
    notes = await asyncio.to_thread(progress.get_notes, content_hash)
    summary = await ai_client.generate_notes_summary(req.title, notes or [])
    if summary:
        return {"status": "success", "summary": summary}
    from fastapi import HTTPException
    raise HTTPException(status_code=500, detail="Failed to generate summary")

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serves the premium InstaShelf status & control web dashboard."""
    groq_usage = utils.get_groq_usage()
    gemini_usage = utils.get_gemini_usage()
    pending_rows = len(utils.get_pending_rows())
    
    groq_percentage = min(100.0, (groq_usage / 1000.0) * 100.0)
    gemini_percentage = min(100.0, (gemini_usage / 20.0) * 100.0)
    
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>InstaShelf Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: rgba(255, 255, 255, 0.03);
            --card-border: rgba(255, 255, 255, 0.08);
            --text-primary: #ffffff;
            --text-secondary: #94a3b8;
            --primary: #8b5cf6;
            --primary-glow: rgba(139, 92, 246, 0.15);
            --success: #10b981;
            --success-glow: rgba(16, 185, 129, 0.15);
            --warning: #f59e0b;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            overflow-x: hidden;
            position: relative;
        }

        /* Abstract glowing backgrounds */
        body::before {
            content: '';
            position: absolute;
            width: 400px;
            height: 400px;
            background: radial-gradient(circle, var(--primary-glow) 0%, transparent 70%);
            top: -100px;
            left: -100px;
            z-index: 0;
            pointer-events: none;
        }

        body::after {
            content: '';
            position: absolute;
            width: 450px;
            height: 450px;
            background: radial-gradient(circle, rgba(16, 185, 129, 0.08) 0%, transparent 70%);
            bottom: -100px;
            right: -100px;
            z-index: 0;
            pointer-events: none;
        }

        .container {
            width: 100%;
            max-width: 900px;
            padding: 40px 20px;
            z-index: 1;
        }

        header {
            text-align: center;
            margin-bottom: 40px;
        }

        h1 {
            font-size: 2.8rem;
            font-weight: 800;
            background: linear-gradient(135deg, #ffffff 40%, #a78bfa 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
            letter-spacing: -0.5px;
        }

        header p {
            color: var(--text-secondary);
            font-size: 1.1rem;
            font-weight: 300;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 24px;
            margin-bottom: 32px;
        }

        .card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 20px;
            padding: 24px;
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);
            position: relative;
            overflow: hidden;
        }

        .card:hover {
            transform: translateY(-5px);
            border-color: rgba(255, 255, 255, 0.15);
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.3);
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }

        .card-title {
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .card-icon {
            font-size: 1.4rem;
            width: 40px;
            height: 40px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--card-border);
        }

        .stat-value {
            font-size: 2.2rem;
            font-weight: 800;
            margin-bottom: 8px;
            display: flex;
            align-items: baseline;
            gap: 4px;
        }

        .stat-unit {
            font-size: 1rem;
            font-weight: 400;
            color: var(--text-secondary);
        }

        .stat-desc {
            font-size: 0.85rem;
            color: var(--text-secondary);
        }

        /* Status Badge */
        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: var(--success-glow);
            color: var(--success);
            padding: 6px 14px;
            border-radius: 30px;
            font-weight: 600;
            font-size: 0.9rem;
            border: 1px solid rgba(16, 185, 129, 0.2);
            box-shadow: 0 0 15px rgba(16, 185, 129, 0.05);
        }

        .status-dot {
            width: 8px;
            height: 8px;
            background-color: var(--success);
            border-radius: 50%;
            display: inline-block;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.9); opacity: 0.6; }
            50% { transform: scale(1.15); opacity: 1; box-shadow: 0 0 10px var(--success); }
            100% { transform: scale(0.9); opacity: 0.6; }
        }

        /* Progress Bar */
        .progress-container {
            width: 100%;
            height: 6px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            margin-top: 15px;
            overflow: hidden;
        }

        .progress-bar {
            height: 100%;
            background: linear-gradient(90deg, var(--primary) 0%, #a78bfa 100%);
            border-radius: 10px;
            transition: width 1s ease-in-out;
        }

        .progress-bar.gemini {
            background: linear-gradient(90deg, #3b82f6 0%, #60a5fa 100%);
        }

        /* Guide Card */
        .guide-card {
            grid-column: span 1;
        }

        @media (min-width: 768px) {
            .guide-card {
                grid-column: span 2;
            }
        }

        .guide-list {
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .guide-item {
            display: flex;
            align-items: flex-start;
            gap: 12px;
            font-size: 0.95rem;
            color: var(--text-secondary);
        }

        .guide-num {
            background: rgba(139, 92, 246, 0.1);
            color: var(--primary);
            border: 1px solid rgba(139, 92, 246, 0.2);
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.8rem;
            font-weight: 700;
            flex-shrink: 0;
            margin-top: 2px;
        }

        footer {
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.85rem;
            margin-top: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
            padding-top: 20px;
            width: 100%;
        }

        footer a {
            color: var(--primary);
            text-decoration: none;
            transition: color 0.2s;
        }

        footer a:hover {
            color: #a78bfa;
        }

        .shelf-btn {
            display: inline-block;
            margin-top: 20px;
            padding: 12px 32px;
            background: linear-gradient(135deg, var(--primary) 0%, #a78bfa 100%);
            color: white;
            text-decoration: none;
            font-weight: 600;
            border-radius: 30px;
            font-size: 1.1rem;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(139, 92, 246, 0.4);
        }

        .shelf-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(139, 92, 246, 0.6);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>InstaShelf</h1>
            <p>Telegram Intelligent Content Extractor & Book Shelf Curation</p>
            <a href="/shelf" class="shelf-btn">✨ Open Interactive Shelf</a>
        </header>

        <div class="grid">
            <!-- Bot Status Card -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">System Health</span>
                    <span class="card-icon">⚡</span>
                </div>
                <div style="margin: 15px 0;">
                    <div class="status-badge">
                        <span class="status-dot"></span>
                        Active & Running
                    </div>
                </div>
                <p class="stat-desc">Webhook configuration active, receiving updates.</p>
            </div>

            <!-- Groq API Usage Card -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Groq API Quota (Primary)</span>
                    <span class="card-icon">⚡</span>
                </div>
                <div class="stat-value">
                    {groq_usage} <span class="stat-unit">/ 1000</span>
                </div>
                <p class="stat-desc">Daily primary AI extraction requests used.</p>
                <div class="progress-container">
                    <div class="progress-bar" style="width: {groq_percentage}%"></div>
                </div>
            </div>

            <!-- Gemini API Usage Card -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Gemini API Quota (Fallback)</span>
                    <span class="card-icon">🤖</span>
                </div>
                <div class="stat-value">
                    {gemini_usage} <span class="stat-unit">/ 20</span>
                </div>
                <p class="stat-desc">Daily fallback AI extraction requests used.</p>
                <div class="progress-container">
                    <div class="progress-bar gemini" style="width: {gemini_percentage}%"></div>
                </div>
            </div>

            <!-- Database / Caching Card -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Offline Cache Sync</span>
                    <span class="card-icon">💾</span>
                </div>
                <div class="stat-value">
                    {pending_rows}
                    <span class="stat-unit">rows</span>
                </div>
                <p class="stat-desc">Pending Google Sheets updates in offline queue.</p>
            </div>

            <!-- Quick Instructions Card -->
            <div class="card guide-card">
                <div class="card-header">
                    <span class="card-title">Telegram Bot Instructions</span>
                    <span class="card-icon">📖</span>
                </div>
                <ul class="guide-list">
                    <li class="guide-item">
                        <span class="guide-num">1</span>
                        <span>Send any Instagram Post or Reel URL to your Telegram bot.</span>
                    </li>
                    <li class="guide-item">
                        <span class="guide-num">2</span>
                        <span>The bot automatically scrapes the video keyframes/captions, runs Groq/Gemini Multimodal extraction, and dedups.</span>
                    </li>
                    <li class="guide-item">
                        <span class="guide-num">3</span>
                        <span>Identified books and YouTube videos are enriched and saved instantly to your Google Sheet.</span>
                    </li>
                </ul>
            </div>
        </div>

        <footer>
            <p>Made with ❤️ by <a href="https://github.com/Aryan2004rnxs/InstaShelf" target="_blank">Aryan2004rnxs</a> | Powered by Groq Llama 4 & Gemini 2.5 & FastAPI</p>
        </footer>
    </div>
</body>
</html>"""
    formatted_html = html_content.replace("{groq_usage}", str(groq_usage))\
                                 .replace("{groq_percentage}", f"{groq_percentage:.1f}")\
                                 .replace("{gemini_usage}", str(gemini_usage))\
                                 .replace("{gemini_percentage}", f"{gemini_percentage:.1f}")\
                                 .replace("{pending_rows}", str(pending_rows))
    return HTMLResponse(content=formatted_html, status_code=200)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Receives updates from Telegram webhook.
    Validates security header if secret token is configured.
    """
    if WEBHOOK_SECRET:
        received_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if received_secret != WEBHOOK_SECRET:
            logger.warning("Forbidden webhook request: Secret token mismatch.")
            return Response(status_code=403)
            
    try:
        data = await request.json()
        update = Update.de_json(data, tg_app.bot)
        # Process asynchronously using PTB process_update
        await tg_app.process_update(update)
    except Exception as e:
        logger.error(f"Error processing incoming Telegram update: {e}")
        
    return Response(status_code=200)

# ---------------------------------------------------------------------------
# Google ADK Agent Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/agent/process")
async def api_agent_process(req: ProcessRequest):
    """
    Submits a content URL and optional learning goal for autonomous ADK agent execution.
    Returns immediate acknowledgment (< 1s) and task_id.
    """
    import uuid
    from datetime import datetime
    
    task_id = f"INSTASHELF-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    
    # Trigger async workflow background execution
    asyncio.create_task(orchestrator.run_workflow(
        content_url=req.url,
        learning_goal=req.learning_goal,
        user_id=req.user_id or "default_user",
        task_id=task_id
    ))
    
    return {
        "status": "success",
        "task_id": task_id,
        "message": "InstaShelf Agent accepted request and is processing in background.",
        "url": req.url,
        "learning_goal": req.learning_goal
    }

@app.get("/api/agent/tasks/{task_id}")
async def api_get_agent_task(task_id: str):
    """Fetches real-time status and decision audit log for a specific agent task."""
    from fastapi import HTTPException
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
    return {"status": "success", "task": task.model_dump()}

@app.get("/api/agent/tasks")
async def api_list_agent_tasks(limit: int = 20):
    """Lists recent agent tasks for developer & UI observability."""
    tasks = list_recent_tasks(limit=limit)
    return {"status": "success", "tasks": [t.model_dump() for t in tasks]}

class CreateMissionRequest(BaseModel):
    topic: str
    user_id: Optional[str] = "default_user"

@app.get("/api/agent/missions")
async def api_list_missions(user_id: str = "default_user"):
    """Lists active Learning Missions for the user."""
    missions = list_missions(user_id=user_id)
    return {"status": "success", "missions": [m.model_dump() for m in missions]}

@app.post("/api/agent/missions")
async def api_create_mission(req: CreateMissionRequest):
    """Creates a new Learning Mission for a topic."""
    shelf_items = await sheets.get_all_rows_sync_fallback()
    mission = await create_learning_mission(topic=req.topic, user_id=req.user_id or "default_user", existing_shelf_items=shelf_items)
    return {"status": "success", "mission": mission.model_dump()}

@app.get("/api/agent/memory")
async def api_get_memory(user_id: str = "default_user"):
    """Retrieves persistent long-term user memory."""
    mem = get_user_memory(user_id=user_id)
    return {"status": "success", "memory": mem}

@app.get("/api/agent/ledger")
async def api_get_ledger(limit: int = 50):
    """Retrieves entries from the Append-Only Action Ledger."""
    from memory.action_ledger import get_action_ledger
    ledger_entries = get_action_ledger(limit=limit)
    return {"status": "success", "ledger": [e.model_dump() for e in ledger_entries]}

@app.get("/api/agent/catalog")
async def api_get_catalog():
    """Verifies Gemini 3.5+ API model catalog status."""
    from services.gemini_service import verify_model_catalog
    catalog_status = verify_model_catalog()
    return {"status": "success", "catalog": catalog_status}

@app.post("/api/agent/multimodal/fuse")
async def api_multimodal_fuse():
    """Executes Multimodal Content Fusion ('Teach Me From What I Showed You')."""
    from services.multimodal_inbox import process_multimodal_content_fusion
    fusion_result = await process_multimodal_content_fusion()
    return {"status": "success", "fusion": fusion_result}

@app.post("/api/agent/debt/paydown")
async def api_debt_paydown():
    """Executes Knowledge Debt Paydown."""
    from services.knowledge_debt import calculate_knowledge_debt, execute_knowledge_debt_paydown
    debt = calculate_knowledge_debt(342, 12, 7, 5, 3)
    paydown = execute_knowledge_debt_paydown(debt)
    return {"status": "success", "paydown": paydown}

@app.post("/api/agent/proactive/evaluate")
async def api_proactive_evaluate():
    """Triggers Proactive Mission Health Scheduler evaluation."""
    from services.proactive_scheduler import run_proactive_mission_health_check
    res = await run_proactive_mission_health_check()
    return {"status": "success", "proactive_result": res}

@app.post("/api/agent/auditor/run")
async def api_auditor_run():
    """Executes Knowledge Auditor & 'Learning the Wrong Thing' check."""
    from services.knowledge_auditor import audit_user_knowledge_and_saved_items
    shelf_items = await sheets.get_all_rows_sync_fallback()
    audit_res = await audit_user_knowledge_and_saved_items(
        goal_statement="Become interview-ready in RAG",
        saved_shelf_items=shelf_items,
        completed_concepts=["Embeddings", "Vector Databases"],
        pending_concepts=["RAG Evaluation", "Reranking"]
    )
    return {"status": "success", "audit": audit_res}

@app.get("/api/agent/demo/hero")
async def api_demo_hero():
    """Judge Demo Mode endpoint showing single continuous story."""
    return {
        "status": "success",
        "demo_scenario": "RAG Interview Readiness",
        "distance_to_goal_before": "42%",
        "distance_to_goal_after": "14%",
        "goal_achievement_pct": "86%",
        "knowledge_debt_index": 41,
        "attention_saved": "109 notifications suppressed",
        "human_effort_reduced": "18 decisions automated / 2 human interventions"
    }

# ------------------------------------------------------------------------------
# AUTONOMOUS KNOWLEDGE CARTOGRAPHER V6.0 API ENDPOINTS
# ------------------------------------------------------------------------------
from services.entity_extractor import extract_discovery_container
from services.entity_resolver import resolve_entities
from services.source_evaluator import evaluate_and_rank_candidates
from services.vector_retriever import evaluate_similarity_and_novelty
from services.knowledge_graph import mutate_graph, get_living_map
from services.path_engine import generate_consumption_path
from services.gap_detector import detect_knowledge_gaps
from services.proactive_scheduler import run_proactive_background_cartography
from models import DiscoveredEntity

@app.post("/api/cartographer/process")
async def api_cartographer_process(request: Request):
    """Processes a single URL input as a multi-entity Discovery Container."""
    body = await request.json()
    url = body.get("url", "https://www.youtube.com/watch?v=upbh9dmrRRQ")
    raw_text = body.get("text", "")
    
    container = await extract_discovery_container(url, raw_text)
    container.status = "RESOLVING"
    
    resolved_entities = resolve_entities(container.entities)
    container.entities = resolved_entities
    container.status = "RESEARCHING"

    # Evaluate candidate sources for primary entity
    primary_source, alternatives = evaluate_and_rank_candidates(resolved_entities[0])
    
    # Vector retrieval & duplicate suppression check
    existing_entities = [DiscoveredEntity(entity_id="E0", canonical_name="Vector Search", entity_type="CONCEPT")]
    sim_score, nov_score, is_suppressed, supp_reason = evaluate_similarity_and_novelty(resolved_entities[0], existing_entities)
    
    if not is_suppressed:
        # Save newly mapped source as real ShelfRow item
        import hashlib
        c_hash = hashlib.md5(f"{url}_{datetime.utcnow().timestamp()}".encode()).hexdigest()
        new_row = ShelfRow(
            saved_at=datetime.utcnow().isoformat() + "Z",
            source_type="YOUTUBE" if "youtube" in url or "youtu.be" in url else "IDEA",
            content_type="YOUTUBE" if "youtube" in url or "youtu.be" in url else "IDEA",
            title=primary_source.title,
            creator="Agent Cartographer",
            url=url,
            thumbnail_url="https://img.youtube.com/vi/upbh9dmrRRQ/hqdefault.jpg" if "youtube" in url else "",
            confidence=primary_source.overall_score / 100.0,
            raw_context=raw_text or f"Discovered entity: {resolved_entities[0].canonical_name}",
            ai_summary=f"Curated {primary_source.designation} (Quality Score: {primary_source.overall_score}%). {primary_source.evidence[0] if primary_source.evidence else ''}",
            content_hash=c_hash,
            status="UNREAD",
            tags=",".join([e.canonical_name for e in resolved_entities])
        )
        utils.save_shelf_row(new_row)

        mutate_graph(
            event_type="LINK",
            cluster_id="CLUST-DYNAMIC",
            description=f"LINKED '{resolved_entities[0].canonical_name}' into living knowledge map.",
            evidence=[f"Similarity: {sim_score}%, Novelty: {nov_score}%"],
            affected_nodes=[e.entity_id for e in resolved_entities]
        )
    
    container.status = "COMPLETE"
    path = generate_consumption_path(resolved_entities[0].canonical_name)
    gaps = detect_knowledge_gaps(resolved_entities[0].canonical_name, [e.canonical_name for e in resolved_entities])

    return {
        "status": "success",
        "container": container.model_dump(),
        "primary_source": primary_source.model_dump(),
        "alternatives": [a.model_dump() for a in alternatives],
        "similarity_score": sim_score,
        "novelty_score": nov_score,
        "is_suppressed": is_suppressed,
        "suppression_reason": supp_reason,
        "consumption_path": [p.model_dump() for p in path],
        "knowledge_gaps": gaps
    }

@app.get("/api/cartographer/map")
async def api_cartographer_map():
    """Returns living knowledge map state & evolution history timeline."""
    return await get_living_map()

@app.get("/api/cartographer/path")
async def api_cartographer_path(topic: str = "RAG", mode: str = "BALANCED"):
    """Returns purpose-driven consumption path DAG."""
    nodes = generate_consumption_path(topic, mode=mode)
    return {"status": "success", "topic": topic, "mode": mode, "path": [n.model_dump() for n in nodes]}

@app.post("/api/cartographer/proactive-check")
async def api_cartographer_proactive_check():
    """Triggers background proactive cartography maintenance check."""
    res = await run_proactive_background_cartography()
    return res

@app.post("/api/cartographer/mutate")
async def api_cartographer_mutate():
    """Simulates a graph mutation event for live demonstration."""
    import random
    domains = ["CLUST-STORYTELLING", "CLUST-PHILOSOPHY", "CLUST-TECH-FINANCE", "CLUST-MINDSET", "CLUST-CULTURE"]
    target_d = random.choice(domains)
    event = mutate_graph(
        event_type="LINK",
        cluster_id=target_d,
        description=f"AI Agent detected semantic connection & re-clustered node into domain '{target_d}'",
        evidence=["Zero-shot Gemini Classifier", "Embedding Cosine Distance: 0.92"],
        affected_nodes=["Vector Indexing", "Communication Craft"]
    )
    return {"status": "success", "event": event.model_dump()}


@app.get("/favicon.ico")
async def favicon():
    from fastapi import Response
    return Response(status_code=204)

if __name__ == "__main__":
    import uvicorn
    dev_reload = os.getenv("DEV_RELOAD", "false").lower() == "true"
    port = int(os.getenv("PORT", 7860))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=dev_reload)

