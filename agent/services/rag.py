"""
RAG (Retrieval-Augmented Generation) Service
Combines vector search with LLM generation
"""
from typing import Optional, Dict, Any, List
import logging

from agent.services.embeddings import EmbeddingService
from agent.services.llm import LLMService
from agent.services.settings_manager import SettingsManager

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(self, user_id: Optional[str] = None, effective_settings: Optional[Dict] = None):
        """
        Initialize RAG service.
        
        Args:
            user_id: User identifier for settings retrieval
            effective_settings: Pre-loaded user settings (optional)
        """
        self.user_id = user_id
        
        # Load or use provided settings
        if effective_settings:
            self.effective_settings = effective_settings
        elif user_id:
            settings_manager = SettingsManager(user_id)
            retrieved = settings_manager.get_settings(setting_type="general")
            self.effective_settings = retrieved if retrieved else {}
            logger.info(f"Loaded RAG settings for user {user_id}")
        else:
            logger.warning("RAGService initialized without user_id or settings - using defaults")
            self.effective_settings = {}
        
        # Initialize services with user settings
        try:
            self.embedding_service = EmbeddingService(
                effective_settings={
                    **(self.effective_settings or {}),
                    "user_id": user_id or "anonymous"
                }
            )
            logger.info("✅ EmbeddingService initialized in RAGService")
        except Exception as e:
            logger.error(f"Failed to initialize EmbeddingService in RAGService: {e}")
            raise
        
        try:
            self.llm_service = LLMService(effective_settings=self.effective_settings)
            logger.info("✅ LLMService initialized in RAGService")
        except Exception as e:
            logger.error(f"Failed to initialize LLMService in RAGService: {e}")
            raise
    
    async def query(
        self,
        query: str,
        user_id: str,
        tenant_id: str,
        email_context: Optional[Dict[str, Any]] = None,
        limit: int = 5,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a RAG query:
        1. Generate embedding for query
        2. Retrieve similar emails from vector DB
        3. Generate answer using LLM with retrieved context
        """
        
        namespace = f"{tenant_id}_{user_id}"
        
        # Retrieve relevant emails
        similar_results = await self.embedding_service.find_similar_by_text(
            text=query,
            namespace=namespace,
            limit=limit
        )
        
        # Build context from retrieved emails
        context_parts = []
        sources = []
        
        for result in similar_results:
            metadata = result.get("metadata", {})
            
            email_text = f"""
From: {metadata.get('from', 'Unknown')}
To: {metadata.get('to', 'Unknown')}
Subject: {metadata.get('subject', 'No subject')}
Date: {metadata.get('timestamp', 'Unknown')}

{metadata.get('content', metadata.get('text', ''))}
"""
            context_parts.append(email_text.strip())
            
            sources.append({
                "subject": metadata.get('subject'),
                "from": metadata.get('from'),
                "timestamp": metadata.get('timestamp'),
                "score": result.get('score')
            })
        
        # Add email context if provided
        if email_context:
            current_email = f"""
Current email context:
From: {email_context.get('from')}
To: {', '.join(email_context.get('to', []))}
Subject: {email_context.get('subject')}

{email_context.get('content')}
"""
            context_parts.insert(0, current_email)
        
        # Combine all context
        full_context = "\n\n---\n\n".join(context_parts)
        
        # Generate answer using LLM
        messages = [
            {
                "role": "system",
                "content": """You are an AI email assistant with access to the user's email history. 
Answer questions based on the provided email context. Be concise and cite specific emails when relevant.
If the context doesn't contain enough information to answer the question, say so."""
            },
            {
                "role": "user",
                "content": f"""Based on these emails from my inbox:

{full_context}

Question: {query}

Please provide a helpful answer based on the email context above."""
            }
        ]
        
        answer = await self.llm_service.generate(
            messages=messages,
            provider=provider
        )
        
        return {
            "answer": answer,
            "sources": sources,
            "context_count": len(similar_results)
        }
    
    async def search_emails(
        self,
        query: str,
        user_id: str,
        tenant_id: str,
        limit: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search emails using semantic similarity
        Returns matching emails without LLM generation
        """
        
        namespace = f"{tenant_id}_{user_id}"
        
        results = await self.embedding_service.find_similar_by_text(
            text=query,
            namespace=namespace,
            limit=limit,
            filter=filter
        )
        
        return [
            {
                "id": result.get("id"),
                "score": result.get("score"),
                "metadata": result.get("metadata", {})
            }
            for result in results
        ]
    
    async def get_thread_summary(
        self,
        thread_emails: List[Dict[str, Any]],
        provider: Optional[str] = None
    ) -> str:
        """Generate a summary for a thread of emails"""
        
        thread_text = "\n\n---\n\n".join([
            f"From: {email.get('from', 'Unknown')}\n"
            f"To: {', '.join(email.get('to', []))}\n"
            f"Subject: {email.get('subject', 'No subject')}\n"
            f"Date: {email.get('timestamp', 'Unknown')}\n\n"
            f"{email.get('content', '')}"
            for email in thread_emails
        ])
        
        return await self.llm_service.summarize(
            content=thread_text,
            user_id="",  # Not needed for this call
            tenant_id="",
            provider=provider
        )
