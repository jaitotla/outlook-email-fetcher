"""
OpenMailBot Agent - FastAPI Application
Handles email ingestion, embeddings, RAG, and LLM interface
"""
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uvicorn
from datetime import datetime
import os
import sys
import json
import base64
import re
import html
import sqlite3
import asyncio
import uuid
import threading
from functools import partial

# ✓ MUST be before any 'from agent import' statements
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agent.config import settings
#from agent.services.ingestion import EmailIngestionService
# from agent.services.embeddings import EmbeddingService
# from agent.services.rag import RAGService
# from agent.services.llm import LLMService
#from agent.services.slack_ingestion import SlackIngestionService
#from agent.services.file_processor import FileProcessor
from agent.services.chat_pipeline import ChatWithThreadPipeline
from agent.services.draft_pipeline import DraftPipeline
from agent.services.settings_manager import SettingsManager
from agent.services.preprocessing_emails import EmailPreprocessingPipeline
from agent.services.label_pipeline import EmailLabelPipeline
from agent.services.label_email_lockbook import get_user_lockbook, get_global_lockbook
from agent.services.store_pipeline import CheckAndStoreEmailPipeline, CheckAndStoreAttachmentsPipeline
from agent.services.summarization_pipeline import SummarizationPipeline
from agent.services.encryption_service import get_encryption_service
from agent.services.email_tone_pipeline import TonePipelineManager
from agent.services.draft_cache_manager import DraftCacheManager
#from agent.database.mongodb import MongoDBClient
from agent.services.simple_draft_pipeline import SimpleDraftPipeline

import logging
from logging.handlers import RotatingFileHandler

# ── Rotating File Logger Setup ──────────────────────────────────────────────
# Configure logging with rotating file handler (max 5 files, 10MB each)
def setup_logger():
    """Setup rotating file logger for backend/main.py"""
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    # Create root logger
    logger = logging.getLogger("openmailbot.backend")
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers = []
    
    # ─ MAIN LOG: app.log (ALL operations, all levels) ─
    log_file = os.path.join(logs_dir, "app.log")
    main_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=4  # Keeps log, log.1, log.2, log.3, log.4 (5 total)
    )
    main_handler.setLevel(logging.DEBUG)
    
    # ─ OPERATIONS LOG: operations.log (DEBUG level for detailed pipeline operations) ─
    ops_log_file = os.path.join(logs_dir, "operations.log")
    ops_handler = RotatingFileHandler(
        ops_log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=4
    )
    ops_handler.setLevel(logging.DEBUG)
    
    # ─ ERRORS LOG: errors.log (ERROR level only) ─
    error_log_file = os.path.join(logs_dir, "errors.log")
    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=4
    )
    error_handler.setLevel(logging.ERROR)
    
    # Console handler for stdout - NOW DEBUG LEVEL to see all details
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)  # Changed from INFO to DEBUG
    
    # Formatter
    detailed_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s - %(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    simple_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    main_handler.setFormatter(detailed_formatter)
    ops_handler.setFormatter(detailed_formatter)
    error_handler.setFormatter(detailed_formatter)
    console_handler.setFormatter(simple_formatter)
    
    # Add handlers to logger
    logger.addHandler(main_handler)
    logger.addHandler(ops_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)
    
    return logger

# Initialize the logger
logger = setup_logger()
logger.info("🚀 OpenMailBot Backend Starting - Logging initialized")
logger.debug(f"   Log files location: {os.path.join(os.path.dirname(__file__), 'logs')}")
logger.debug(f"   Main log: app.log | Operations log: operations.log | Errors log: errors.log")

# # ── Startup diagnostic logger ──────────────────────────────────────────────
# logging.basicConfig(
#     level=logging.DEBUG,
#     format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
#     stream=sys.stdout,
# )
# _slog = logging.getLogger("startup")

# _slog.info("▶ 1/10 stdlib imports OK")

# try:
#     from config import settings
#     _slog.info(f"▶ 2/10 config imported — HOST={settings.HOST} PORT={settings.PORT} "
#                f"LLM={settings.LLM_PROVIDER} EMB={settings.EMBEDDING_PROVIDER} "
#                f"VEC={settings.VECTOR_PROVIDER} BACKEND={settings.BACKEND_API_URL}")
# except Exception as e:
#     _slog.exception(f"✗ 2/10 config FAILED: {e}")
#     sys.exit(1)

# try:
#     from services.chat_pipeline import ChatWithThreadPipeline
#     _slog.info("▶ 3/10 ChatWithThreadPipeline imported")
# except Exception as e:
#     _slog.exception(f"✗ 3/10 ChatWithThreadPipeline FAILED: {e}")

# try:
#     from services.draft_pipeline import DraftPipeline
#     _slog.info("▶ 4/10 DraftPipeline imported")
# except Exception as e:
#     _slog.exception(f"✗ 4/10 DraftPipeline FAILED: {e}")

# try:
#     from services.settings_manager import SettingsManager
#     _slog.info("▶ 5/10 SettingsManager imported")
# except Exception as e:
#     _slog.exception(f"✗ 5/10 SettingsManager FAILED: {e}")

# try:
#     from services.preprocessing_emails import EmailPreprocessingPipeline
#     _slog.info("▶ 6/10 EmailPreprocessingPipeline imported")
# except Exception as e:
#     _slog.exception(f"✗ 6/10 EmailPreprocessingPipeline FAILED: {e}")

# try:
#     from services.label_pipeline import EmailLabelPipeline
#     _slog.info("▶ 7/10 EmailLabelPipeline imported")
# except Exception as e:
#     _slog.exception(f"✗ 7/10 EmailLabelPipeline FAILED: {e}")

# try:
#     from services.label_email_lockbook import get_user_lockbook, get_global_lockbook
#     _slog.info("▶ 8/10 lockbook imported")
# except Exception as e:
#     _slog.exception(f"✗ 8/10 lockbook FAILED: {e}")

# try:
#     from services.store_pipeline import CheckAndStoreEmailPipeline, CheckAndStoreAttachmentsPipeline
#     _slog.info("▶ 9/10 store pipelines imported")
# except Exception as e:
#     _slog.exception(f"✗ 9/10 store pipelines FAILED: {e}")

# try:
#     from agent_request_logger import log_request
#     _slog.info("▶ 10/10 agent_request_logger imported")
# except Exception as e:
#     _slog.warning(f"⚠ 10/10 agent_request_logger not found (using no-op): {e}")
#     def log_request(*args, **kwargs):
#         pass

# _slog.info("✅ All imports done — building FastAPI app")






# Import request logger
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
try:
    from agent_request_logger import log_request
except:
    def log_request(*args, **kwargs):
        pass  # Fallback if logger not available

# Import backend IMAP services
try:
    from backend.services.imap_database import IMAPDatabaseManager
    from backend.services.imap_fetcher import IMAPFetcherService
    _imap_available = True
except ImportError as e:
    print(f"⚠️  IMAP services not available: {e}")
    _imap_available = False
    IMAPDatabaseManager = None
    IMAPFetcherService = None


def _load_config() -> dict:
    """Load config from relative path, fall back to empty dict gracefully."""
    candidates = [
        os.path.join(os.path.dirname(__file__), "config.json"),
        os.getenv("OPENMAILBOT_CONFIG_PATH", ""),
    ]
    for path in candidates:
        path = os.path.abspath(path)
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}

CONFIG = _load_config()

# _slog.info("▶ Loading config.json...")
# CONFIG = _load_config()
# _slog.info(f"▶ CONFIG keys loaded: {list(CONFIG.keys())}")

# In-memory job store for background task tracking
_job_store: Dict[str, Dict[str, Any]] = {}
_job_store_lock = threading.Lock()

# In-memory auto-draft tracking for push notifications
# Structure: {user_id: [{thread_id, draft_content, subject, created_at}, ...]}
_auto_drafts: Dict[str, List[Dict[str, Any]]] = {}
_auto_drafts_lock = threading.Lock()


def _set_job(job_id: str, status: str, result: Any = None, error: str = None):
    with _job_store_lock:
        _job_store[job_id] = {
            "status": status,       # "pending" | "processing" | "done" | "error"
            "result": result,
            "error": error,
            "updated_at": datetime.utcnow().isoformat(),
        }


def _register_auto_draft(user_id: str, thread_id: str, draft_content: str, subject: str = ""):
    """
    Register a newly auto-generated draft for push notification to Thunderbird.
    
    Args:
        user_id: User's email address
        thread_id: Thread ID
        draft_content: The generated draft
        subject: Email subject (for context)
    """
    with _auto_drafts_lock:
        if user_id not in _auto_drafts:
            _auto_drafts[user_id] = []
        
        _auto_drafts[user_id].append({
            "thread_id": thread_id,
            "draft_content": draft_content,
            "subject": subject,
            "created_at": datetime.utcnow().isoformat(),
        })
        logger.info(f"✅ Registered auto-draft for {user_id} — thread {thread_id}")


def _get_auto_drafts(user_id: str, consume: bool = False) -> List[Dict[str, Any]]:
    """
    Get pending auto-drafts for a user.
    
    Args:
        user_id: User's email address
        consume: If True, clear the queue after returning (so they're only shown once)
        
    Returns:
        List of pending auto-drafts
    """
    with _auto_drafts_lock:
        drafts = _auto_drafts.get(user_id, [])
        result = list(drafts)  # Make a copy
        if consume:
            _auto_drafts[user_id] = []
        return result


app = FastAPI(
    title="OpenMailBot Agent",
    description="AI processing backend for OpenMailBot",
    version="1.0.0"
)
logger.info("✅ FastAPI app initialized")

# ──────────────────────────────────────────────────────────────────────────────
# REQUEST LOGGING MIDDLEWARE - Log all incoming requests
# ──────────────────────────────────────────────────────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import time
import sys

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Log incoming request
        start_time = time.time()
        method = request.method
        path = request.url.path
        query_string = request.url.query
        
        log_msg = f"📨 [{method}] {path}"
        if query_string:
            log_msg += f" | Query: {query_string}"
        print(f"\n{log_msg}", flush=True)
        logger.debug(log_msg)
        
        # For POST/PUT/PATCH, try to log body info without consuming it
        if method in ["POST", "PUT", "PATCH"] and "/api/settings" in path:
            try:
                # Get body without consuming the stream
                body = await request.body()
                if body:
                    body_data = json.loads(body)
                    user_id = body_data.get("user_id", "unknown")
                    settings_count = len(body_data.get("settings", {})) if isinstance(body_data.get("settings"), dict) else 0
                    body_log = f"📋 User: {user_id}, Settings: {settings_count}"
                    print(f"   {body_log}", flush=True)
                    logger.debug(body_log)
                    
                    # Important: Receive the body again for the endpoint handler
                    # We need to create a new receive callable that returns the cached body
                    async def receive():
                        return {"type": "http.request", "body": body}
                    request._receive = receive
            except Exception as e:
                error_msg = f"⚠️  Could not parse body: {e}"
                print(f"   {error_msg}", flush=True)
                logger.warning(error_msg)
        
        # Call the actual route handler
        response = await call_next(request)
        
        # Log response
        process_time = time.time() - start_time
        status = response.status_code
        status_emoji = "✅" if status == 200 else "⚠️ " if status >= 400 else "ℹ️ "
        response_log = f"{status_emoji} Status {status} ({process_time:.3f}s)"
        print(f"   {response_log}", flush=True)
        logger.info(f"[{method}] {path} - Status {status} ({process_time:.3f}s)")
        
        return response

# Add the middleware to the app
app.add_middleware(RequestLoggingMiddleware)

# Initialize IMAP fetcher service
_imap_fetcher = None
if _imap_available:
    try:
        _imap_fetcher = IMAPFetcherService(
            db_manager=IMAPDatabaseManager(),
            agent_url=os.getenv("AGENT_URL", "http://localhost:5051"),
            enable_label_classification=os.getenv("ENABLE_LABEL_CLASSIFICATION", "true").lower() == "true"
        )
        logger.info("✅ IMAP Fetcher Service initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize IMAP Fetcher: {e}", exc_info=True)
        _imap_fetcher = None
else:
    logger.warning("⚠️  IMAP services not available")


# ──────────────────────────────────────────────────────────────────────────────
# CONTINUOUS IMAP MONITORING BACKGROUND THREAD
# ──────────────────────────────────────────────────────────────────────────────

_imap_monitoring_active = False
_imap_monitoring_thread = None

def _start_continuous_imap_monitoring():
    """
    Start a background thread that monitors and fetches emails continuously.
    Runs every 60 seconds for all enabled users.
    """
    global _imap_monitoring_active, _imap_monitoring_thread
    
    if not _imap_available or _imap_fetcher is None:
        logger.warning("⚠️  IMAP monitoring not started: IMAP service not available")
        return
    
    def imap_monitor_loop():
        """Continuous monitoring loop - runs every 60 seconds"""
        import time
        
        logger.info("🔄 IMAP Background Monitor Started (runs every 60 seconds)")
        print("🔄 IMAP Background Monitor Started (runs every 60 seconds)")
        _imap_monitoring_active = True
        
        while _imap_monitoring_active:
            try:
                # Get all enabled IMAP users
                enabled_users = _imap_fetcher.db.get_all_enabled_users()
                
                if enabled_users:
                    msg = f"📧 [IMAP MONITOR] Checking {len(enabled_users)} enabled user(s)"
                    logger.info(msg)
                    print(f"\n{msg}")
                    
                    for user_record in enabled_users:
                        try:
                            # user_record could be a dict or tuple
                            if isinstance(user_record, dict):
                                user_id = user_record.get('user_id') or user_record.get('email')
                            elif isinstance(user_record, (tuple, list)):
                                user_id = user_record[0] if len(user_record) > 0 else None
                            else:
                                user_id = str(user_record)
                            
                            if not user_id:
                                logger.warning(f"⚠️  Could not extract user_id from: {user_record}")
                                print(f"   ⚠️  Could not extract user_id from: {user_record}")
                                continue
                            
                            count, error = _imap_fetcher.fetch_and_process_for_user(user_id)
                            if error:
                                logger.error(f"⚠️  {user_id}: {error}")
                                print(f"   ⚠️  {user_id}: {error}")
                            else:
                                logger.info(f"✅ {user_id}: {count} email(s)")
                                print(f"   ✅ {user_id}: {count} email(s)")
                        except Exception as e:
                            logger.error(f"❌ Error processing user: {str(e)}", exc_info=True)
                            print(f"   ❌ Error processing user: {str(e)}")
                
                # Sleep for 60 seconds before next check
                for i in range(60):
                    if not _imap_monitoring_active:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"❌ IMAP Monitor Error: {str(e)}", exc_info=True)
                print(f"❌ IMAP Monitor Error: {str(e)}")
                time.sleep(5)  # Wait 5 seconds before retrying
    
    # Start monitoring in a daemon thread
    _imap_monitoring_thread = threading.Thread(
        target=imap_monitor_loop,
        daemon=True,
        name="IMAPMonitor"
    )
    _imap_monitoring_thread.start()
    logger.info("✅ IMAP Continuous Monitor Thread Started")
    print("✅ IMAP Continuous Monitor Thread Started")


# Start continuous IMAP monitoring on app startup
_start_continuous_imap_monitoring()


# Data Storage Pipeline Configuration
BASE_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def normalize_thread_id(thread_id: str) -> str:
    """
    Normalize a thread ID to a canonical form so that the same email thread
    submitted from different clients (Gmail Add-on vs Thunderbird) is stored
    as a single entry in ChromaDB.

    Conversion rules:
    ┌─────────────────────────────────┬────────────────────────────────────────────┐
    │ Input format                    │ Output                                      │
    ├─────────────────────────────────┼────────────────────────────────────────────┤
    │ Large decimal (X-GM-THRID IMAP) │ Lowercase hex  e.g. "17f1a2b3c4d5e6f7"     │
    │ 16-char hex (GAS thread.getId)  │ Lowercase hex (unchanged)                   │
    │ RFC Message-ID  <abc@host>      │ Returned as-is                              │
    │ Outlook Conversation-ID         │ Returned as-is (stripped)                   │
    │ Anything else                   │ Stripped of surrounding whitespace          │
    └─────────────────────────────────┴────────────────────────────────────────────┘
    """
    if not thread_id:
        return thread_id
    tid = thread_id.strip()
    # Strip RFC Message-ID angle bracket wrappers: <local@domain> → local@domain
    if tid.startswith('<') and tid.endswith('>'):
        tid = tid[1:-1].strip()
    # Large decimal integer → convert to lowercase hex (X-GM-THRID from IMAP)
    if re.fullmatch(r'\d{10,20}', tid):
        try:
            return format(int(tid), 'x')
        except (ValueError, OverflowError):
            pass
    return tid


