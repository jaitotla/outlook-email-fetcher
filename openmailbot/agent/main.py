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
import json
import base64
import re
import html
import sqlite3
import asyncio
import uuid
import threading
from functools import partial

from config import settings
#from services.ingestion import EmailIngestionService
# from services.embeddings import EmbeddingService
# from services.rag import RAGService
# from services.llm import LLMService
#from services.slack_ingestion import SlackIngestionService
#from services.file_processor import FileProcessor
from services.chat_pipeline import ChatWithThreadPipeline
from services.draft_pipeline import DraftPipeline
from services.settings_manager import SettingsManager
from services.preprocessing_emails import EmailPreprocessingPipeline
from services.label_pipeline import EmailLabelPipeline
from services.label_email_lockbook import get_user_lockbook, get_global_lockbook
from services.store_pipeline import CheckAndStoreEmailPipeline, CheckAndStoreAttachmentsPipeline
from services.summarization_pipeline import SummarizationPipeline
#from database.mongodb import MongoDBClient
from services.simple_draft_pipeline import SimpleDraftPipeline

import sys
import logging

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


def _set_job(job_id: str, status: str, result: Any = None, error: str = None):
    with _job_store_lock:
        _job_store[job_id] = {
            "status": status,       # "pending" | "processing" | "done" | "error"
            "result": result,
            "error": error,
            "updated_at": datetime.utcnow().isoformat(),
        }


app = FastAPI(
    title="OpenMailBot Agent",
    description="AI processing backend for OpenMailBot",
    version="1.0.0"
)



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
    user_preferences: Optional[Dict[str, Any]] = None


class LogEmailRequest(BaseModel):
    user_id: str
    thread_id: str
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


