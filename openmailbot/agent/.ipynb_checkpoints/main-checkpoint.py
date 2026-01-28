"""
OpenMailBot Agent - FastAPI Application
Handles email ingestion, embeddings, RAG, and LLM interface
"""
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uvicorn
from datetime import datetime

from openmailbot.agent.config import settings
from services.ingestion import EmailIngestionService
from services.embeddings import EmbeddingService
from services.rag import RAGService
from services.llm import LLMService
from services.slack_ingestion import SlackIngestionService
from services.file_processor import FileProcessor
from services.chat_pipeline import ChatWithThreadPipeline
from services.draft_pipeline import DraftWithAttachmentsPipeline
from database.mongodb import MongoDBClient

app = FastAPI(
    title="OpenMailBot Agent",
    description="AI processing backend for OpenMailBot",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.BACKEND_API_URL, "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
db_client = MongoDBClient(settings.MONGODB_URI)
embedding_service = EmbeddingService()
rag_service = RAGService()
llm_service = LLMService()
ingestion_service = EmailIngestionService()
file_processor = FileProcessor()
chat_pipeline = ChatWithThreadPipeline()
draft_pipeline = DraftWithAttachmentsPipeline()
slack_service = SlackIngestionService(
    backend_url=settings.BACKEND_API_URL,
    llm_service=llm_service,
    file_processor=file_processor
)


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


# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "openmailbot-agent"
    }


# Email Ingestion
@app.post("/api/ingest")
async def ingest_emails(request: IngestEmailsRequest):
    """Ingest emails from Gmail or Outlook"""
    try:
        result = await ingestion_service.ingest_emails(
            user_id=request.userId,
            tenant_id=request.tenantId,
            provider=request.provider,
            access_token=request.accessToken,
            sync_from=request.syncFrom
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


# Related Threads
@app.post("/api/related-threads")
async def get_related_threads(request: RelatedThreadsRequest):
    """Find related email threads using vector similarity"""
    try:
        # Get the thread content
        thread_emails = await db_client.get_emails_by_thread(
            thread_id=request.threadId,
            user_id=request.userId,
            tenant_id=request.tenantId
        )
        
        if not thread_emails:
            return {"relatedThreadIds": []}
        
        # Generate embedding for the thread
        thread_text = " ".join([email.get("content", "") for email in thread_emails])
        thread_embedding = await embedding_service.generate_embedding(thread_text)
        
        # Find similar threads
        similar_results = await embedding_service.find_similar(
            embedding=thread_embedding,
            namespace=f"{request.tenantId}_{request.userId}",
            limit=request.limit + 1  # +1 to exclude the query thread itself
        )
        
        # Extract thread IDs (excluding the query thread)
        related_thread_ids = [
            result["metadata"].get("threadId")
            for result in similar_results
            if result["metadata"].get("threadId") != request.threadId
        ][:request.limit]
        
        return {"relatedThreadIds": related_thread_ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


@app.post("/api/slack/ingest")
async def ingest_slack(request: SlackIngestRequest):
    """Ingest Slack workspace messages"""
    try:
        result = await slack_service.ingest_workspace(
            user_id=request.userId,
            workspace_id=request.workspaceId,
            access_token=request.accessToken,
            bot_token=request.botToken,
            sync_days=request.syncDays,
            selected_channels=request.selectedChannels,
            selected_dms=request.selectedDMs,
            include_public=request.includePublic,
            include_private=request.includePrivate,
            include_dms=request.includeDMs,
            file_config=request.fileConfig
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ChatWithThreadRequest(BaseModel):
    user_id: str
    thread_id: str
    question: str


class DraftWithAttachmentsRequest(BaseModel):
    user_id: str
    thread_id: str
    user_preferences: Optional[Dict[str, Any]] = None


@app.post("/chat-with-thread")
async def chat_with_thread(request: ChatWithThreadRequest):
    """
    Chat with an email thread using RAG pipeline
    
    This endpoint processes unprocessed emails and attachments,
    then uses OpenAI for tool selection and Ollama for final answer generation.
    """
    try:
        result = chat_pipeline.process_and_chat(
            user_id=request.user_id,
            thread_id=request.thread_id,
            user_question=request.question
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/draft-with-attachments")
async def draft_with_attachments(request: DraftWithAttachmentsRequest):
    """
    Generate email draft with attachment context using hybrid approach
    
    This endpoint processes attachments and generates a professional email draft
    using OpenAI for tool selection and Ollama for final draft generation.
    
    Request:
    {
        "user_id": "user@example.com",
        "thread_id": "gmail_thread_id",
        "user_preferences": {
            "name": "John Doe",
            "position": "Manager",
            "tone": "professional",
            "custom_instructions": "Always include bullet points"
        }
    }
    
    Returns:
    {
        "success": true,
        "response": "Generated draft email...",
        "processing_info": {
            "attachments_found": 2,
            "attachments_processed": 1,
            "attachments_skipped": 1,
            "errors": []
        }
    }
    """
    try:
        result = draft_pipeline.process_email_request(
            user_id=request.user_id,
            thread_id=request.thread_id,
            user_preferences=request.user_preferences
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SlackChannelsRequest(BaseModel):
    accessToken: str


@app.post("/api/slack/channels")
async def get_slack_channels(request: SlackChannelsRequest):
    """Get available Slack channels"""
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


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development"
    )