def get_user_data_dir(user_id: str) -> Dict[str, str]:
    """
    Get all data directories for a specific user.
    Creates user-isolated folder structure:
    data/
    └── {user_id}/
        ├── log_emails/
        ├── store_attachments/
        ├── vector_db/
        └── sql_data/
            ├── chat_thread_processing.db
            └── draft_processing.db
    """
    user_data_dir = os.path.join(BASE_DATA_DIR, user_id)
    
    dirs = {
        "user_base": user_data_dir,
        "log_emails": os.path.join(user_data_dir, "log_emails"),
        "attachments": os.path.join(user_data_dir, "store_attachments"),
        "vector_db": os.path.join(user_data_dir, "vector_db"),
        "sql_data": os.path.join(user_data_dir, "sql_data"),
    }
    
    # Create all directories
    for dir_path in dirs.values():
        os.makedirs(dir_path, exist_ok=True)
    
    return dirs


def get_sql_db_paths(user_id: str) -> Dict[str, str]:
    """Get SQLite database file paths for a user"""
    sql_dir = os.path.join(BASE_DATA_DIR, user_id, "sql_data")
    os.makedirs(sql_dir, exist_ok=True)
    
    return {
        "chat_thread_db": os.path.join(sql_dir, "chat_thread_processing.db"),
        "draft_db": os.path.join(sql_dir, "draft_processing.db"),
    }