# Health check
@app.get("/health")
async def health_check():
    """Basic health check - returns immediately"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "openmailbot-agent"
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
@app.post("/api/embed")
async def generate_embeddings(request: Dict[str, Any]):
    """Generate embeddings for email content"""
    try:
        text = request.get("text")
        user_id = request.get("userId")
        tenant_id = request.get("tenantId")
        
        if not text or not user_id or not tenant_id:
            raise HTTPException(status_code=400, detail="Missing required fields")
        
        embedding = await embedding_service.generate_embedding(text)
        
        # Store in vector DB
        await embedding_service.store_embedding(
            embedding=embedding,
            metadata={
                "userId": user_id,
                "tenantId": tenant_id,
                "text": text[:500]  # Store preview
            },
            namespace=f"{tenant_id}_{user_id}"
        )
        
        return {"embedding": embedding, "dimension": len(embedding)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Summarize Thread
@app.post("/api/summarize")
async def summarize_thread(request: SummarizeRequest):
    """Summarize an email thread"""
    try:
        # Prepare thread content
        thread_text = "\n\n---\n\n".join([
            f"From: {email.from_address}\nTo: {', '.join(email.to)}\n"
            f"Subject: {email.subject}\nDate: {email.timestamp}\n\n{email.content}"
            for email in request.emails
        ])
        
        # Generate summary using LLM
        summary = await llm_service.summarize(
            content=thread_text,
            user_id=request.userId,
            tenant_id=request.tenantId
        )
        
        return {"summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Generate Reply
@app.post("/api/generate-reply")
async def generate_reply(request: GenerateReplyRequest):
    """Generate a context-aware reply"""
    try:
        # Prepare context
        thread_context = "\n\n---\n\n".join([
            f"From: {email.from_address}\nTo: {', '.join(email.to)}\n"
            f"Subject: {email.subject}\n\n{email.content}"
            for email in request.threadContext
        ])
        
        # Generate reply
        reply = await llm_service.generate_reply(
            email_content=request.email.content,
            from_address=request.email.from_address,
            thread_context=thread_context,
            tone=request.tone,
            additional_context=request.additionalContext,
            user_id=request.userId,
            tenant_id=request.tenantId
        )
        
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# RAG Query
@app.post("/api/rag")
async def rag_query(request: RAGQueryRequest):
    """Handle RAG query over email history"""
    try:
        result = await rag_service.query(
            query=request.query,
            user_id=request.userId,
            tenant_id=request.tenantId,
            email_context=request.emailContext.dict() if request.emailContext else None
        )
        
        return {
            "answer": result["answer"],
            "sources": result.get("sources", [])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


# Analytics endpoint for sentiment analysis
@app.post("/api/analyze-sentiment")
async def analyze_sentiment(request: Dict[str, Any]):
    """Analyze sentiment of email content"""
    try:
        text = request.get("text")
        
        if not text:
            raise HTTPException(status_code=400, detail="Text is required")
        
        sentiment = await llm_service.analyze_sentiment(text)
        
        return {"sentiment": sentiment}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


@app.post("/api/settings")
async def sync_settings(request: SyncSettingsRequest):
    """
    Sync user settings from Gmail Add-on to backend.
    
    This endpoint receives settings configured in the Gmail Add-on
    and saves them to encrypted SQLite database.
    
    Request:
    {
        "user_id": "user@example.com",
        "settings": {
            "mode": "custom",
            "llm_provider": "openai",
            "llm_api_key": "sk-...",
            "embedding_provider": "openai",
            "user_tone": "professional"
        }
    }
    
    Returns:
    {
        "success": true,
        "message": "Settings synced successfully",
        "user_id": "user@example.com",
        "settings_saved": 15,
        "encrypted": true
    }
    """
    print("🔧 /api/settings endpoint called")
    print(f"   User: {request.user_id}")
    print(f"   Settings received: {list(request.settings.keys())}")
    
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
        
        print(f"✅ Settings saved to encrypted database")
        print(f"   User: {request.user_id}")
        print(f"   Settings count: {len(request.settings)}")
        print(f"   Storage: data/{request.user_id}/sql_data/chat_thread_processing.db")
        
        return {
            "success": True,
            "message": "Settings synced successfully",
            "user_id": request.user_id,
            "settings_saved": len(request.settings),
            "encrypted": True,
            "storage": f"data/{request.user_id}/sql_data/chat_thread_processing.db"
        }
    except Exception as e:
        print(f"❌ Error syncing settings: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync settings: {str(e)}"
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
        import traceback
        traceback.print_exc()
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
        import traceback
        traceback.print_exc()
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
        import traceback
        traceback.print_exc()
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
        
        # ─ Cleanup stored email data and attachments after pipeline completes ─
        logger.info(f"   [job {job_id}] Simple draft pipeline complete, starting cleanup...")
        clean_thread_data(request.user_id, norm_thread_id)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        _set_job(job_id, "error", error=str(e))


@app.post("/api/draft")
async def simple_draft(request: SimpleDraftRequest, background_tasks: BackgroundTasks):
    """
    Generate email draft from thread emails (no attachments).

    Returns a job_id immediately; processing runs in background.
    Poll /api/job-status/{job_id} until status is "done" or "error".

    Request:
    {
        "user_id": "user@example.com",
        "thread_id": "thread_123abc",
        "user_preferences": {
            "name": "Alice",
            "position": "Manager",
            "tone": "professional",
            "custom_instructions": ""
        }
    }
    """
    job_id = str(uuid.uuid4())
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
    
    print(f"📋 /api/summarize-thread endpoint called")
    print(f"   Job ID: {job_id}")
    print(f"   User: {request.user_id}")
    print(f"   Thread: {request.thread_id}")
    print(f"   User Name: {request.user_name}")
    
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
        print(f"❌ Summarization pipeline error: {str(e)}")
        import traceback
        traceback.print_exc()
        _set_job(job_id, "error", error=str(e))


@app.get("/api/job-status/{job_id}")
async def get_job_status(job_id: str):
    """Poll the status of a background job submitted by chat-with-thread or draft-with-attachments."""
    with _job_store_lock:
        job = _job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job}


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
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
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
        
        # Save preprocessed messages with "preprocessed_" prefix
        last_msg_id = request.messages[-1].message_id if request.messages else thread_id
        preprocessed_filename = f"{last_msg_id}.json"
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
        # Get OpenAI API key from environment or config
        openai_api_key = os.getenv("OPENAI_API_KEY") or CONFIG.get("OPENAI_KEY")
        
        if not openai_api_key:
            logger.warning("   No OpenAI API key found, using rule-based only")
        
        label_pipeline = EmailLabelPipeline(openai_api_key=openai_api_key)
        
        # Label the thread (focuses on last message)
        # Label and store thread in graph database — offload to thread pool to avoid blocking the event loop
        loop = asyncio.get_running_loop()
        label_and_store_result = await loop.run_in_executor(
            None,
            partial(
                label_pipeline.label_and_store_thread,
                thread_id=thread_id,
                messages=processed_messages,
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
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ===========================================================================
# Gmail REST API helper — applies a label directly on the user's mailbox
# ===========================================================================

# Max time the async labeler may spend before giving up (60 min for production, change to 5 * 60 for testing)
_LABEL_PUSH_TIMEOUT_SECONDS = 60 * 60

# Color palette matching the Apps Script CONFIG.LABEL_COLORS
_GMAIL_LABEL_COLORS: Dict[str, Dict[str, str]] = {
    "Response":       {"backgroundColor": "#4a86e8", "textColor": "#ffffff"},
    "Fyi":            {"backgroundColor": "#16a766", "textColor": "#ffffff"},
    "Notification":   {"backgroundColor": "#b7b7b7", "textColor": "#000000"},
    "Meeting":        {"backgroundColor": "#9900ff", "textColor": "#ffffff"},
    "Awaiting reply": {"backgroundColor": "#ffff00", "textColor": "#000000"},
    "Escalation":     {"backgroundColor": "#cc0000", "textColor": "#ffffff"},
    "Hotels":         {"backgroundColor": "#ff9900", "textColor": "#000000"},
    "Airline":        {"backgroundColor": "#7f6000", "textColor": "#ffffff"},
    "Airlines":       {"backgroundColor": "#7f6000", "textColor": "#ffffff"},
    "Travel":         {"backgroundColor": "#274e13", "textColor": "#ffffff"},
    "Restaurant":     {"backgroundColor": "#ff9900", "textColor": "#000000"},
    "Booking":        {"backgroundColor": "#4a86e8", "textColor": "#ffffff"},
    "Bank":           {"backgroundColor": "#16a766", "textColor": "#ffffff"},
    "Recruitment":    {"backgroundColor": "#274e13", "textColor": "#ffffff"},
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
        with open(os.path.join(thread_folder, f"{last_msg_id}.json"), "w", encoding="utf-8") as f:
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

        # ── Vector store (non-fatal) ──────────────────────────────────────
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    CheckAndStoreEmailPipeline(user_id=request.user_id).run(request.user_id, thread_id, processed_messages),
                    CheckAndStoreAttachmentsPipeline(user_id=request.user_id).run(request.user_id, thread_id),
                    return_exceptions=True,
                ),
                timeout=_LABEL_PUSH_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning(f"   [job {job_id}] Vector-store timed out — continuing to label")
        except Exception as ve:
            logger.warning(f"   [job {job_id}] Vector-store error (non-fatal): {ve}")

        # ── Label pipeline (CPU-bound, run in thread pool) ────────────────
        openai_api_key = os.getenv("OPENAI_API_KEY") or CONFIG.get("OPENAI_KEY")
        label_pipeline = EmailLabelPipeline(openai_api_key=openai_api_key)
        loop = asyncio.get_running_loop()
        label_and_store_result = await loop.run_in_executor(
            None,
            partial(
                label_pipeline.label_and_store_thread,
                thread_id=thread_id,
                messages=processed_messages,
            ),
        )
        label_name: str = label_and_store_result["label_result"]["label"]
        # graph_status = label_and_store_result.get("graph_store_result") or {}  # DISABLED: graph storage
        logger.info(f"   [job {job_id}] Label determined: '{label_name}'")

        # ── Push label to Gmail via REST API ──────────────────────────────
        gmail_result: Dict[str, Any] = {}
        if request.access_token:
            logger.info(f"📬 [job {job_id}] Starting Gmail API label push (background task)")
            logger.info(f"   Thread ID: {thread_id}")
            logger.info(f"   Label: '{label_name}'")
            logger.info(f"   Access token: {request.access_token[:20]}..." if len(request.access_token) > 20 else request.access_token)
            try:
                logger.info(f"📤 [job {job_id}] Calling _apply_gmail_label_sync in thread pool executor...")
                gmail_result = await loop.run_in_executor(
                    None,
                    partial(
                        _apply_gmail_label_sync,
                        thread_id=thread_id,
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
            logger.warning(f"⚠️ [job {job_id}] No access_token provided — skipping Gmail API push")

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
            },
        )
        
        # ─ Cleanup stored email data and attachments after pipeline completes ─
        logger.info(f"   [job {job_id}] Labeling complete, starting cleanup...")
        clean_thread_data(request.user_id, thread_id)
        
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
        traceback.print_exc()
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

class SettingsRequest(BaseModel):
    """Request model for settings operations"""
    user_id: str = Field(..., description="User email or ID")
    settings: Optional[Dict[str, Any]] = Field(None, description="Settings object to save")

class SettingsResponse(BaseModel):
    """Response model for settings operations"""
    success: bool
    user_id: str
    settings: Optional[Dict[str, Any]] = None
    source: Optional[str] = None  # 'database', 'defaults', 'encrypted'
    message: Optional[str] = None

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

@app.post("/api/settings")
async def save_settings(request: SettingsRequest):
    """
    Save or update user settings
    
    **Request Body:**
    ```json
    {
        "user_id": "ankitgoel2004@gmail.com",
        "settings": {
            "mode": "inbuilt",
            "llm_provider": "openai",
            "llm_api_key": "sk-...",
            "llm_model": "gpt-4o-mini",
            "user_name": "Ankit Goel",
            "user_tone": "professional",
            ...
        }
    }
    ```
    
    **Returns:**
    - Updated settings object
    - Confirmation message
    
    **Example Response:**
    ```json
    {
        "success": true,
        "user_id": "ankitgoel2004@gmail.com",
        "settings": { ... },
        "source": "encrypted",
        "message": "Settings saved successfully"
    }
    ```
    """
    if not request.user_id:
        raise HTTPException(
            status_code=400, 
            detail="Missing required field: user_id"
        )
    
    if not request.settings:
        raise HTTPException(
            status_code=400, 
            detail="Missing required field: settings"
        )
    
    try:
        manager = SettingsManager(user_id=request.user_id)
        saved_settings = manager.save_settings(request.settings)
        
        return {
            "success": True,
            "user_id": request.user_id,
            "settings": saved_settings,
            "source": "encrypted",
            "message": "Settings saved successfully"
        }
    except Exception as e:
        print(f"[Settings] Error saving settings for {request.user_id}: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error saving settings: {str(e)}"
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


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development"
    )

