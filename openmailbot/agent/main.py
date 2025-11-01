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

from config import settings
from services.ingestion import EmailIngestionService
from services.embeddings import EmbeddingService
from services.rag import RAGService
from services.llm import LLMService
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


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development"
    )