# CORS
# Configure CORS to allow requests from Thunderbird add-on (moz-extension://) and other clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.BACKEND_API_URL,
        "http://localhost:3001",
        "http://localhost:3000",
        "http://omb.manotr.com",  # Production frontend
        "moz-extension://*",  # Thunderbird add-on origin
        "*"  # Allow all origins as fallback
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom exception handler for validation errors
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    """Handle validation errors with detailed messages"""
    error_details = []
    for error in exc.errors():
        error_details.append({
            "field": ".".join(str(x) for x in error["loc"][1:]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    print(f"Validation Error: {error_details}")
    
    return {
        "detail": "Request validation failed",
        "errors": error_details,
        "body": str(exc.body) if hasattr(exc, 'body') else None
    }

# Initialize services
#db_client = MongoDBClient(settings.MONGODB_URI)
# embedding_service = EmbeddingService()
# rag_service = RAGService()
# llm_service = LLMService()
#ingestion_service = EmailIngestionService()
#file_processor = FileProcessor()
# Pipelines will be initialized per-user in endpoints
#slack_service = SlackIngestionService(
#    backend_url=settings.BACKEND_API_URL,
#    llm_service=llm_service,
#    file_processor=file_processor
#)


# ==================== Data Storage Helper Functions ====================

def clean_email_body(body):
    """
    Clean email body by removing:
    - HTML tags and code
    - All URLs/links
    - Email disclaimers
    - Excessive whitespace
    Using only Python regex (no external libraries except html)
    """
    if not body:
        return ""
    
    # Decode HTML entities first (e.g., &nbsp; &lt; &gt; &amp;)
    body = html.unescape(body)
    
    # Remove HTML comments
    body = re.sub(r'<!--.*?-->', '', body, flags=re.DOTALL)
    
    # Remove script and style tags with their content
    body = re.sub(r'<script[^>]*>.*?</script>', '', body, flags=re.DOTALL | re.IGNORECASE)
    body = re.sub(r'<style[^>]*>.*?</style>', '', body, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove all HTML tags
    body = re.sub(r'<[^>]+>', '', body)
    
    # Remove all URLs (multiple patterns for comprehensive coverage)
    # http:// and https:// URLs
    body = re.sub(r'https?://[^\s<>"{}|\\^`\[\]]+', '', body)
    # www. URLs without protocol
    body = re.sub(r'www\.[^\s<>"{}|\\^`\[\]]+', '', body)
    # Remove email-style links with <> brackets
    body = re.sub(r'<[^\s]+@[^\s]+>', '', body)
    # Remove mailto: links
    body = re.sub(r'mailto:[^\s]+', '', body)
    
    # Remove common email disclaimers (case insensitive, multiline)
    disclaimer_patterns = [
        r'this\s+email.*?confidential.*?intended.*?recipient.*?(?:\n|$)',
        r'confidentiality\s+notice:.*?(?:\n\n|\Z)',
        r'disclaimer:.*?(?:\n\n|\Z)',
        r'this\s+message.*?confidential.*?(?:\n\n|\Z)',
        r'if\s+you.*?not.*?intended\s+recipient.*?(?:\n\n|\Z)',
        r'please\s+consider\s+the\s+environment\s+before\s+printing.*?(?:\n|$)',
        r'virus.*?free.*?checked.*?(?:\n\n|\Z)',
        r'unsubscribe.*?(?:\n\n|\Z)',
        r'to\s+unsubscribe.*?(?:\n|$)',
        r'click\s+here\s+to.*?(?:\n|$)',
        r'you\s+received\s+this\s+email\s+because.*?(?:\n\n|\Z)',
    ]
    
    for pattern in disclaimer_patterns:
        body = re.sub(pattern, '', body, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove email signatures (common patterns)
    # Standard -- separator
    body = re.sub(r'\n--\s*\n.*', '', body, flags=re.DOTALL)
    # Long separator lines
    body = re.sub(r'\n_{5,}.*', '', body, flags=re.DOTALL)
    body = re.sub(r'\n={5,}.*', '', body, flags=re.DOTALL)
    body = re.sub(r'\n-{5,}.*', '', body, flags=re.DOTALL)
    
    # Remove common signature patterns
    body = re.sub(r'\n(best\s+regards?|sincerely|thanks?|cheers|regards),?\s*\n.*', '', body, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove excessive whitespace
    body = re.sub(r'\n{3,}', '\n\n', body)  # Multiple newlines to max 2
    body = re.sub(r'[ \t]+', ' ', body)  # Multiple spaces/tabs to single space
    body = re.sub(r' +\n', '\n', body)  # Trailing spaces before newline
    body = re.sub(r'\n ', '\n', body)  # Leading spaces after newline
    
    return body.strip()


def extract_new_content(body):
    """
    Remove quoted/nested email content from body
    Returns only the new content written in this specific message
    """
    if not body:
        return ""
    
    lines = body.split('\n')
    new_content = []
    
    for line in lines:
        # Stop at common quote indicators
        # "On Thu, Jan 22, 2026 at 10:34 AM ... wrote:"
        if re.match(r'^On .+wrote:\s*$', line.strip()):
            break
        # Lines starting with ">"
        if re.match(r'^>\s*', line):
            break
        # Email headers in forwarded messages
        if re.match(r'^From:\s*', line.strip()):
            break
        # Separator lines
        if re.match(r'^-{3,}', line.strip()):
            break
        # Alternative quote pattern with email
        if 'wrote:' in line and '@' in line and '<' in line:
            break
            
        new_content.append(line)
    
    # Join and clean up
    result = '\n'.join(new_content).strip()
    
    # Remove excessive blank lines
    result = re.sub(r'\n{3,}', '\n\n', result)
    
    return result


def deduplicate_messages(messages):
    """
    Process messages to extract only new content from each message
    Removes nested/quoted email content, HTML, links, and disclaimers
    """
    processed = []
    
    for msg in messages:
        raw_body = msg.get('body', '')
        
        # Step 1: Extract new content (remove quoted/nested emails)
        new_content = extract_new_content(raw_body)
        
        # Step 2: Clean the content (remove HTML, links, disclaimers)
        clean_body = clean_email_body(new_content)
        
        # Create new message object with cleaned body
        processed_msg = {
            'message_id': msg.get('message_id'),
            'from': msg.get('from'),
            'to': msg.get('to'),
            'subject': msg.get('subject'),
            'timestamp': msg.get('timestamp'),
            'body': clean_body
        }
        
        processed.append(processed_msg)
    
    return processed


def clean_thread_data(user_id: str, thread_id: str):
    """
    Delete stored email logs and attachments for a thread after pipeline processing is complete.
    
    This function safely removes:
    - data/{user_id}/log_emails/{thread_id}/
    - data/{user_id}/store_attachments/{thread_id}/
    
    Error handling ensures cleanup failures don't break the main pipeline.
    
    Args:
        user_id: The user's ID
        thread_id: The normalized thread ID (already normalized via normalize_thread_id())
    """
    logger = logging.getLogger(__name__)
    
    try:
        user_dirs = get_user_data_dir(user_id)
        
        # Path 1: Delete log_emails/{thread_id}
        log_thread_path = os.path.join(user_dirs["log_emails"], thread_id)
        if os.path.exists(log_thread_path):
            try:
                import shutil
                shutil.rmtree(log_thread_path)
                logger.info(f"   [cleanup] Deleted log_emails: {log_thread_path}")
            except Exception as e:
                logger.warning(f"   [cleanup] Failed to delete log_emails {log_thread_path}: {str(e)}")
        
        # Path 2: Delete store_attachments/{thread_id}
        attachments_thread_path = os.path.join(user_dirs["attachments"], thread_id)
        if os.path.exists(attachments_thread_path):
            try:
                import shutil
                shutil.rmtree(attachments_thread_path)
                logger.info(f"   [cleanup] Deleted attachments: {attachments_thread_path}")
            except Exception as e:
                logger.warning(f"   [cleanup] Failed to delete attachments {attachments_thread_path}: {str(e)}")
        
        logger.info(f"✅ Cleanup complete for thread {thread_id}")
        
    except Exception as e:
        logger.warning(f"   [cleanup] Unexpected error during cleanup: {str(e)}", exc_info=True)
        # Note: Don't raise - cleanup failures should not break the pipeline


# Request/Response Models
class EmailData(BaseModel):
    from_address: str = Field(..., alias="from")
    to: List[str]
    subject: str
    content: str
    timestamp: datetime
    message_id: Optional[str] = None
    thread_id: Optional[str] = None


class SummarizeRequest(BaseModel):
    emails: List[EmailData]
    userId: str
    tenantId: str


class GenerateReplyRequest(BaseModel):
    email: EmailData
    threadContext: List[EmailData]
    tone: str = "professional"
    additionalContext: Optional[str] = None
    userId: str
    tenantId: str


class RAGQueryRequest(BaseModel):
    query: str
    userId: str
    tenantId: str
    emailContext: Optional[EmailData] = None


class RelatedThreadsRequest(BaseModel):
    threadId: str
    userId: str
    tenantId: str
    limit: int = 5


class IngestEmailsRequest(BaseModel):
    userId: str
    tenantId: str
    provider: str  # "google" or "microsoft"
    accessToken: str
    syncFrom: Optional[datetime] = None


# ==================== Data Storage Request Models ====================

class EmailMessage(BaseModel):
    message_id: str
    from_address: str
    to: List[str]
    subject: str
    timestamp: str
    body: str


class SimpleDraftRequest(BaseModel):
    user_id: str
    thread_id: str
    last_message_id: Optional[str] = None  # Last message ID for cache validation
    user_preferences: Optional[Dict[str, Any]] = None


class LogEmailRequest(BaseModel):
    user_id: str
    thread_id: str
    gmail_thread_id: Optional[str] = None  # Real Gmail hex thread ID for Gmail REST API (thread_id may be canonical RFC Message-ID)
    messages: List[EmailMessage]
    access_token: Optional[str] = None  # Gmail OAuth token for server-side label push
    attachments: Optional[List["AttachmentData"]] = None  # Optional attachments to store alongside labeling


class AttachmentData(BaseModel):
    filename: str
    content: str  # base64 encoded
    mime_type: str = "application/octet-stream"


class StoreAttachmentsRequest(BaseModel):
    user_id: str
    thread_id: str
    message_id: str
    attachments: List[AttachmentData]


# Root route
@app.get("/")
async def root():
    """Root endpoint — confirms the server is running"""
    return {
        "service": "openmailbot-agent",
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "docs": "/docs",
        "health": "/health"
    }


# Suppress browser favicon 404 noise
@app.get("/favicon.ico", status_code=204)
async def favicon():
    return None


# ==================== Provider Validation Endpoint ====================

class ValidateProviderRequest(BaseModel):
    provider_type: str          # "llm" | "embedding" | "vector"
    provider: str               # "openai" | "anthropic" | "groq" | "ollama" | "pinecone" | "qdrant"
    api_key: Optional[str] = None
    base_url: Optional[str] = None  # Ollama URL or vector DB URL
    model: Optional[str] = None     # optional model to verify


@app.post("/api/validate-provider")
async def validate_provider(request: ValidateProviderRequest):
    """
    Validate a provider's API key / connectivity without consuming tokens.

    Uses each provider's lightweight listing / health endpoint:
      - OpenAI / Groq     → GET /v1/models          (returns model list, 0 tokens)
      - Anthropic          → GET /v1/models          (same, 0 tokens)
      - Ollama             → GET {base_url}/api/tags (lists installed models)
      - Pinecone           → GET /indexes            (lists indexes)
      - Qdrant (self-host) → GET /healthz            (health probe)

    Returns:
      { "valid": bool, "message": str, "models": [...] }
    """
    import httpx as _httpx

    provider = request.provider.lower()
    api_key  = (request.api_key or "").strip()
    base_url = (request.base_url or "").rstrip("/")
    models: List[str] = []

    try:
        async with _httpx.AsyncClient(timeout=15.0) as client:

            # ── OpenAI ──────────────────────────────────────────────────────
            if provider == "openai":
                if not api_key:
                    return {"valid": False, "message": "OpenAI API key is required.", "models": []}
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # Filter models based on provider type
                    if request.provider_type == "llm":
                        # Only include chat/completion models, exclude embeddings, audio, moderation, etc.
                        models = sorted([m["id"] for m in data.get("data", [])
                                         if not any(x in m["id"] for x in
                                                    ["whisper", "tts", "dall-e", "babbage", "davinci",
                                                     "text-moderation", "embedding", "realtime", "transcribe",
                                                     "ada", "curie", "babbage-002", "davinci-002"])])
                    elif request.provider_type == "embedding":
                        # Only include embedding models
                        models = sorted([m["id"] for m in data.get("data", [])
                                         if "embedding" in m["id"]])
                    else:
                        models = sorted([m["id"] for m in data.get("data", [])])
                    
                    if not models:
                        return {"valid": True, "message": f"OpenAI API key is valid but no {request.provider_type} models found.", "models": []}
                    return {"valid": True, "message": f"OpenAI API key is valid. Found {len(models)} model(s).", "models": models}
                elif resp.status_code == 401:
                    return {"valid": False, "message": "Invalid OpenAI API key.", "models": []}
                else:
                    return {"valid": False, "message": f"OpenAI returned HTTP {resp.status_code}.", "models": []}

            # ── Anthropic ───────────────────────────────────────────────────
            elif provider == "anthropic":
                if not api_key:
                    return {"valid": False, "message": "Anthropic API key is required.", "models": []}
                resp = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01"
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m["id"] for m in data.get("data", [])]
                    return {"valid": True, "message": "Anthropic API key is valid.", "models": models}
                elif resp.status_code == 401:
                    return {"valid": False, "message": "Invalid Anthropic API key.", "models": []}
                else:
                    return {"valid": False, "message": f"Anthropic returned HTTP {resp.status_code}.", "models": []}

            # ── Groq ────────────────────────────────────────────────────────
            elif provider == "groq":
                if not api_key:
                    return {"valid": False, "message": "Groq API key is required.", "models": []}
                resp = await client.get(
                    "https://api.groq.com/openai/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    models = sorted([m["id"] for m in data.get("data", [])])
                    return {"valid": True, "message": "Groq API key is valid.", "models": models}
                elif resp.status_code == 401:
                    return {"valid": False, "message": "Invalid Groq API key.", "models": []}
                else:
                    return {"valid": False, "message": f"Groq returned HTTP {resp.status_code}.", "models": []}

            # ── Ollama ──────────────────────────────────────────────────────
            elif provider == "ollama":
                ollama_url = base_url or "http://localhost:11434"
                headers = {}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                
                # Determine deployment type for better messaging
                is_local = "localhost" in ollama_url or "127.0.0.1" in ollama_url
                is_secured = bool(api_key)
                
                try:
                    resp = await client.get(f"{ollama_url}/api/tags", headers=headers, timeout=10.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        models = [m["name"] for m in data.get("models", [])]
                        
                        # Filter models based on provider type for Ollama
                        if request.provider_type == "embedding":
                            # Prioritize embedding-specific models
                            embedding_keywords = ["embed", "bge", "minilm", "arctic", "mxbai", "nomic"]
                            embedding_models = [m for m in models if any(kw in m.lower() for kw in embedding_keywords)]
                            if embedding_models:
                                models = embedding_models
                        
                        if not models:
                            deployment_info = "Local Ollama" if is_local else "Remote Ollama"
                            return {"valid": True,
                                    "message": f"{deployment_info} is reachable but no models are installed. Run 'ollama pull <model>' first.",
                                    "models": []}
                        
                        deployment_type = ""
                        if is_local:
                            deployment_type = "Local Ollama"
                        elif is_secured:
                            deployment_type = "Remote Ollama (secured)"
                        else:
                            deployment_type = "Remote Ollama"
                        
                        return {"valid": True,
                                "message": f"{deployment_type} is reachable. Found {len(models)} model(s).",
                                "models": sorted(models)}
                    elif resp.status_code == 401:
                        return {"valid": False, "message": "Ollama requires authentication — check your API key.", "models": []}
                    else:
                        return {"valid": False, "message": f"Ollama returned HTTP {resp.status_code}.", "models": []}
                except _httpx.ConnectError:
                    suggestion = "Is Ollama running?" if is_local else "Check the URL and ensure it's publicly accessible."
                    return {"valid": False, "message": f"Cannot connect to Ollama at {ollama_url}. {suggestion}", "models": []}

            # ── Pinecone ────────────────────────────────────────────────────
            elif provider == "pinecone":
                if not api_key:
                    return {"valid": False, "message": "Pinecone API key is required.", "models": []}
                resp = await client.get(
                    "https://api.pinecone.io/indexes",
                    headers={"Api-Key": api_key}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    indexes = [idx.get("name", "") for idx in data.get("indexes", [])]
                    return {"valid": True,
                            "message": f"Pinecone API key is valid. Found {len(indexes)} index(es).",
                            "models": indexes}
                elif resp.status_code == 401:
                    return {"valid": False, "message": "Invalid Pinecone API key.", "models": []}
                else:
                    return {"valid": False, "message": f"Pinecone returned HTTP {resp.status_code}.", "models": []}

            # ── Qdrant ──────────────────────────────────────────────────────
            elif provider == "qdrant":
                qdrant_url = base_url or "http://localhost:6333"
                headers = {}
                if api_key:
                    headers["api-key"] = api_key
                # Try /healthz first, fallback to root
                for probe in [f"{qdrant_url}/healthz", f"{qdrant_url}/"]:
                    try:
                        resp = await client.get(probe, headers=headers)
                        if resp.status_code in (200, 204):
                            return {"valid": True, "message": "Qdrant is reachable and responding.", "models": []}
                    except _httpx.ConnectError:
                        pass
                return {"valid": False, "message": f"Cannot connect to Qdrant at {qdrant_url}.", "models": []}

            else:
                return {"valid": False, "message": f"Unknown provider: {provider}", "models": []}

    except Exception as e:
        return {"valid": False, "message": f"Validation error: {str(e)}", "models": []}


# Health check
@app.get("/health")
async def health_check():
    """Basic health check - returns immediately"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "openmailbot-agent"
    }


# Handshake — used by client onboarding to verify this agent is reachable
@app.get("/handshake")
async def handshake():
    """
    Lightweight connectivity probe for client onboarding.
    Returns a fixed response so the Thunderbird add-on can confirm the
    custom agent URL points to a live OpenMailBot agent before saving it.
    """
    return {
        "status": "ok",
        "handshake": True,
        "service": "openmailbot-agent",
        "timestamp": datetime.utcnow().isoformat(),
    }


# Detailed health check with provider status
@app.get("/health/detailed")
async def detailed_health_check(user_id: Optional[str] = None, tenant_id: Optional[str] = None):
    """
    Detailed health check that tests configured providers.
    Pass user_id and tenant_id to test user-specific provider configuration.
    """
    health_status = {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "openmailbot-agent",
        "providers": {}
    }
    
    # Get effective settings if user context provided
    effective_settings = None
    if user_id and tenant_id:
        # TODO: Fetch from backend /api/settings
        pass
    
    # Test LLM provider
    try:
        # Simple test - just check if provider is configured
        provider = effective_settings.get("llm_provider", "inbuilt") if effective_settings else settings.LLM_PROVIDER
        health_status["providers"]["llm"] = {
            "provider": provider,
            "status": "configured"
        }
    except Exception as e:
        health_status["providers"]["llm"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Test embedding provider
    try:
        provider = effective_settings.get("embedding_provider", "inbuilt") if effective_settings else settings.EMBEDDING_PROVIDER
        health_status["providers"]["embedding"] = {
            "provider": provider,
            "status": "configured"
        }
    except Exception as e:
        health_status["providers"]["embedding"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Test vector provider
    try:
        provider = effective_settings.get("vector_provider", "inbuilt") if effective_settings else settings.VECTOR_PROVIDER
        health_status["providers"]["vector"] = {
            "provider": provider,
            "status": "configured"
        }
    except Exception as e:
        health_status["providers"]["vector"] = {
            "status": "error",
            "error": str(e)
        }
    
    # Set overall status based on provider health
    has_errors = any(
        p.get("status") == "error" 
        for p in health_status["providers"].values()
    )
    if has_errors:
        health_status["status"] = "degraded"
    
    return health_status


# # Email Ingestion
# @app.post("/api/ingest")
# async def ingest_emails(request: IngestEmailsRequest):
#     """Ingest emails from Gmail or Outlook"""
#     try:
#         result = await ingestion_service.ingest_emails(
#             user_id=request.userId,
#             tenant_id=request.tenantId,
#             provider=request.provider,
#             access_token=request.accessToken,
#             sync_from=request.syncFrom
#         )
#         return result
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# Generate Embeddings
# NOTE: embedding_service, llm_service, and rag_service are per-user services
# initialized inside pipelines (ChatWithThreadPipeline, DraftPipeline, etc.).
# These legacy singleton endpoints are disabled to prevent NameError at runtime.
# @app.post("/api/embed")
# async def generate_embeddings(request: Dict[str, Any]):
#     """Generate embeddings for email content"""
#     try:
#         text = request.get("text")
#         user_id = request.get("userId")
#         tenant_id = request.get("tenantId")
#
#         if not text or not user_id or not tenant_id:
#             raise HTTPException(status_code=400, detail="Missing required fields")
#
#         embedding = await embedding_service.generate_embedding(text)
#
#         await embedding_service.store_embedding(
#             embedding=embedding,
#             metadata={"userId": user_id, "tenantId": tenant_id, "text": text[:500]},
#             namespace=f"{tenant_id}_{user_id}"
#         )
#
#         return {"embedding": embedding, "dimension": len(embedding)}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# Summarize Thread — use /api/summarize-thread (SummarizationPipeline) instead.
# @app.post("/api/summarize")
# async def summarize_thread(request: SummarizeRequest):
#     thread_text = "\n\n---\n\n".join([...])
#     summary = await llm_service.summarize(...)  # llm_service is not instantiated globally
#     return {"summary": summary}


# Generate Reply — use /api/draft or /api/draft-with-attachments (DraftPipeline) instead.
# @app.post("/api/generate-reply")
# async def generate_reply(request: GenerateReplyRequest):
#     reply = await llm_service.generate_reply(...)  # llm_service is not instantiated globally
#     return {"reply": reply}


# RAG Query — use /api/chat-with-thread (ChatWithThreadPipeline) instead.
# @app.post("/api/rag")
# async def rag_query(request: RAGQueryRequest):
#     result = await rag_service.query(...)  # rag_service is not instantiated globally
#     return {"answer": result["answer"], "sources": result.get("sources", [])}


# # Related Threads
# @app.post("/api/related-threads")
# async def get_related_threads(request: RelatedThreadsRequest):
#     """Find related email threads using vector similarity"""
#     try:
#         # Get the thread content
#         thread_emails = await db_client.get_emails_by_thread(
#             thread_id=request.threadId,
#             user_id=request.userId,
#             tenant_id=request.tenantId
#         )
        
#         if not thread_emails:
#             return {"relatedThreadIds": []}
        
#         # Generate embedding for the thread
#         thread_text = " ".join([email.get("content", "") for email in thread_emails])
#         thread_embedding = await embedding_service.generate_embedding(thread_text)
        
#         # Find similar threads
#         similar_results = await embedding_service.find_similar(
#             embedding=thread_embedding,
#             namespace=f"{request.tenantId}_{request.userId}",
#             limit=request.limit + 1  # +1 to exclude the query thread itself
#         )
        
#         # Extract thread IDs (excluding the query thread)
#         related_thread_ids = [
#             result["metadata"].get("threadId")
#             for result in similar_results
#             if result["metadata"].get("threadId") != request.threadId
#         ][:request.limit]
        
#         return {"relatedThreadIds": related_thread_ids}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


# Analytics endpoint for sentiment analysis — disabled (llm_service not instantiated globally).
# @app.post("/api/analyze-sentiment")
# async def analyze_sentiment(request: Dict[str, Any]):
#     sentiment = await llm_service.analyze_sentiment(text)
#     return {"sentiment": sentiment}


# Slack Integration Endpoints
class SlackIngestRequest(BaseModel):
    userId: str
    workspaceId: str
    accessToken: str
    botToken: Optional[str] = None
    syncDays: int = 7
    selectedChannels: Optional[List[str]] = None
    selectedDMs: Optional[List[str]] = None
    includePublic: bool = True
    includePrivate: bool = False
    includeDMs: bool = False
    fileConfig: Optional[Dict[str, Any]] = None


# @app.post("/api/slack/ingest")
# async def ingest_slack(request: SlackIngestRequest):
#     """Ingest Slack workspace messages"""
#     try:
#         result = await slack_service.ingest_workspace(
#             user_id=request.userId,
#             workspace_id=request.workspaceId,
#             access_token=request.accessToken,
#             bot_token=request.botToken,
#             sync_days=request.syncDays,
#             selected_channels=request.selectedChannels,
#             selected_dms=request.selectedDMs,
#             include_public=request.includePublic,
#             include_private=request.includePrivate,
#             include_dms=request.includeDMs,
#             file_config=request.fileConfig
#         )
#         return result
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))


class ChatWithThreadRequest(BaseModel):
    user_id: str
    thread_id: str
    question: str


class DraftWithAttachmentsRequest(BaseModel):
    user_id: str
    thread_id: str
    user_preferences: Optional[Dict[str, Any]] = None


class SummarizeThreadRequest(BaseModel):
    """Request model for email thread summarization"""
    user_id: str
    thread_id: str
    user_name: Optional[str] = "User"  # Name for draft response generation


class SyncSettingsRequest(BaseModel):
    user_id: str
    settings: Dict[str, Any]


class EncryptedSettingsRequest(BaseModel):
    """Request model for encrypted settings from add-ons using libsodium."""
    user_id: str
    encrypted_payload: str  # base64-encoded encrypted settings
    key_version: int = 1
    timestamp: Optional[str] = None


@app.get("/api/public-key")
async def get_public_key(user_id: Optional[str] = None):
    """
    Get the public encryption key for client-side settings encryption.
    
    Each user gets their own Ed25519 keypair.
    Add-ons fetch this key during onboarding or settings save and use it to encrypt.
    Backend decrypts using the corresponding private key.
    
    Args:
        user_id: User email or unique identifier. If provided, returns user-specific key.
                If not provided, returns HTTP 400.
    
    Returns:
    {
        "user_id": "user@example.com",
        "public_key": "base64-encoded-key",
        "algorithm": "libsodium/box_seal",
        "key_version": 1,
        "format": "base64",
        "instance_id": "unique-instance-identifier-for-debugging"
    }
    """
    try:
        enc_service = get_encryption_service()
        import socket
        instance_id = f"{socket.gethostname()}:{settings.PORT}"
        
        # If user_id provided, return per-user key
        if user_id:
            print(f"\n📤 GET /api/public-key?user_id={user_id}", flush=True)
            print(f"   🔐 Fetching/generating public key for user encryption", flush=True)
            print(f"   📍 Instance: {instance_id}", flush=True)
            sys.stdout.flush()
            
            key_dict = enc_service.get_user_public_key_dict(user_id)
            key_dict["instance_id"] = instance_id  # Include for debugging
            return key_dict
        else:
            # Fallback: if no user_id, raise error (force user_id)
            print("\n📤 GET /api/public-key called without user_id", flush=True)
            sys.stdout.flush()
            raise HTTPException(
                status_code=400,
                detail="user_id parameter is required"
            )
    except HTTPException:
        raise
    except Exception as e:
        print(f"\n❌ [ERROR] Failed to get public key: {e}", flush=True)
        sys.stdout.flush()
        raise HTTPException(status_code=500, detail=f"Failed to get public key: {str(e)}")


@app.post("/api/settings")
async def sync_settings(request: SyncSettingsRequest, background_tasks: BackgroundTasks):
    """
    Sync user settings from Gmail Add-on to backend (PLAINTEXT - DEPRECATED).
    
    DEPRECATED: New add-ons should use encrypted endpoint.
    This endpoint maintained for backward compatibility.
    
    Request:
    {
        "user_id": "user@example.com",
        "settings": {
            "mode": "custom",
            "llm_provider": "openai",
            "llm_api_key": "sk-...",
            ...
        }
    }
    
    Returns:
    {
        "success": true,
        "message": "Settings synced successfully",
        "user_id": "user@example.com",
        "settings_saved": 15,
        "encrypted": true,
        "transport": "plaintext",
        "warning": "Consider using POST /api/settings/encrypted for better security"
    }
    """
    print("\n" + "="*70, flush=True)
    print("🔧 [REQUEST] POST /api/settings endpoint called (PLAINTEXT - DEPRECATED)", flush=True)
    print(f"   👤 User ID: {request.user_id}", flush=True)
    print(f"   📋 Settings: {list(request.settings.keys())}", flush=True)
    print(f"   ⚠️  Transport: PLAINTEXT - Consider using encrypted endpoint", flush=True)
    print("="*70, flush=True)
    sys.stdout.flush()
    
    try:
        # Initialize settings manager for the user
        settings_manager = SettingsManager(request.user_id)
        
        # Save encrypted settings to database
        success = settings_manager.save_settings(
            request.settings,
            request.user_id,
            "general"
        )
        
        if not success:
            raise Exception("Failed to save settings to database")
        
        print(f"✅ [SAVED] Settings encrypted and stored successfully", flush=True)
        print(f"   📁 Database: data/{request.user_id}/sql_data/chat_thread_processing.db", flush=True)
        print(f"   🔐 Encryption: Enabled (Fernet, at-rest only)", flush=True)
        sys.stdout.flush()
        
        # Check if IMAP server should be enabled
        run_imap = request.settings.get("run_imap_server", False)
        print(f"🔍 [IMAP CHECK] run_imap={run_imap}, _imap_fetcher={'available' if _imap_fetcher else 'None'}", flush=True)
        sys.stdout.flush()
        
        if run_imap and _imap_fetcher is not None:
            # Extract IMAP credentials from settings
            imap_email = request.settings.get("imap_email") or request.user_id
            imap_app_password = request.settings.get("imap_app_password")
            imap_host = request.settings.get("imap_host", "imap.gmail.com")
            imap_port = request.settings.get("imap_port", 993)
            
            if imap_app_password:
                # Add or update user in IMAP database
                db_success = _imap_fetcher.db.add_or_update_user(
                    user_id=request.user_id,
                    email=imap_email,
                    app_password=imap_app_password,
                    imap_host=imap_host,
                    imap_port=imap_port,
                    enabled=True
                )
                
                if db_success:
                    print(f"✅ IMAP enabled for user: {request.user_id}", flush=True)
                    print(f"   📧 Email: {imap_email}", flush=True)
                    print(f"   🌐 Host: {imap_host}:{imap_port}", flush=True)
                    print(f"   🔄 Scheduling background email fetch...", flush=True)
                    
                    # Schedule IMAP email fetch to run in the background (non-blocking)
                    background_tasks.add_task(
                        _imap_fetcher.fetch_and_process_for_user,
                        request.user_id
                    )
                    
                    print(f"✅ Background task queued for IMAP fetch", flush=True)
                else:
                    print(f"❌ Failed to enable IMAP for user: {request.user_id}", flush=True)
            else:
                print(f"⚠️  IMAP enabled but no app_password provided for {request.user_id}", flush=True)
        elif run_imap and _imap_fetcher is None:
            print(f"⚠️  IMAP requested but service not available for {request.user_id}", flush=True)
        
        sys.stdout.flush()
        
        return {
            "success": True,
            "message": "Settings synced successfully",
            "user_id": request.user_id,
            "settings_saved": len(request.settings),
            "encrypted": True,
            "transport": "plaintext",
            "storage": f"data/{request.user_id}/sql_data/chat_thread_processing.db",
            "warning": "This endpoint receives plaintext. Consider POST /api/settings/encrypted for client-side encryption"
        }
    except Exception as e:
        logger.exception(f"❌ Failed to sync settings for {request.user_id}")
        logger.error(f"   Error details: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync settings: {str(e)}"
        )


@app.post("/api/settings/encrypted")
async def sync_settings_encrypted(request: EncryptedSettingsRequest, background_tasks: BackgroundTasks):
    """
    Sync ENCRYPTED user settings from add-ons to backend.
    
    Add-ons encrypt settings client-side using the public key fetched from /api/public-key.
    Backend decrypts using the private key stored in environment variables.
    
    This provides defense-in-depth:
    - Layer 1: Encrypted in transit (libsodium box_seal)
    - Layer 2: Encrypted at-rest (Fernet)
    
    Request:
    {
        "user_id": "user@example.com",
        "encrypted_payload": "base64-encoded-encrypted-settings",
        "key_version": 1,
        "timestamp": "2024-06-02T10:30:00Z"
    }
    
    Returns:
    {
        "success": true,
        "message": "Settings encrypted and stored successfully",
        "user_id": "user@example.com",
        "settings_saved": 15,
        "encrypted": true,
        "transport": "encrypted",
        "storage": "data/{user_id}/sql_data/chat_thread_processing.db"
    }
    """
    print("\n" + "="*70, flush=True)
    print("🔧 [REQUEST] POST /api/settings/encrypted endpoint called", flush=True)
    print(f"   👤 User ID: {request.user_id}", flush=True)
    print(f"   🔐 Payload size: {len(request.encrypted_payload)} bytes (base64)", flush=True)
    print(f"   📅 Timestamp: {request.timestamp}", flush=True)
    print(f"   🔑 Key version: {request.key_version}", flush=True)
    print("="*70, flush=True)
    sys.stdout.flush()
    
    try:
        # Decrypt the settings using user's private key
        enc_service = get_encryption_service()
        settings = enc_service.decrypt_settings_for_user(request.user_id, request.encrypted_payload)
        
        print(f"✅ [DECRYPTED] Successfully decrypted settings for user {request.user_id}", flush=True)
        print(f"   📋 Settings keys: {list(settings.keys())}", flush=True)
        sys.stdout.flush()
        
        # Initialize settings manager for the user
        settings_manager = SettingsManager(request.user_id)
        
        # Save settings with additional Fernet encryption (2nd layer)
        success = settings_manager.save_settings(
            settings,
            request.user_id,
            "general"
        )
        
        if not success:
            raise Exception("Failed to save settings to database")
        
        print(f"✅ [SAVED] Settings encrypted and stored successfully", flush=True)
        print(f"   📁 Database: data/{request.user_id}/sql_data/chat_thread_processing.db", flush=True)
        print(f"   🔐 Transport: Encrypted (libsodium box_seal)", flush=True)
        print(f"   🔐 Storage: Encrypted (Fernet)", flush=True)
        sys.stdout.flush()
        
        # Check if IMAP server should be enabled
        run_imap = settings.get("run_imap_server", False)
        print(f"🔍 [IMAP CHECK] run_imap={run_imap}, _imap_fetcher={'available' if _imap_fetcher else 'None'}", flush=True)
        sys.stdout.flush()
        
        if run_imap and _imap_fetcher is not None:
            # Extract IMAP credentials from settings
            imap_email = settings.get("imap_email") or request.user_id
            imap_app_password = settings.get("imap_app_password")
            imap_host = settings.get("imap_host", "imap.gmail.com")
            imap_port = settings.get("imap_port", 993)
            
            if imap_app_password:
                # Add or update user in IMAP database
                db_success = _imap_fetcher.db.add_or_update_user(
                    user_id=request.user_id,
                    email=imap_email,
                    app_password=imap_app_password,
                    imap_host=imap_host,
                    imap_port=imap_port,
                    enabled=True
                )
                
                if db_success:
                    print(f"✅ IMAP enabled for user: {request.user_id}", flush=True)
                    print(f"   📧 Email: {imap_email}", flush=True)
                    print(f"   🌐 Host: {imap_host}:{imap_port}", flush=True)
                    print(f"   🔄 Scheduling background email fetch...", flush=True)
                    
                    # Schedule IMAP email fetch to run in the background (non-blocking)
                    background_tasks.add_task(
                        _imap_fetcher.fetch_and_process_for_user,
                        request.user_id
                    )
                    
                    print(f"✅ Background task queued for IMAP fetch", flush=True)
                else:
                    print(f"❌ Failed to enable IMAP for user: {request.user_id}", flush=True)
            else:
                print(f"⚠️  IMAP enabled but no app_password provided for {request.user_id}", flush=True)
        elif run_imap and _imap_fetcher is None:
            print(f"⚠️  IMAP requested but service not available for {request.user_id}", flush=True)
        
        sys.stdout.flush()
        
        return {
            "success": True,
            "message": "Settings encrypted and stored successfully",
            "user_id": request.user_id,
            "settings_saved": len(settings),
            "encrypted": True,
            "transport": "encrypted",
            "storage": f"data/{request.user_id}/sql_data/chat_thread_processing.db"
        }
    except ValueError as e:
        # Decryption failed - provide diagnostic help
        error_msg = str(e)
        print(f"\n❌ [ERROR] Decryption failed for {request.user_id}: {error_msg}", flush=True)
        print(f"   🔍 DIAGNOSTIC HINTS:", flush=True)
        print(f"   💡 This error typically occurs when:", flush=True)
        print(f"      1. Add-on's cached public key mismatches backend private key", flush=True)
        print(f"      2. Different backend instances (load balancer) have different keypairs", flush=True)
        print(f"      3. Backend keypair changed between client fetch and data send", flush=True)
        print(f"      4. Network corruption during transmission", flush=True)
        print(f"   🔧 TROUBLESHOOTING STEPS:", flush=True)
        print(f"      1. Client: Delete cached public key (browser.storage.local)", flush=True)
        print(f"      2. Client: Fetch fresh /api/public-key", flush=True)
        print(f"      3. Retry encryption", flush=True)
        print(f"      4. If using load balancer: Configure key sharing across instances", flush=True)
        print(f"   📝 Error details: {error_msg}", flush=True)
        sys.stdout.flush()
        raise HTTPException(
            status_code=400,
            detail=f"Decryption failed: {error_msg}. Try refreshing the public key cache on client."
        )
    except Exception as e:
        logger.exception(f"❌ Failed to sync encrypted settings for {request.user_id}")
        logger.error(f"   Error details: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync encrypted settings: {str(e)}"
        )


@app.post("/api/chat-with-thread")
async def chat_with_thread(request: ChatWithThreadRequest, background_tasks: BackgroundTasks):
    """
    Chat with an email thread using RAG pipeline

    Returns a job_id immediately; heavy processing runs in background.
    Poll /api/job-status/{job_id} until status is "done" or "error".
    """
    job_id = str(uuid.uuid4())
    _set_job(job_id, "pending")
    background_tasks.add_task(_run_chat_pipeline, job_id, request)
    return {"job_id": job_id, "status": "pending"}


def _run_chat_pipeline(job_id: str, request: ChatWithThreadRequest):
    _set_job(job_id, "processing")
    logger = logging.getLogger(__name__)
    try:
        chat_pipeline = ChatWithThreadPipeline(user_id=request.user_id)
        norm_thread_id = normalize_thread_id(request.thread_id)
        result = chat_pipeline.process_and_chat(
            request.user_id,
            norm_thread_id,
            request.question,
        )
        _set_job(job_id, "done", result=result)
        
        # ─ Cleanup stored email data and attachments after pipeline completes ─
        logger.info(f"   [job {job_id}] Pipeline complete, starting cleanup...")
        clean_thread_data(request.user_id, norm_thread_id)
        
    except Exception as e:
        logger.exception(f"❌ [job {job_id}] Chat pipeline error: {str(e)}")
        _set_job(job_id, "error", error=str(e))


@app.post("/api/reset-and-reprocess-thread")
async def reset_and_reprocess_thread(request: ChatWithThreadRequest):
    """
    Clear all embeddings for a thread and re-process from scratch.
    
    Use this when:
    - Embeddings were created before the "document" field was added
    - Search results are showing empty/None content
    - You need to regenerate embeddings with fixed metadata
    
    This will delete old embeddings and re-embed all emails and attachments
    with the correct metadata structure.
    """
    logger = logging.getLogger(__name__)
    try:
        chat_pipeline = ChatWithThreadPipeline(user_id=request.user_id)
        norm_thread_id = normalize_thread_id(request.thread_id)
        
        # Step 1: Clear old embeddings
        logger.info(f"🧹 Clearing embeddings for thread {norm_thread_id}")
        clear_info = chat_pipeline.clear_thread_embeddings(request.user_id, norm_thread_id)
        
        # Step 2: Re-process emails and attachments
        logger.info(f"🔄 Re-processing thread with new metadata structure")
        result = chat_pipeline.process_and_chat(
            request.user_id,
            norm_thread_id,
            request.question
        )
        
        return {
            "success": True,
            "cleared_embeddings": clear_info,
            "reprocessed_result": result
        }
    except Exception as e:
        logger.exception(f"❌ Reset and reprocess thread failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/draft-with-attachments")
async def draft_with_attachments(request: DraftWithAttachmentsRequest, background_tasks: BackgroundTasks):
    """
    Generate email draft with attachment context using hybrid approach

    Returns a job_id immediately; heavy processing runs in background.
    Poll /api/job-status/{job_id} until status is "done" or "error".
    """
    job_id = str(uuid.uuid4())
    _set_job(job_id, "pending")
    background_tasks.add_task(_run_draft_pipeline, job_id, request)
    return {"job_id": job_id, "status": "pending"}


def _run_draft_pipeline(job_id: str, request: DraftWithAttachmentsRequest):
    _set_job(job_id, "processing")
    logger = logging.getLogger(__name__)
    try:
        draft_pipeline = DraftPipeline(user_id=request.user_id)
        norm_thread_id = normalize_thread_id(request.thread_id)
        result = asyncio.run(draft_pipeline.process_email_request(
            request.user_id,
            norm_thread_id,
            request.user_preferences,
        ))
        _set_job(job_id, "done", result=result)
        
        # ─ Cleanup stored email data and attachments after pipeline completes ─
        logger.info(f"   [job {job_id}] Draft pipeline complete, starting cleanup...")
        clean_thread_data(request.user_id, norm_thread_id)
        
    except Exception as e:
        logger.exception(f"❌ [job {job_id}] Draft pipeline error: {str(e)}")
        _set_job(job_id, "error", error=str(e))




def _run_simple_draft_pipeline(job_id: str, request: SimpleDraftRequest):
    _set_job(job_id, "processing")
    logger = logging.getLogger(__name__)
    try:
        pipeline = SimpleDraftPipeline(user_id=request.user_id)
        norm_thread_id = normalize_thread_id(request.thread_id)
        result = asyncio.run(pipeline.process_email_request(
            request.user_id,
            norm_thread_id,
            request.user_preferences,
        ))
        _set_job(job_id, "done", result=result)
        
        # ── SAVE DRAFT TO CACHE ──
        if result.get('success'):
            try:
                last_msg_id = request.last_message_id or norm_thread_id
                cache_manager = DraftCacheManager(request.user_id)
                cache_manager.save_draft(
                    thread_id=norm_thread_id,
                    last_message_id=last_msg_id,
                    draft_content=result.get('draft_content', ''),
                    processing_info=result.get('processing_info', {})
                )
                logger.info(f"✅ Draft saved to cache for thread {norm_thread_id}")
            except Exception as cache_err:
                logger.warning(f"⚠️  Failed to cache draft (non-fatal): {cache_err}")
        
    except Exception as e:
        logger.exception(f"❌ [job {job_id}] Simple draft pipeline error: {str(e)}")
        _set_job(job_id, "error", error=str(e))


@app.post("/api/draft")
async def simple_draft(request: SimpleDraftRequest, background_tasks: BackgroundTasks):
    """
    Generate email draft from thread emails (no attachments).
    
    Checks draft cache first:
    - If last_message_id matches cached version → return cached draft immediately
    - Otherwise → generate new draft and cache it
    
    Returns a job_id immediately; processing runs in background (if cache miss).
    Poll /api/job-status/{job_id} until status is "done" or "error".

    Request:
    {
        "user_id": "user@example.com",
        "thread_id": "thread_123abc",
        "last_message_id": "msg_id_xyz",  # Optional: for cache validation
        "user_preferences": {
            "name": "Alice",
            "position": "Manager",
            "tone": "professional",
            "custom_instructions": ""
        }
    }
    """
    logger = logging.getLogger(__name__)
    job_id = str(uuid.uuid4())
    thread_id = normalize_thread_id(request.thread_id)
    
    # ── CHECK CACHE FIRST ──
    if request.last_message_id:
        try:
            cache_manager = DraftCacheManager(request.user_id)
            
            # First, invalidate any stale cache (if message ID has changed)
            is_stale = cache_manager.invalidate_stale_cache(thread_id, request.last_message_id)
            if is_stale:
                logger.info(f"🗑️  [job {job_id}] Stale cache deleted, regenerating draft...")
            else:
                # If not stale, try to retrieve cached draft
                cached_draft = cache_manager.get_draft(thread_id, request.last_message_id)
                
                if cached_draft:
                    logger.info(f"✅ [job {job_id}] CACHE HIT: Returning cached draft")
                    logger.info(f"   User: {request.user_id}")
                    logger.info(f"   Thread: {thread_id}")
                    logger.info(f"   Message ID: {request.last_message_id}")
                    
                    # Set job as done immediately with cached result
                    _set_job(job_id, "done", result={
                        "success": True,
                        "draft_content": cached_draft.get('draft_content', ''),
                        "processing_info": cached_draft.get('processing_info', {}),
                        "cached": True,
                    })
                    
                    return {"job_id": job_id, "status": "done", "cached": True}
        except Exception as cache_err:
            logger.warning(f"⚠️  Cache lookup failed (non-fatal): {cache_err}")
            # Fall through to generate new draft
    
    # ── CACHE MISS: Generate new draft ──
    logger.info(f"📝 [job {job_id}] Cache miss or no message_id provided — generating new draft")
    _set_job(job_id, "pending")
    background_tasks.add_task(_run_simple_draft_pipeline, job_id, request)
    return {"job_id": job_id, "status": "pending"}




# ==================== SUMMARIZATION ENDPOINTS ====================

@app.post("/api/summarize-thread")
async def summarize_thread(request: SummarizeThreadRequest, background_tasks: BackgroundTasks):
    """
    Summarize an email thread using LLM analysis
    
    Returns a job_id immediately; heavy processing runs in background.
    Poll /api/job-status/{job_id} until status is "done" or "error".
    
    Request:
    {
        "user_id": "user@example.com",
        "thread_id": "thread_123abc",
        "user_name": "Puja"  # Optional, used for draft response
    }
    
    Response:
    {
        "job_id": "uuid-here",
        "status": "pending"
    }
    """
    job_id = str(uuid.uuid4())
    _set_job(job_id, "pending")
    
    logger.info(f"📋 /api/summarize-thread endpoint called")
    logger.info(f"   Job ID: {job_id}")
    logger.info(f"   User: {request.user_id}")
    logger.info(f"   Thread: {request.thread_id}")
    logger.info(f"   User Name: {request.user_name}")
    
    background_tasks.add_task(_run_summarization_pipeline, job_id, request)
    return {"job_id": job_id, "status": "pending"}


def _run_summarization_pipeline(job_id: str, request: SummarizeThreadRequest):
    """Background task for summarization pipeline"""
    _set_job(job_id, "processing")
    logger = logging.getLogger(__name__)
    try:
        summarization_pipeline = SummarizationPipeline(user_id=request.user_id)
        norm_thread_id = normalize_thread_id(request.thread_id)
        result = summarization_pipeline.process_and_summarize(
            user_id=request.user_id,
            thread_id=norm_thread_id
        )
        _set_job(job_id, "done", result=result)
        
        # ─ Cleanup stored email data and attachments after pipeline completes ─
        logger.info(f"   [job {job_id}] Summarization pipeline complete, starting cleanup...")
        clean_thread_data(request.user_id, norm_thread_id)
        
    except Exception as e:
        logger.exception(f"❌ [job {job_id}] Summarization pipeline error: {str(e)}")
        _set_job(job_id, "error", error=str(e))


@app.get("/api/job-status/{job_id}")
async def get_job_status(job_id: str):
    """Poll the status of a background job submitted by chat-with-thread or draft-with-attachments."""
    with _job_store_lock:
        job = _job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}


@app.get("/api/auto-drafts/{user_id}")
async def get_auto_drafts(user_id: str):
    """
    Get pending auto-generated drafts for a user.
    
    This endpoint allows Thunderbird to poll for new auto-drafts that were
    generated from label-email-async (when "Escalation" or "Response" labels are triggered).
    
    When Thunderbird retrieves these drafts, it automatically consumes them
    (they won't be returned again).
    
    Response:
    {
        "user_id": "user@example.com",
        "auto_drafts": [
            {
                "thread_id": "...",
                "draft_content": "...",
                "subject": "...",
                "created_at": "2026-07-15T14:45:06.123456Z"
            },
            ...
        ],
        "count": 2
    }
    """
    drafts = _get_auto_drafts(user_id, consume=True)  # Consume after retrieving
    return {
        "user_id": user_id,
        "auto_drafts": drafts,
        "count": len(drafts),
    }


class SlackChannelsRequest(BaseModel):
    accessToken: str

"""
@app.post("/api/slack/channels")
async def get_slack_channels(request: SlackChannelsRequest):
  
    try:
        import httpx
        
        async with httpx.AsyncClient() as client:
            # Fetch public channels
            public_response = await client.get(
                'https://slack.com/api/conversations.list',
                headers={'Authorization': f'Bearer {request.accessToken}'},
                params={'types': 'public_channel,private_channel', 'exclude_archived': True}
            )
            public_data = public_response.json()
            
            # Fetch DMs
            dm_response = await client.get(
                'https://slack.com/api/conversations.list',
                headers={'Authorization': f'Bearer {request.accessToken}'},
                params={'types': 'im,mpim', 'exclude_archived': True}
            )
            dm_data = dm_response.json()
            
            return {
                "channels": public_data.get('channels', []) if public_data.get('ok') else [],
                "dms": dm_data.get('channels', []) if dm_data.get('ok') else []
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

"""

# ==================== Data Storage Endpoints ====================

@app.post("/api/log-email")
async def log_email_data(request: LogEmailRequest):
    """
    Store all messages from a thread in a single JSON file
    User-isolated storage: data/{user_id}/log_emails/{thread_id}/{thread_id}.json
    
    Automatically deduplicates nested email content, removes HTML, links, and disclaimers
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"✅ /api/log-email endpoint called")
    logger.info(f"   User: {request.user_id}")
    logger.info(f"   Thread: {request.thread_id}")
    logger.info(f"   Messages count: {len(request.messages) if request.messages else 0}")
    print(f"✅ log-email endpoint called for user: {request.user_id}, thread: {request.thread_id}, messages: {len(request.messages) if request.messages else 0}")
    try:
        if not request.messages:
            raise HTTPException(status_code=400, detail="No messages provided")

        # Normalize thread_id so Gmail Add-on (hex) and Thunderbird (X-GM-THRID decimal)
        # map to the identical key, preventing duplicate ChromaDB entries.
        thread_id = normalize_thread_id(request.thread_id)
        if thread_id != request.thread_id:
            logger.info(f"   Thread ID normalized: {request.thread_id!r} → {thread_id!r}")

        # Get user's data directories
        user_dirs = get_user_data_dir(request.user_id)
        log_dir = user_dirs["log_emails"]
        
        # Create thread folder: data/{user_id}/log_emails/thread_xxx/
        thread_folder = os.path.join(log_dir, thread_id)
        os.makedirs(thread_folder, exist_ok=True)
        
        # Convert messages to dict format for deduplication
        messages_dict = [
            {
                'message_id': msg.message_id,
                'from': msg.from_address,
                'to': msg.to,
                'subject': msg.subject,
                'timestamp': msg.timestamp,
                'body': msg.body
            }
            for msg in request.messages
        ]
        
        # Deduplicate messages (remove nested content)
        clean_messages = deduplicate_messages(messages_dict)
        
        # Save as single JSON file: thread_id.json
        filename = f"{thread_id}.json"
        filepath = os.path.join(thread_folder, filename)
        
        # Prepare output data with cleaned messages
        output_data = {
            'thread_id': thread_id,
            'user_id': request.user_id,
            'messages': clean_messages,
            'metadata': {
                'original_message_count': len(request.messages),
                'processed_message_count': len(clean_messages),
                'stored_at': datetime.utcnow().isoformat()
            }
        }
        
        # Write entire thread data as JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"Saved {len(clean_messages)} cleaned messages to: {filepath}")
        
        return {
            "success": True,
            "message": f"Saved {len(clean_messages)} messages (cleaned from {len(request.messages)} original)",
            "user_id": request.user_id,
            "thread_id": thread_id,
            "filepath": filepath,
            "original_count": len(request.messages),
            "clean_count": len(clean_messages)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error saving clean emails for {request.user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/label-email")
async def label_email_data(request: LogEmailRequest):
    """
    Label email thread using preprocessing + labeling pipeline
    
    This endpoint:
    1. Processes emails through preprocessing pipeline (cleaning, deduplication)
    2. Sends processed data to label pipeline
    3. Returns a single label for the thread
    4. Logs metrics to lock book for tracking
    
    For threads with multiple messages, the LAST message is analyzed as it has
    the most importance in determining thread category.
    
    Expected payload (same as /api/log-email):
    {
        "user_id": "user@example.com",
        "thread_id": "thread_xxx",
        "messages": [
            {
                "message_id": "msg_xxx",
                "from_address": "sender@example.com",
                "to": ["recipient@example.com"],
                "subject": "Meeting tomorrow",
                "timestamp": "2026-02-06T10:00:00Z",
                "body": "<html>...</html>"
            }
        ]
    }
    
    Returns:
    {
        "success": true,
        "label": "meeting",
        "user_id": "user@example.com",
        "thread_id": "thread_xxx",
        "messages_processed": 3,
        "classification_method": "rule-based" or "llm"
    }
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"✅ /api/label-email endpoint called")
    logger.info(f"   User: {request.user_id}")
    logger.info(f"   Thread: {request.thread_id}")
    logger.info(f"   Messages count: {len(request.messages) if request.messages else 0}")
    
    try:
        if not request.messages:
            raise HTTPException(status_code=400, detail="No messages provided")

        # Normalize thread_id to prevent duplicate ChromaDB entries from different clients
        thread_id = normalize_thread_id(request.thread_id)
        if thread_id != request.thread_id:
            logger.info(f"   Thread ID normalized: {request.thread_id!r} → {thread_id!r}")

        # Convert messages to dict format for preprocessing
        messages_dict = [
            {
                'message_id': msg.message_id,
                'from': msg.from_address,
                'to': msg.to,
                'subject': msg.subject,
                'timestamp': msg.timestamp,
                'body': msg.body
            }
            for msg in request.messages
        ]
        
        # Step 1: Preprocess messages (clean HTML, remove quotes, etc.)
        preprocessing_pipeline = EmailPreprocessingPipeline()
        processed_messages = preprocessing_pipeline.process(messages_dict)
        
        logger.info(f"   Preprocessed {len(processed_messages)} messages")
        
        # Step 1.5: Store preprocessed messages in same format as /api/log-email
        user_dirs = get_user_data_dir(request.user_id)
        log_dir = user_dirs["log_emails"]
        
        # Create thread folder: data/{user_id}/log_emails/thread_xxx/
        thread_folder = os.path.join(log_dir, thread_id)
        os.makedirs(thread_folder, exist_ok=True)
        
        # Save preprocessed messages with thread_id as filename for draft pipeline compatibility
        last_msg_id = request.messages[-1].message_id if request.messages else thread_id
        preprocessed_filename = f"{thread_id}.json"
        preprocessed_filepath = os.path.join(thread_folder, preprocessed_filename)
        
        # Prepare output data with preprocessed messages
        preprocessed_output_data = {
            'thread_id': thread_id,
            'user_id': request.user_id,
            'messages': processed_messages,
            'metadata': {
                'original_message_count': len(request.messages),
                'processed_message_count': len(processed_messages),
                'processing_type': 'preprocessing_pipeline',
                'stored_at': datetime.utcnow().isoformat()
            }
        }
        
        # Write preprocessed thread data as JSON
        with open(preprocessed_filepath, 'w', encoding='utf-8') as f:
            json.dump(preprocessed_output_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"   Stored preprocessed messages to: {preprocessed_filepath}")
        
        # Step 2: Label the thread using the processed messages
        label_pipeline = EmailLabelPipeline(user_id=request.user_id)
        
        # Label the thread (focuses on last message)
        # Label and store thread in graph database — offload to thread pool to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        label_and_store_result = await loop.run_in_executor(
            None,
            partial(
                label_pipeline.label_and_store_thread,
                thread_id=thread_id,
                messages=processed_messages,
                user_id=request.user_id,
            )
        )
        
        label = label_and_store_result["label_result"]
        
        logger.info(f"✅ Email labeled: {label}")
        
        # ─ Cleanup stored email data and attachments after pipeline completes ─
        logger.info(f"   Labeling complete, starting cleanup...")
        clean_thread_data(request.user_id, thread_id)
        
        return {
            "success": True,
            "label": label["label"],
            "category": label["category"],
            "topic": label["topic"],
            "subtopic": label["subtopic"],
            "user_id": request.user_id,
            "thread_id": thread_id,
            "messages_processed": len(processed_messages),
            # "graph_store_status": None,  # DISABLED: graph storage
            # "graph_store_steps": 0          # DISABLED: graph storage
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error labeling email: {str(e)}")
        logger.exception(f"   Traceback details")
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# Gmail REST API helper — applies a label directly on the user's mailbox
# ===========================================================================

# Max time the async labeler may spend before giving up (60 min for production, change to 5 * 60 for testing)
_LABEL_PUSH_TIMEOUT_SECONDS = 60 * 60

# Color palette — verified from official Gmail API docs (April 2026):
# https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.labels
# Full allowed palette: #000000 #434343 #666666 #999999 #cccccc #efefef #f3f3f3 #ffffff
#   #fb4c2f #ffad47 #fad165 #16a766 #43d692 #4a86e8 #a479e2 #f691b3
#   #f6c5be #ffe6c7 #fef1d1 #b9e4d0 #c6f3de #c9daf8 #e4d7f5 #fcdee8
#   #efa093 #ffd6a2 #fce8b3 #89d3b2 #a0eac9 #a4c2f4 #d0bcf1 #fbc8d9
#   #e66550 #ffbc6b #fcda83 #44b984 #68dfa9 #6d9eeb #b694e8 #f7a7c0
#   #cc3a21 #eaa041 #f2c960 #149e60 #3dc789 #3c78d8 #8e63ce #e07798
#   #ac2b16 #cf8933 #d5ae49 #0b804b #2a9c68 #285bac #653e9b #b65775
#   #822111 #a46a21 #aa8831 #076239 #1a764d #1c4587 #41236d #83334c
#   #464646 #e7e7e7 #0d3472 #b6cff5 #0d3b44 #98d7e4 #3d188e #e3d7ff
#   #711a36 #fbd3e0 #8a1c0a #f2b2a8 #7a2e0b #ffc8af #7a4706 #ffdeb5
#   #594c05 #fbe983 #684e07 #fdedc1 #0b4f30 #b3efd3 #04502e #a2dcc1
#   #c2c2c2 #4986e7 #2da2bb #b99aff #994a64 #f691b2 #ff7537 #ffad46
#   #662e37 #ebdbde #cca6ac #094228 #42d692 #16a765
_GMAIL_LABEL_COLORS: Dict[str, Dict[str, str]] = {
    "Response":       {"backgroundColor": "#4a86e8", "textColor": "#ffffff"},  # blue
    "Fyi":            {"backgroundColor": "#16a766", "textColor": "#ffffff"},  # green
    "Notification":   {"backgroundColor": "#e7e7e7", "textColor": "#000000"},  # light gray
    "Meeting":        {"backgroundColor": "#653e9b", "textColor": "#ffffff"},  # purple
    "Awaiting reply": {"backgroundColor": "#fad165", "textColor": "#000000"},  # yellow
    "Escalation":     {"backgroundColor": "#cc3a21", "textColor": "#ffffff"},  # dark red
    "Hotels":         {"backgroundColor": "#ffad47", "textColor": "#000000"},  # orange
    "Airline":        {"backgroundColor": "#7a4706", "textColor": "#ffffff"},  # brown
    "Airlines":       {"backgroundColor": "#7a4706", "textColor": "#ffffff"},  # brown
    "Travel":         {"backgroundColor": "#149e60", "textColor": "#ffffff"},  # green
    "Restaurant":     {"backgroundColor": "#ffbc6b", "textColor": "#000000"},  # light orange
    "Booking":        {"backgroundColor": "#4a86e8", "textColor": "#ffffff"},  # blue
    "Bank":           {"backgroundColor": "#2da2bb", "textColor": "#ffffff"},  # teal
    "Recruitment":    {"backgroundColor": "#8e63ce", "textColor": "#ffffff"},  # purple
}


def _apply_gmail_label_sync(
    thread_id: str,
    label_name: str,
    access_token: str,
    logger,
) -> dict:
    """
    Apply *label_name* to *thread_id* using the Gmail REST API.
    Creates the label (with colour) if it does not already exist.
    This is a synchronous function, safe to call from a thread-pool executor.
    Includes detailed logging for all Gmail API calls.
    """
    import requests as _requests

    GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    # Normalise: capitalise first letter so "meeting" → "Meeting"
    formatted = label_name.strip().title()
    
    logger.info(f"🔗 Gmail API: starting label push for thread {thread_id}")
    logger.info(f"   Label name: '{label_name}' → formatted: '{formatted}'")

    # ── Step 1: list existing labels ──────────────────────────────────────
    logger.info(f"🔗 Gmail API [STEP 1/3]: GET /labels (list all labels)")
    try:
        resp = _requests.get(f"{GMAIL_BASE}/labels", headers=headers, timeout=30)
        logger.info(f"   ✓ Response: {resp.status_code} OK")
        
        if resp.status_code != 200:
            logger.error(f"   ✗ FAILED: {resp.status_code}")
            logger.error(f"   Error body: {resp.text[:500]}")
            raise RuntimeError(
                f"Gmail list-labels failed [{resp.status_code}]: {resp.text[:300]}"
            )
        
        labels_data = resp.json()
        all_labels = labels_data.get("labels", [])
        logger.info(f"   Found {len(all_labels)} existing labels in Gmail account")
        
        existing = {lbl["name"].lower(): lbl["id"] for lbl in all_labels}
        label_id = existing.get(formatted.lower())
        
        if label_id:
            logger.info(f"   ✓ Label '{formatted}' found in account → ID: {label_id}")
        else:
            logger.info(f"   ℹ️  Label '{formatted}' NOT in account → will CREATE")
            
    except Exception as e:
        logger.error(f"   ✗ Exception: {str(e)}")
        raise

    # ── Step 2: create label if missing ───────────────────────────────────
    if not label_id:
        logger.info(f"🔗 Gmail API [STEP 2/3]: POST /labels (create label '{formatted}')")
        
        body: Dict[str, Any] = {"name": formatted, "labelListVisibility": "labelShow",
                                 "messageListVisibility": "show"}
        color = _GMAIL_LABEL_COLORS.get(formatted)
        if color:
            body["color"] = color
            logger.info(f"   Color config: {color}")
        
        logger.info(f"   Request body: {body}")
        
        try:
            cr = _requests.post(f"{GMAIL_BASE}/labels", headers=headers, json=body, timeout=30)
            logger.info(f"   ✓ Response: {cr.status_code}")
            
            if cr.status_code not in (200, 201):
                logger.error(f"   ✗ FAILED: {cr.status_code}")
                logger.error(f"   Error body: {cr.text[:500]}")
                raise RuntimeError(
                    f"Gmail create-label failed [{cr.status_code}]: {cr.text[:300]}"
                )
            
            cr_data = cr.json()
            label_id = cr_data.get("id")
            logger.info(f"   ✓ SUCCESS: created label '{formatted}'")
            logger.info(f"   Label ID: {label_id}")
            logger.info(f"   Response data: {cr_data}")
            
        except Exception as e:
            logger.error(f"   ✗ Exception: {str(e)}")
            raise
    else:
        logger.info(f"🔗 Gmail API [STEP 2/3]: SKIP (label already exists)")

    # ── Step 3: apply label to thread ─────────────────────────────────────
    logger.info(f"🔗 Gmail API [STEP 3/3]: POST /threads/{thread_id}/modify")
    logger.info(f"   Applying label ID: {label_id} (name: '{formatted}')")
    logger.info(f"   Request body: {{\"addLabelIds\": [\"{label_id}\"]}}")
    
    try:
        mr = _requests.post(
            f"{GMAIL_BASE}/threads/{thread_id}/modify",
            headers=headers,
            json={"addLabelIds": [label_id]},
            timeout=30,
        )
        logger.info(f"   ✓ Response: {mr.status_code}")
        
        if mr.status_code != 200:
            logger.error(f"   ✗ FAILED: {mr.status_code}")
            logger.error(f"   Error body: {mr.text[:500]}")
            raise RuntimeError(
                f"Gmail modify-thread failed [{mr.status_code}]: {mr.text[:300]}"
            )
        
        mr_data = mr.json()
        logger.info(f"   ✓ SUCCESS: label applied to thread")
        logger.info(f"   Response: {mr_data}")
        logger.info(f"✅ Gmail API: COMPLETE — thread {thread_id} now labeled '{formatted}'")
        
        return {"label_id": label_id, "label_name": formatted}
        
    except Exception as e:
        logger.error(f"   ✗ Exception: {str(e)}")
        raise


async def _capture_tone_for_sent_emails(user_id: str, thread_id: str, processed_messages: List[Dict],
                                    logger=None) -> Dict[str, Any]:
    """
    Captures email tone/style for emails SENT by the user (where from == user_id).
    
    This is called during the label pipeline to extract and store the user's writing
    style, relationship, and tone information. Data is stored per-user in:
        data/{user_id}/tone_db/
    
    Uses the user's configured LLM provider and embedding provider from SettingsManager.
    
    Args:
        user_id: The user's email (primary identifier)
        thread_id: Normalized thread ID
        processed_messages: List of preprocessed message dicts
        logger: Optional logger instance
    
    Returns:
        Dict with tone extraction results: {"captured": int, "errors": [...], "details": [...]}
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    result = {"captured": 0, "errors": [], "details": []}
    
    try:
        base_data_dir = os.path.join(os.path.dirname(__file__), "data")
        tone_manager = TonePipelineManager(user_id, base_data_dir)
        
        for msg in processed_messages:
            # Check if this is a SENT email (from == user_id)
            msg_from = msg.get("from", "").strip().lower()
            user_id_lower = user_id.strip().lower()
            
            if msg_from != user_id_lower:
                # Not a sent email, skip
                continue
            
            # Extract recipients and email body
            recipients = msg.get("to", [])
            email_body = msg.get("body", "")
            message_id = msg.get("message_id")
            
            if not recipients or not email_body:
                logger.warning(f"      [tone] Skipping sent email: missing recipients or body")
                continue
            
            # Process each recipient (user may have sent to multiple people)
            for recipient in recipients:
                recipient = recipient.strip()
                if not recipient:
                    continue
                
                try:
                    logger.info(f"      [tone] Processing sent email to {recipient}")
                    extracted = await tone_manager.process_sent_email(
                        recipient=recipient,
                        email_text=email_body,
                        email_id=message_id
                    )
                    result["captured"] += 1
                    result["details"].append({
                        "recipient": recipient,
                        "tone": extracted.get("writing_style", {}).get("tone"),
                        "relationship": extracted.get("relationship", {}).get("type"),
                    })
                    logger.info(
                        f"      [tone] ✅ Captured tone: {recipient} | "
                        f"Tone={extracted.get('writing_style', {}).get('tone')} | "
                        f"Relationship={extracted.get('relationship', {}).get('type')}"
                    )
                except Exception as e:
                    logger.warning(f"      [tone] ⚠️  Failed to capture tone for {recipient}: {e}")
                    result["errors"].append({"recipient": recipient, "error": str(e)})
        
        tone_manager.close()
        
        if result["captured"] > 0:
            logger.info(f"   ✅ Tone capture: {result['captured']} email(s) processed")
        else:
            logger.info(f"   ℹ️  No sent emails found in thread (tone capture skipped)")
        
        return result
        
    except Exception as e:
        logger.warning(f"   ⚠️  Tone capture error (non-fatal): {e}")
        result["errors"].append({"general": str(e)})
        return result


async def _run_label_and_push_to_gmail(job_id: str, request: LogEmailRequest):
    """
    Background task for /api/label-email-async.

    1. Runs the full label pipeline (preprocessing + LLM/rule-based labeling).
    2. Pushes the resulting label back to Gmail directly via REST API using
       the OAuth access token supplied by the Apps Script caller.
    3. Updates the job-store so callers can still poll /api/job-status/{job_id}.

    Timeout: _LABEL_PUSH_TIMEOUT_SECONDS (5 min for testing).
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"")
    logger.info(f"╔════════════════════════════════════════════════════════════════╗")
    logger.info(f"║         BACKGROUND JOB: label-email-async START                 ║")
    logger.info(f"╚════════════════════════════════════════════════════════════════╝")
    logger.info(f"Job ID:       {job_id}")
    logger.info(f"User:         {request.user_id}")
    logger.info(f"Thread:       {request.thread_id}")
    logger.info(f"Messages:     {len(request.messages)}")
    logger.info(f"Has token:    {'Yes' if request.access_token else 'No'}")
    logger.info(f"Timeout:      {_LABEL_PUSH_TIMEOUT_SECONDS}s ({_LABEL_PUSH_TIMEOUT_SECONDS // 60} min)")
    logger.info(f"")
    
    _set_job(job_id, "processing")

    lockbook = get_user_lockbook(request.user_id)
    global_lockbook = get_global_lockbook()

    # Normalize thread_id once — all storage and API calls below use this value
    thread_id = normalize_thread_id(request.thread_id)
    if thread_id != request.thread_id:
        logger.info(f"   [job {job_id}] Thread ID normalized: {request.thread_id!r} → {thread_id!r}")

    try:
        # ── Preprocessing ────────────────────────────────────────────────
        messages_dict = [
            {
                "message_id": msg.message_id,
                "from": msg.from_address,
                "to": msg.to,
                "subject": msg.subject,
                "timestamp": msg.timestamp,
                "body": msg.body,
            }
            for msg in request.messages
        ]
        preprocessing_pipeline = EmailPreprocessingPipeline()
        processed_messages = preprocessing_pipeline.process(messages_dict)
        logger.info(f"   [job {job_id}] Preprocessed {len(processed_messages)} msg(s)")

        # ── Persist preprocessed emails ──────────────────────────────────
        user_dirs = get_user_data_dir(request.user_id)
        thread_folder = os.path.join(user_dirs["log_emails"], thread_id)
        os.makedirs(thread_folder, exist_ok=True)
        last_msg_id = request.messages[-1].message_id if request.messages else thread_id
        with open(os.path.join(thread_folder, f"{thread_id}.json"), "w", encoding="utf-8") as f:
            json.dump(
                {
                    "thread_id": thread_id,
                    "user_id": request.user_id,
                    "messages": processed_messages,
                    "metadata": {
                        "original_message_count": len(request.messages),
                        "processed_message_count": len(processed_messages),
                        "processing_type": "preprocessing_pipeline_async",
                        "stored_at": datetime.utcnow().isoformat(),
                    },
                },
                f,
                indent=2,
                ensure_ascii=False,
            )

        # ── Save attachments to disk (non-fatal, before vector store) ────
        if request.attachments:
            try:
                attach_dir = os.path.join(user_dirs["attachments"], thread_id)
                os.makedirs(attach_dir, exist_ok=True)
                last_msg_id = request.messages[-1].message_id if request.messages else thread_id
                saved_attach = []
                for att in request.attachments:
                    safe_name = "".join(c for c in att.filename if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()
                    safe_path = os.path.join(attach_dir, f"{last_msg_id}_{safe_name}")
                    try:
                        with open(safe_path, "wb") as af:
                            af.write(base64.b64decode(att.content))
                        saved_attach.append({"filename": safe_name, "filepath": safe_path, "mime_type": att.mime_type})
                    except Exception as att_err:
                        logger.warning(f"   [job {job_id}] Failed to save attachment '{att.filename}': {att_err}")
                # Write metadata file alongside saved files
                att_meta_path = os.path.join(attach_dir, f"{last_msg_id}_metadata.json")
                with open(att_meta_path, "w", encoding="utf-8") as mf:
                    json.dump({
                        "user_id": request.user_id,
                        "thread_id": thread_id,
                        "message_id": last_msg_id,
                        "timestamp": datetime.utcnow().isoformat(),
                        "attachments": saved_attach,
                    }, mf, indent=2)
                logger.info(f"   [job {job_id}] Saved {len(saved_attach)} attachment(s) to disk")
            except Exception as att_disk_err:
                logger.warning(f"   [job {job_id}] Attachment disk-save error (non-fatal): {att_disk_err}")

        # ── Vector store (DISABLED for label process) ──────────────────────────────────────
        # NOTE: Embedding creation is disabled for label API routes.
        # Emails are preprocessed and stored to disk, but NOT embedded into vector DB.
        logger.info(f"   [job {job_id}] Skipping vector store (embedding creation disabled for label process)")

        # ── Label pipeline (CPU-bound, run in thread pool) ────────────────
        label_pipeline = EmailLabelPipeline(user_id=request.user_id)
        loop = asyncio.get_running_loop()
        label_and_store_result = await loop.run_in_executor(
            None,
            partial(
                label_pipeline.label_and_store_thread,
                thread_id=thread_id,
                messages=processed_messages,
                user_id=request.user_id,
            ),
        )
        label_name: str = label_and_store_result["label_result"]["label"]
        # graph_status = label_and_store_result.get("graph_store_result") or {}  # DISABLED: graph storage
        logger.info(f"   [job {job_id}] Label determined: '{label_name}'")

        # ── Tone capture for SENT emails (non-fatal) ──────────────────────
        try:
            tone_result = await _capture_tone_for_sent_emails(
                user_id=request.user_id,
                thread_id=thread_id,
                processed_messages=processed_messages,
                logger=logger
            )
            if tone_result["captured"] > 0:
                logger.info(f"   [job {job_id}] Tone capture: {tone_result}")
        except Exception as tone_err:
            logger.warning(f"   [job {job_id}] Tone capture failed (non-fatal): {tone_err}")

        # ── Push label to Gmail via REST API ──────────────────────────────
        gmail_result: Dict[str, Any] = {}
        if request.access_token and request.access_token != "thunderbird_addon":
            # Use gmail_thread_id (Gmail's hex ID) for the REST API call.
            # thread_id may be a canonical RFC Message-ID used for ChromaDB — Gmail
            # rejects anything other than its own 16-char hex thread IDs.
            gmail_api_thread_id = request.gmail_thread_id or thread_id
            logger.info(f"📬 [job {job_id}] Starting Gmail API label push (background task)")
            logger.info(f"   Thread ID (canonical): {thread_id}")
            logger.info(f"   Thread ID (Gmail API): {gmail_api_thread_id}")
            logger.info(f"   Label: '{label_name}'")
            logger.info(f"   Access token: {request.access_token[:20]}..." if len(request.access_token) > 20 else request.access_token)
            try:
                logger.info(f"📤 [job {job_id}] Calling _apply_gmail_label_sync in thread pool executor...")
                gmail_result = await loop.run_in_executor(
                    None,
                    partial(
                        _apply_gmail_label_sync,
                        thread_id=gmail_api_thread_id,
                        label_name=label_name,
                        access_token=request.access_token,
                        logger=logger,
                    ),
                )
                logger.info(f"✅ [job {job_id}] Gmail API push SUCCEEDED")
                logger.info(f"   Result: {gmail_result}")
            except Exception as gmail_err:
                logger.error(f"❌ [job {job_id}] Gmail API push FAILED")
                logger.error(f"   Error: {str(gmail_err)}")
                import traceback
                logger.error(f"   Traceback: {traceback.format_exc()}")
                gmail_result = {"error": str(gmail_err)}
        else:
            if request.access_token == "thunderbird_addon":
                logger.info(f"📧 [job {job_id}] Thunderbird add-on detected — skipping Gmail API push")
                logger.info(f"   ℹ️  Labels applied locally by Thunderbird client")
                gmail_result = {"skipped": "thunderbird_addon"}
            else:
                logger.warning(f"⚠️ [job {job_id}] No access_token provided — skipping Gmail API push")

        # ── AUTO-DRAFT TRIGGER (if label is Escalation or Response) ───────
        auto_draft_result = None
        last_msg_id = request.messages[-1].message_id if request.messages else thread_id
        
        if label_name in ["Escalation", "Response"]:
            logger.info(f"")
            logger.info(f"⚡ [job {job_id}] Label '{label_name}' triggers AUTO-DRAFT")
            logger.info(f"   Starting draft pipeline...")
            _set_job(job_id, "processing")  # Update status to show processing
            
            try:
                # Build draft request from label request
                draft_request = SimpleDraftRequest(
                    user_id=request.user_id,
                    thread_id=thread_id,
                    last_message_id=last_msg_id,
                    user_preferences=None  # Not available in LogEmailRequest
                )
                
                # Run draft pipeline inline (awaitable)
                logger.info(f"   [job {job_id}] Calling SimpleDraftPipeline.process_email_request()...")
                pipeline = SimpleDraftPipeline(user_id=request.user_id)
                auto_draft_result = await pipeline.process_email_request(
                    request.user_id,
                    thread_id,
                    None,  # user_preferences not available in LogEmailRequest
                )
                
                if auto_draft_result.get('success'):
                    logger.info(f"✅ [job {job_id}] Auto-draft generated successfully")
                    logger.info(f"   Draft length: {len(auto_draft_result.get('draft_content', ''))} chars")
                    logger.info(f"   Processing info: {auto_draft_result.get('processing_info', {})}")
                    
                    # ── SAVE DRAFT TO CACHE ──
                    try:
                        cache_manager = DraftCacheManager(request.user_id)
                        cache_manager.save_draft(
                            thread_id=thread_id,
                            last_message_id=last_msg_id,
                            draft_content=auto_draft_result.get('draft_content', ''),
                            processing_info=auto_draft_result.get('processing_info', {})
                        )
                        logger.info(f"✅ [job {job_id}] Draft saved to cache")
                        
                        # ── REGISTER AUTO-DRAFT FOR THUNDERBIRD ──
                        # Extract subject from first message for context
                        subject = processed_messages[0].get('subject', 'Re: Thread') if processed_messages else 'Re: Thread'
                        _register_auto_draft(
                            user_id=request.user_id,
                            thread_id=thread_id,
                            draft_content=auto_draft_result.get('draft_content', ''),
                            subject=subject
                        )
                        logger.info(f"✅ [job {job_id}] Auto-draft registered for Thunderbird push")
                    except Exception as cache_err:
                        logger.warning(f"⚠️  [job {job_id}] Failed to cache draft (non-fatal): {cache_err}")
                else:
                    logger.warning(f"⚠️  [job {job_id}] Draft generation failed: {auto_draft_result.get('error', 'Unknown error')}")
                    auto_draft_result = {
                        "generated": False,
                        "error": auto_draft_result.get('error', 'Unknown error')
                    }
                
            except Exception as draft_err:
                logger.error(f"❌ [job {job_id}] Auto-draft pipeline error: {str(draft_err)}")
                import traceback
                logger.error(f"   Traceback: {traceback.format_exc()}")
                auto_draft_result = {
                    "generated": False,
                    "error": str(draft_err)
                }

        # ── Lock-book metrics ─────────────────────────────────────────────
        num_stored = 0  # Graph storage disabled
        for lb in (lockbook, global_lockbook):
            try:
                lb.log_request(
                    thread_id=thread_id,
                    label=label_name,
                    num_labeled=len(processed_messages),
                    num_graph_stored=num_stored,
                    status="SUCCESS",
                )
            except Exception:
                pass

        _set_job(
            job_id,
            "done",
            result={
                "label": label_name,
                "thread_id": thread_id,
                "messages_processed": len(processed_messages),
                "gmail_push": gmail_result,
                "auto_draft": auto_draft_result,  # NEW: Auto-generated draft if triggered
            },
        )
        
        # ─ Cleanup stored email data and attachments after pipeline completes ─
        # NOTE: If auto-draft was triggered, SimpleDraftPipeline handles cleanup
        # Only cleanup here if auto-draft was NOT triggered
        if auto_draft_result is None:
            logger.info(f"   [job {job_id}] Labeling complete, starting cleanup...")
            clean_thread_data(request.user_id, thread_id)
        else:
            logger.info(f"   [job {job_id}] Labeling complete (cleanup handled by auto-draft pipeline)")
        
        logger.info(f"✅ JOB COMPLETED SUCCESSFULLY")
        logger.info(f"   Label: '{label_name}'")
        logger.info(f"   Gmail push: {'SUCCESS' if 'label_id' in gmail_result else 'SKIPPED/FAILED'}")
        logger.info(f"   Messages processed: {len(processed_messages)}")
        logger.info(f"╔════════════════════════════════════════════════════════════════╗")
        logger.info(f"║         BACKGROUND JOB: label-email-async COMPLETE            ║")
        logger.info(f"╚════════════════════════════════════════════════════════════════╝")
        logger.info(f"")

    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"❌ JOB FAILED")
        logger.error(f"   Error: {str(e)}")
        logger.error(f"   Traceback:\n{tb}")
        logger.error(f"╔════════════════════════════════════════════════════════════════╗")
        logger.error(f"║         BACKGROUND JOB: label-email-async FAILED              ║")
        logger.error(f"╚════════════════════════════════════════════════════════════════╝")
        try:
            lockbook.log_request(
                thread_id=request.thread_id, label="error",
                num_labeled=0, num_graph_stored=0, status="FAILED"
            )
            global_lockbook.log_request(
                thread_id=request.thread_id, label="error",
                num_labeled=0, num_graph_stored=0, status="FAILED"
            )
        except Exception:
            pass
        _set_job(job_id, "error", error=str(e))
        
        # ─ Cleanup stored email data and attachments even on error ─
        try:
            norm_thread_id = normalize_thread_id(request.thread_id)
            logger.info(f"   [job {job_id}] Error occurred, attempting cleanup...")
            clean_thread_data(request.user_id, norm_thread_id)
        except Exception as cleanup_err:
            logger.warning(f"   [job {job_id}] Cleanup failed: {str(cleanup_err)}")


@app.post("/api/label-email-async", status_code=202)
async def label_email_async(
    request: LogEmailRequest,
    background_tasks: BackgroundTasks,
):
    """
    Server-push labeling (202 Accepted).

    Flow:
      1. Apps Script sends thread data + OAuth access_token → 202 returned immediately.
      2. Server runs the full label pipeline in the background (max 5 min).
      3. Server calls Gmail REST API (users.threads.modify) to apply the label
         directly — no polling required from the client.
      4. Job status is still available via GET /api/job-status/{job_id} if needed.

    Expected payload (extends /api/label-email):
    {
        "user_id": "user@example.com",
        "thread_id": "thread_xxx",
        "messages": [ ... ],
        "access_token": "ya29.xxx"   ← from ScriptApp.getOAuthToken()
    }

    Returns (202):
    {
        "job_id": "uuid",
        "status": "pending",
        "message": "Processing in background; label will be applied via Gmail API"
    }
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"")
    logger.info(f"📨 /api/label-email-async endpoint received")
    logger.info(f"   User:       {request.user_id}")
    logger.info(f"   Thread:     {request.thread_id}")
    logger.info(f"   Messages:   {len(request.messages)}")
    logger.info(f"   Token:      {request.access_token[:20]}..." if request.access_token and len(request.access_token) > 20 else f"   Token:      {request.access_token}")

    if not request.access_token:
        logger.error(f"❌ No access_token provided")
        raise HTTPException(
            status_code=400,
            detail="access_token is required for server-push labeling",
        )
    if not request.messages:
        logger.error(f"❌ No messages provided")
        raise HTTPException(status_code=400, detail="No messages provided")

    job_id = str(uuid.uuid4())
    logger.info(f"")
    logger.info(f"🆔 Job ID: {job_id}")
    logger.info(f"✅ Job queued for background processing")
    logger.info(f"")
    
    _set_job(job_id, "pending")
    background_tasks.add_task(_run_label_and_push_to_gmail, job_id, request)
    
    logger.info(f"📤 Returning 202 Accepted immediately (async processing)")
    logger.info(f"   Poll status: GET /api/job-status/{job_id}")
    
    return {
        "job_id": job_id,
        "status": "pending",
        "message": "Processing in background; label will be applied via Gmail API",
    }


@app.post("/api/store-attachments")
async def store_attachments(request: StoreAttachmentsRequest):
    """
    Store email attachments
    User-isolated storage: data/{user_id}/store_attachments/{thread_id}/
    
    Expected payload:
    {
        "user_id": "user@example.com",
        "thread_id": "thread_xxx",
        "message_id": "msg_xxx",
        "attachments": [
            {
                "filename": "document.pdf",
                "content": "base64_encoded_content",
                "mime_type": "application/pdf"
            }
        ]
    }
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"✅ /api/store-attachments endpoint called")
    logger.info(f"   User: {request.user_id}")
    logger.info(f"   Thread: {request.thread_id}")
    logger.info(f"   Attachments count: {len(request.attachments) if request.attachments else 0}")
    print(f"✅ store-attachments endpoint called for user: {request.user_id}, thread: {request.thread_id}, attachments: {len(request.attachments) if request.attachments else 0}")
    
    try:
        if not request.attachments:
            raise HTTPException(status_code=400, detail="No attachments provided")

        # Normalize thread_id for consistent ChromaDB keying
        thread_id = normalize_thread_id(request.thread_id)
        if thread_id != request.thread_id:
            logger.info(f"   Thread ID normalized: {request.thread_id!r} → {thread_id!r}")

        # Get user's data directories
        user_dirs = get_user_data_dir(request.user_id)
        attachment_dir = user_dirs["attachments"]
        
        # Create directory for this thread: data/{user_id}/store_attachments/thread_xxx/
        thread_dir = os.path.join(attachment_dir, thread_id)
        os.makedirs(thread_dir, exist_ok=True)
        
        saved_files = []
        
        for idx, attachment in enumerate(request.attachments):
            filename = attachment.filename
            content = attachment.content
            mime_type = attachment.mime_type
            
            # Sanitize filename
            filename = "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()
            
            # Add message_id prefix to avoid conflicts
            safe_filename = f"{request.message_id}_{filename}"
            filepath = os.path.join(thread_dir, safe_filename)
            
            # Decode base64 content and save
            try:
                file_content = base64.b64decode(content)
                with open(filepath, 'wb') as f:
                    f.write(file_content)
                
                saved_files.append({
                    "filename": safe_filename,
                    "filepath": filepath,
                    "size": len(file_content),
                    "mime_type": mime_type
                })
            except Exception as e:
                saved_files.append({
                    "filename": safe_filename,
                    "error": f"Failed to save: {str(e)}"
                })
        
        # Create metadata file
        metadata = {
            "user_id": request.user_id,
            "thread_id": thread_id,
            "message_id": request.message_id,
            "timestamp": datetime.utcnow().isoformat(),
            "attachments": saved_files
        }
        
        metadata_file = os.path.join(thread_dir, f"{request.message_id}_metadata.json")
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"   Saved {len(saved_files)} attachments to disk")
        
        # Step 2: Embed attachments into vector DB asynchronously
        try:
            attachment_store_result = await CheckAndStoreAttachmentsPipeline(user_id=request.user_id).run(
                request.user_id,
                thread_id,
            )
            logger.info(f"   Attachment vector store: {attachment_store_result}")
        except Exception as store_exc:
            # Non-fatal: log but continue with response
            logger.warning(f"   Attachment vector store step failed (non-fatal): {store_exc}")
            attachment_store_result = None
        
        return {
            "success": True,
            "message": f"Stored {len(saved_files)} attachments",
            "user_id": request.user_id,
            "thread_id": thread_id,
            "saved_files": saved_files,
            "metadata_file": metadata_file,
            "vector_store_result": attachment_store_result
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Lock Book Endpoints ====================

@app.get("/api/label-email/metrics")
async def get_label_email_metrics(user_id: Optional[str] = None):
    """
    Get label-email metrics from lock book
    
    Returns:
    {
        "user_id": "user@example.com",
        "created_at": "2026-02-20T10:00:00",
        "last_updated": "2026-02-20T11:30:00",
        "metrics": {
            "total_requests": 150,
            "total_labeled_emails": 450,
            "total_graph_stored": 430,
            "by_label": {
                "meeting": {
                    "count": 45,
                    "emails_labeled": 135,
                    "emails_graph_stored": 130
                },
                ...
            }
        }
    }
    """
    try:
        if user_id:
            lockbook = get_user_lockbook(user_id)
            metrics = lockbook.get_metrics()
            return {
                "success": True,
                "data": metrics,
                "lockbook_file": f"data/lockbook/label_email_metrics_{user_id}.json"
            }
        else:
            # Return global metrics
            global_lockbook = get_global_lockbook()
            metrics = global_lockbook.get_metrics()
            return {
                "success": True,
                "data": metrics,
                "lockbook_file": "data/lockbook/label_email_metrics_global.json"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/label-email/recent-requests")
async def get_recent_requests(user_id: Optional[str] = None, limit: int = 20):
    """
    Get recent label-email requests from lock book
    
    Parameters:
    - user_id: Optional user ID (if not provided, uses global metrics)
    - limit: Number of recent requests to return (default: 20, max: 100)
    
    Returns:
    {
        "success": true,
        "count": 20,
        "recent_requests": [
            {
                "timestamp": "2026-02-20T11:30:45.123456",
                "thread_id": "thread_xxx",
                "label": "meeting",
                "emails_labeled": 3,
                "emails_graph_stored": 3,
                "status": "SUCCESS"
            },
            ...
        ]
    }
    """
    try:
        # Limit max to 100
        limit = min(limit, 100)
        
        if user_id:
            lockbook = get_user_lockbook(user_id)
        else:
            lockbook = get_global_lockbook()
        
        recent = lockbook.get_recent_requests(limit)
        return {
            "success": True,
            "count": len(recent),
            "recent_requests": recent
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/label-email/label-stats")
async def get_label_stats(user_id: Optional[str] = None, label: Optional[str] = None):
    """
    Get statistics for specific label(s)
    
    Parameters:
    - user_id: Optional user ID (if not provided, uses global metrics)
    - label: Optional specific label name (if not provided, returns all labels)
    
    Returns:
    {
        "success": true,
        "label": "meeting",
        "stats": {
            "count": 45,
            "emails_labeled": 135,
            "emails_graph_stored": 130
        }
    }
    or
    {
        "success": true,
        "label": null,
        "stats": { ... all labels ... }
    }
    """
    try:
        if user_id:
            lockbook = get_user_lockbook(user_id)
        else:
            lockbook = get_global_lockbook()
        
        stats = lockbook.get_label_stats(label)
        return {
            "success": True,
            "label": label,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# SETTINGS MANAGEMENT ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/settings")
async def get_settings_by_email(user_id: str = None):
    """
    Fetch user settings by email/ID
    
    **Query Parameters:**
    - user_id (required): User email address or ID
    
    **Returns:**
    - Settings object with all user configurations
    - Defaults if user has no saved settings
    
    **Example:**
    ```
    GET /api/settings?user_id=ankitgoel2004@gmail.com
    
    Response:
    {
        "success": true,
        "user_id": "ankitgoel2004@gmail.com",
        "settings": {
            "mode": "inbuilt",
            "llm_provider": "openai",
            "llm_model": "gpt-4o-mini",
            ...
        },
        "source": "database"
    }
    ```
    """
    if not user_id:
        raise HTTPException(
            status_code=400, 
            detail="Missing required parameter: user_id"
        )
    
    try:
        manager = SettingsManager(user_id=user_id)
        settings = manager.get_settings()
        
        return {
            "success": True,
            "user_id": user_id,
            "settings": settings,
            "source": "database" if settings else "defaults",
            "message": "Settings retrieved successfully"
        }
    except Exception as e:
        print(f"[Settings] Error fetching settings for {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error fetching settings: {str(e)}"
        )

@app.get("/api/settings/{user_id}")
async def get_settings_by_path(user_id: str):
    """
    Fetch user settings by path parameter
    
    Alternative to /api/settings?user_id=... 
    
    **Path Parameters:**
    - user_id: User email or ID (URL encoded)
    
    **Returns:**
    - Settings object with all configurations
    
    **Example:**
    ```
    GET /api/settings/ankitgoel2004@gmail.com
    ```
    """
    if not user_id:
        raise HTTPException(
            status_code=400, 
            detail="Missing user_id in path"
        )
    
    print(f"\n📖 [REQUEST] GET /api/settings endpoint", flush=True)
    print(f"   👤 User ID: {user_id}", flush=True)
    sys.stdout.flush()
    
    try:
        manager = SettingsManager(user_id=user_id)
        settings = manager.get_settings()
        
        print(f"✅ [RETRIEVED] Settings loaded for {user_id}", flush=True)
        print(f"   📊 Fields: {len(settings) if settings else 0}", flush=True)
        sys.stdout.flush()
        
        return {
            "success": True,
            "user_id": user_id,
            "settings": settings,
            "source": "database" if settings else "defaults",
            "message": "Settings retrieved successfully"
        }
    except Exception as e:
        print(f"\n❌ [ERROR] Failed to retrieve settings for {user_id}", flush=True)
        print(f"   Error: {str(e)}", flush=True)
        sys.stdout.flush()
        raise HTTPException(
            status_code=500, 
            detail=f"Error fetching settings: {str(e)}"
        )

@app.delete("/api/settings/{user_id}")
async def delete_settings(user_id: str):
    """
    Delete all settings for a user
    
    **Path Parameters:**
    - user_id: User email or ID
    
    **Returns:**
    - Confirmation of deletion
    
    **Warning:**
    This action cannot be undone. All user settings will be reset to defaults.
    
    **Example:**
    ```
    DELETE /api/settings/ankitgoel2004@gmail.com
    ```
    """
    if not user_id:
        raise HTTPException(
            status_code=400, 
            detail="Missing user_id in path"
        )
    
    try:
        manager = SettingsManager(user_id=user_id)
        manager.clear_settings()
        
        return {
            "success": True,
            "user_id": user_id,
            "message": "Settings deleted successfully. User will use defaults on next login."
        }
    except Exception as e:
        print(f"[Settings] Error deleting settings for {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error deleting settings: {str(e)}"
        )

@app.get("/api/settings/{user_id}/validate")
async def validate_settings(user_id: str):
    """
    Validate that settings are properly configured
    
    **Returns:**
    - Validation status for each provider
    - Any configuration issues
    
    **Example:**
    ```
    GET /api/settings/ankitgoel2004@gmail.com/validate
    
    Response:
    {
        "success": true,
        "user_id": "ankitgoel2004@gmail.com",
        "valid": true,
        "checks": {
            "llm_provider": "✅ openai configured",
            "embedding_provider": "✅ inbuilt",
            "vector_provider": "✅ inbuilt"
        }
    }
    ```
    """
    if not user_id:
        raise HTTPException(
            status_code=400, 
            detail="Missing user_id in path"
        )
    
    try:
        manager = SettingsManager(user_id=user_id)
        settings = manager.get_settings()
        
        checks = {}
        valid = True
        
        # Validate LLM provider
        llm_provider = settings.get("llm_provider", "inbuilt")
        if llm_provider == "custom" and not settings.get("llm_api_key"):
            checks["llm_provider"] = "⚠️ API key required for custom provider"
            valid = False
        else:
            checks["llm_provider"] = f"✅ {llm_provider} configured"
        
        # Validate embedding provider
        emb_provider = settings.get("embedding_provider", "inbuilt")
        if emb_provider == "custom" and not settings.get("embedding_api_key"):
            checks["embedding_provider"] = "⚠️ API key required for custom provider"
            valid = False
        else:
            checks["embedding_provider"] = f"✅ {emb_provider} configured"
        
        # Validate vector provider
        vec_provider = settings.get("vector_provider", "inbuilt")
        if vec_provider == "custom" and not settings.get("vector_url"):
            checks["vector_provider"] = "⚠️ URL required for custom provider"
            valid = False
        else:
            checks["vector_provider"] = f"✅ {vec_provider} configured"
        
        return {
            "success": True,
            "user_id": user_id,
            "valid": valid,
            "checks": checks
        }
    except Exception as e:
        print(f"[Settings] Error validating settings for {user_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error validating settings: {str(e)}"
        )


# ============================================================================
# IMAP EMAIL FETCHING ENDPOINTS
# ============================================================================

@app.post("/api/imap/fetch")
async def trigger_imap_fetch(user_id: Optional[str] = None):
    """
    Trigger IMAP email fetching manually
    
    **Query Parameters:**
    - user_id: Optional. If provided, fetch only for this user. 
               If omitted, fetch for all enabled users.
    
    **Returns:**
    - Number of emails fetched
    - Status for each user
    
    **Example:**
    ```
    POST /api/imap/fetch?user_id=user@example.com
    POST /api/imap/fetch  (fetch for all users)
    
    Response:
    {
        "success": true,
        "total_users": 3,
        "total_emails": 15,
        "results": [
            {
                "user_id": "user1@example.com",
                "emails_fetched": 5,
                "success": true,
                "error": null
            },
            ...
        ]
    }
    ```
    """
    if _imap_fetcher is None:
        raise HTTPException(
            status_code=503,
            detail="IMAP service not available"
        )
    
    try:
        if user_id:
            # Fetch for specific user
            count, error = _imap_fetcher.fetch_and_process_for_user(user_id)
            return {
                "success": error is None,
                "total_users": 1,
                "total_emails": count,
                "results": [{
                    "user_id": user_id,
                    "emails_fetched": count,
                    "success": error is None,
                    "error": error
                }]
            }
        else:
            # Fetch for all users
            result = _imap_fetcher.fetch_and_process_all_users()
            return {
                "success": True,
                **result
            }
    except Exception as e:
        print(f"[IMAP] Error triggering fetch: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error triggering IMAP fetch: {str(e)}"
        )


@app.get("/api/imap/status")
async def get_imap_status(user_id: Optional[str] = None):
    """
    Get IMAP configuration status
    
    **Query Parameters:**
    - user_id: Optional. If provided, get status for this user.
               If omitted, get status for all users.
    
    **Returns:**
    - IMAP configuration for user(s)
    - Last check timestamps
    
    **Example:**
    ```
    GET /api/imap/status?user_id=user@example.com
    GET /api/imap/status  (all users)
    
    Response:
    {
        "success": true,
        "service_available": true,
        "users": [
            {
                "user_id": "user@example.com",
                "email": "user@gmail.com",
                "enabled": true,
                "last_check": "2026-05-05T10:30:00",
                "imap_host": "imap.gmail.com",
                "imap_port": 993
            },
            ...
        ]
    }
    ```
    """
    if _imap_fetcher is None:
        return {
            "success": False,
            "service_available": False,
            "users": [],
            "message": "IMAP service not available"
        }
    
    try:
        if user_id:
            # Get status for specific user
            user = _imap_fetcher.db.get_user(user_id)
            users = [user] if user else []
        else:
            # Get all users (enabled and disabled)
            users = _imap_fetcher.db.get_all_enabled_users()
        
        # Remove sensitive app_password from response
        for user in users:
            if "app_password" in user:
                user["app_password"] = "****" if user["app_password"] else None
        
        return {
            "success": True,
            "service_available": True,
            "users": users
        }
    except Exception as e:
        print(f"[IMAP] Error getting status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting IMAP status: {str(e)}"
        )


@app.delete("/api/imap/{user_id}")
async def disable_imap_for_user(user_id: str):
    """
    Disable IMAP fetching for a user
    
    **Path Parameters:**
    - user_id: User email or ID
    
    **Returns:**
    - Confirmation of disabling
    
    **Example:**
    ```
    DELETE /api/imap/user@example.com
    ```
    """
    if _imap_fetcher is None:
        raise HTTPException(
            status_code=503,
            detail="IMAP service not available"
        )
    
    try:
        success = _imap_fetcher.db.disable_user(user_id)
        
        if success:
            return {
                "success": True,
                "user_id": user_id,
                "message": "IMAP disabled for user"
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"User {user_id} not found in IMAP database"
            )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[IMAP] Error disabling user: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error disabling IMAP: {str(e)}"
        )


@app.get("/api/label-email/summary")
async def get_lockbook_summary(user_id: Optional[str] = None):
    """
    Get human-readable summary of label-email metrics
    
    Returns formatted text summary showing all metrics
    """
    try:
        if user_id:
            lockbook = get_user_lockbook(user_id)
        else:
            lockbook = get_global_lockbook()
        
        summary = lockbook.get_summary()
        return {
            "success": True,
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN PANEL AND ASSOCIATED ROUTES
# ═══════════════════════════════════════════════════════════════════════════════
from fastapi.responses import HTMLResponse

class AdminLoginRequest(BaseModel):
    username: str
    password: str

class AdminSaveSettingsRequest(BaseModel):
    settings: Dict[str, Any]

@app.get("/admin", response_class=HTMLResponse)
async def serve_admin_panel():
    """Serves the front-end dashboard for OpenMailBot administration."""
    admin_html_path = os.path.join(os.path.dirname(__file__), "admin.html")
    if os.path.exists(admin_html_path):
        try:
            with open(admin_html_path, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read(), status_code=200)
        except Exception as e:
            return HTMLResponse(content=f"Error reading admin.html: {str(e)}", status_code=500)
    else:
        return HTMLResponse(content="Admin HTML template not found. Please ensure admin.html exists in the backend directory.", status_code=404)

@app.post("/api/admin/login")
async def admin_login(request: AdminLoginRequest):
    """Handles admin credentials authentication."""
    if request.username == "admin" and request.password == "admin@123":
        return {"success": True, "token": "admin-token-2026", "message": "Logged in successfully"}
    raise HTTPException(status_code=401, detail="Invalid admin username or password")

@app.get("/api/admin/users")
async def admin_list_users():
    """List all unique users configured on this backend and gather basic stats"""
    users_dict = {}
    
    # Check directory names in backend/data (represent user_ids)
    if os.path.exists(BASE_DATA_DIR):
        for item in os.listdir(BASE_DATA_DIR):
            item_path = os.path.join(BASE_DATA_DIR, item)
            # Filter for email-like directory names that have '@'
            if os.path.isdir(item_path) and "@" in item:
                users_dict[item] = {
                    "user_id": item,
                    "email": item,
                    "imap_enabled": False,
                    "imap_host": "imap.gmail.com",
                    "last_check": None,
                    "emails_count": 0,
                    "attachments_count": 0,
                    "threads_count": 0
                }
    
    # Check imap_users.db
    if _imap_available and _imap_fetcher is not None:
        try:
            conn = sqlite3.connect(_imap_fetcher.db.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, email, imap_host, enabled, last_check FROM imap_users")
            rows = cursor.fetchall()
            for r in rows:
                uid = r[0]
                if uid not in users_dict:
                    users_dict[uid] = {
                        "user_id": uid,
                        "email": r[1],
                        "imap_enabled": bool(r[3]),
                        "imap_host": r[2],
                        "last_check": r[4],
                        "emails_count": 0,
                        "attachments_count": 0,
                        "threads_count": 0
                    }
                else:
                    users_dict[uid]["email"] = r[1]
                    users_dict[uid]["imap_enabled"] = bool(r[3])
                    users_dict[uid]["imap_host"] = r[2]
                    users_dict[uid]["last_check"] = r[4]
            conn.close()
        except Exception as e:
            print(f"Error querying imap_users table for admin: {e}", flush=True)

    # Fill basic stats for each user
    for uid in users_dict:
        db_paths = get_sql_db_paths(uid)
        chat_db = db_paths.get("chat_thread_db")
        if os.path.exists(chat_db):
            try:
                conn = sqlite3.connect(chat_db)
                cursor = conn.cursor()
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='email_embeddings'")
                if cursor.fetchone():
                    cursor.execute("SELECT COUNT(*), COUNT(DISTINCT thread_id) FROM email_embeddings")
                    row = cursor.fetchone()
                    if row:
                        users_dict[uid]["emails_count"] = row[0] or 0
                        users_dict[uid]["threads_count"] = row[1] or 0
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='attachment_processing'")
                if cursor.fetchone():
                    cursor.execute("SELECT COUNT(*) FROM attachment_processing")
                    row = cursor.fetchone()
                    if row:
                        users_dict[uid]["attachments_count"] = row[0] or 0
                conn.close()
            except Exception as e:
                print(f"Error querying user {uid} sqlite DB: {e}", flush=True)

    return {
        "success": True,
        "users": list(users_dict.values())
    }

@app.get("/api/admin/user/{user_id}/stats")
async def admin_get_user_stats(user_id: str):
    """Retrieve full stats for a specific user"""
    stats = {
        "emails_count": 0,
        "attachments_count": 0,
        "threads_count": 0,
        "last_active": None,
        "imap_settings": None
    }
    
    # 1. Fetch from user sqlite
    db_paths = get_sql_db_paths(user_id)
    chat_db = db_paths.get("chat_thread_db")
    if os.path.exists(chat_db):
        try:
            conn = sqlite3.connect(chat_db)
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='email_embeddings'")
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*), COUNT(DISTINCT thread_id), MAX(timestamp) FROM email_embeddings")
                row = cursor.fetchone()
                if row:
                    stats["emails_count"] = row[0] or 0
                    stats["threads_count"] = row[1] or 0
                    stats["last_active"] = row[2]
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='attachment_processing'")
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*) FROM attachment_processing")
                row = cursor.fetchone()
                if row:
                    stats["attachments_count"] = row[0] or 0
            conn.close()
        except Exception as e:
            print(f"Error getting stats for {user_id}: {e}", flush=True)
            
    # 2. Fetch from imap_users
    if _imap_available and _imap_fetcher is not None:
        try:
            user_imap = _imap_fetcher.db.get_user(user_id)
            if user_imap:
                stats["imap_settings"] = {
                    "email": user_imap.get("email"),
                    "host": user_imap.get("imap_host"),
                    "port": user_imap.get("imap_port"),
                    "enabled": user_imap.get("enabled"),
                    "last_check": user_imap.get("last_check")
                }
        except Exception as e:
            print(f"Error reading IMAP DB for user stats {user_id}: {e}", flush=True)
            
    return {
        "success": True,
        "stats": stats
    }

@app.post("/api/admin/user/{user_id}/settings")
async def admin_save_user_settings(user_id: str, request: AdminSaveSettingsRequest, background_tasks: BackgroundTasks):
    try:
        # Initialize settings manager for the user
        settings_manager = SettingsManager(user_id)
        
        # Save settings (will encrypt internally)
        success = settings_manager.save_settings(
            request.settings,
            user_id,
            "general"
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save settings via SettingsManager")
            
        # Update IMAP if configured
        run_imap = request.settings.get("run_imap_server", False)
        if run_imap and _imap_fetcher is not None:
            imap_email = request.settings.get("imap_email") or user_id
            imap_app_password = request.settings.get("imap_app_password")
            imap_host = request.settings.get("imap_host", "imap.gmail.com")
            
            try:
                imap_port = int(request.settings.get("imap_port", 993))
            except:
                imap_port = 993
                
            if imap_app_password:
                db_success = _imap_fetcher.db.add_or_update_user(
                    user_id=user_id,
                    email=imap_email,
                    app_password=imap_app_password,
                    imap_host=imap_host,
                    imap_port=imap_port,
                    enabled=True
                )
                if db_success:
                    background_tasks.add_task(
                        _imap_fetcher.fetch_and_process_for_user,
                        user_id
                    )
        elif not run_imap and _imap_fetcher is not None:
            try:
                # We can just update enabled=False in IMAP database if user exists there
                existing_user = _imap_fetcher.db.get_user(user_id)
                if existing_user:
                    _imap_fetcher.db.add_or_update_user(
                        user_id=user_id,
                        email=existing_user["email"],
                        app_password=existing_user["app_password"],
                        imap_host=existing_user["imap_host"],
                        imap_port=existing_user["imap_port"],
                        enabled=False
                    )
            except Exception as e:
                print(f"Error disabling imap for {user_id}: {e}", flush=True)

        return {
            "success": True,
            "message": "Settings saved successfully",
            "user_id": user_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    logger.info(f"🚀 Starting OpenMailBot Backend Server")
    logger.info(f"   Host: {settings.HOST}")
    logger.info(f"   Port: {settings.PORT}")
    logger.info(f"   Logs: d:/manotr/openmailbot/backend/logs/app.log")
    logger.info(f"   Retention: 5 files x 10MB each")
    print(f"\n🚀 Starting OpenMailBot Backend Server on {settings.HOST}:{settings.PORT}")
    print(f"   Logs will be saved to: backend/logs/app.log\n")
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False  # Disabled due to memory issues with pydantic schema validation
    )

