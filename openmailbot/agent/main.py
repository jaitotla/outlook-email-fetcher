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
#from database.mongodb import MongoDBClient

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


class LogEmailRequest(BaseModel):
    user_id: str
    thread_id: str
    messages: List[EmailMessage]


class AttachmentData(BaseModel):
    filename: str
    content: str  # base64 encoded
    mime_type: str = "application/octet-stream"


class StoreAttachmentsRequest(BaseModel):
    user_id: str
    thread_id: str
    message_id: str
    attachments: List[AttachmentData]


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
    try:
        chat_pipeline = ChatWithThreadPipeline(user_id=request.user_id)
        result = chat_pipeline.process_and_chat(
            request.user_id,
            request.thread_id,
            request.question,
        )
        _set_job(job_id, "done", result=result)
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
    import logger
    try:
        chat_pipeline = ChatWithThreadPipeline(user_id=request.user_id)
        
        # Step 1: Clear old embeddings
        logger.info(f"🧹 Clearing embeddings for thread {request.thread_id}")
        clear_info = chat_pipeline.clear_thread_embeddings(request.user_id, request.thread_id)
        
        # Step 2: Re-process emails and attachments
        logger.info(f"🔄 Re-processing thread with new metadata structure")
        result = chat_pipeline.process_and_chat(
            request.user_id,
            request.thread_id,
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
    try:
        draft_pipeline = DraftPipeline(user_id=request.user_id)
        result = asyncio.run(draft_pipeline.process_email_request(
            request.user_id,
            request.thread_id,
            request.user_preferences,
        ))
        _set_job(job_id, "done", result=result)
    except Exception as e:
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
        
        # Get user's data directories
        user_dirs = get_user_data_dir(request.user_id)
        log_dir = user_dirs["log_emails"]
        
        # Create thread folder: data/{user_id}/log_emails/thread_xxx/
        thread_folder = os.path.join(log_dir, request.thread_id)
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
        filename = f"{request.thread_id}.json"
        filepath = os.path.join(thread_folder, filename)
        
        # Prepare output data with cleaned messages
        output_data = {
            'thread_id': request.thread_id,
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
            "thread_id": request.thread_id,
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
    
    # Initialize lock book for this user
    lockbook = get_user_lockbook(request.user_id)
    global_lockbook = get_global_lockbook()
    
    try:
        if not request.messages:
            raise HTTPException(status_code=400, detail="No messages provided")
        
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
        thread_folder = os.path.join(log_dir, request.thread_id)
        os.makedirs(thread_folder, exist_ok=True)
        
        # Save preprocessed messages with "preprocessed_" prefix
        preprocessed_filename = f"preprocessed_{request.thread_id}.json"
        preprocessed_filepath = os.path.join(thread_folder, preprocessed_filename)
        
        # Prepare output data with preprocessed messages
        preprocessed_output_data = {
            'thread_id': request.thread_id,
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
                thread_id=request.thread_id,
                messages=processed_messages,
            )
        )
        
        label = label_and_store_result["label_result"]
        graph_status = label_and_store_result["graph_store_result"]
        
        logger.info(f"✅ Email labeled and stored: {label}")
        logger.info(f"   Graph storage status: {graph_status.get('status')}")
        
        # Determine if graph storage was successful
        num_graph_stored = len(processed_messages) if graph_status.get("status") == "SUCCESS" else 0
        
        # Log to lock book
        lockbook.log_request(
            thread_id=request.thread_id,
            label=label["label"],
            num_labeled=len(processed_messages),
            num_graph_stored=num_graph_stored,
            status="SUCCESS"
        )
        
        # Also log to global lock book
        global_lockbook.log_request(
            thread_id=request.thread_id,
            label=label["label"],
            num_labeled=len(processed_messages),
            num_graph_stored=num_graph_stored,
            status="SUCCESS"
        )
        
        logger.info(f"📝 Lock book updated")
        logger.info(f"   User metrics saved to: data/lockbook/label_email_metrics_{request.user_id}.json")
        logger.info(f"   Global metrics saved to: data/lockbook/label_email_metrics_global.json")
        
        return {
            "success": True,
            "label": label["label"],
            "category": label["category"],
            "topic": label["topic"],
            "subtopic": label["subtopic"],
            "user_id": request.user_id,
            "thread_id": request.thread_id,
            "messages_processed": len(processed_messages),
            "graph_store_status": graph_status.get("status"),
            "graph_store_steps": len(graph_status.get("steps", []))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error labeling email: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Log failure to lock book
        try:
            lockbook.log_request(
                thread_id=request.thread_id,
                label="error",
                num_labeled=0,
                num_graph_stored=0,
                status="FAILED"
            )
            global_lockbook.log_request(
                thread_id=request.thread_id,
                label="error",
                num_labeled=0,
                num_graph_stored=0,
                status="FAILED"
            )
        except:
            pass  # Fallback if lock book logging fails
        
        raise HTTPException(status_code=500, detail=str(e))


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
        
        # Get user's data directories
        user_dirs = get_user_data_dir(request.user_id)
        attachment_dir = user_dirs["attachments"]
        
        # Create directory for this thread: data/{user_id}/store_attachments/thread_xxx/
        thread_dir = os.path.join(attachment_dir, request.thread_id)
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
            "thread_id": request.thread_id,
            "message_id": request.message_id,
            "timestamp": datetime.utcnow().isoformat(),
            "attachments": saved_files
        }
        
        metadata_file = os.path.join(thread_dir, f"{request.message_id}_metadata.json")
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        return {
            "success": True,
            "message": f"Stored {len(saved_files)} attachments",
            "user_id": request.user_id,
            "thread_id": request.thread_id,
            "saved_files": saved_files,
            "metadata_file": metadata_file
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

