"""
Inbuilt Service Module
Provides zero-config defaults for tenants using the central server infrastructure.
Wraps utils.py functions for LLM, embeddings, and vector storage.

The "inbuilt" mode is for users who don't want to configure their own API keys
and prefer to use the tenant-hosted central services.
"""
from typing import List, Dict, Any, Optional
import asyncio
import logging
import os

logger = logging.getLogger(__name__)


class InbuiltLLMService:
    """
    LLM service using inbuilt Flask/Ollama server.
    Uses call_chat_api from utils.py for zero-config LLM access.
    """
    
    def __init__(self):
        """Initialize inbuilt LLM service"""
        # Import utils lazily to avoid circular imports
        self._utils_available = False
        try:
            from utils import call_chat_api, ollama_generate_chat
            self._call_chat_api = call_chat_api
            self._ollama_generate_chat = ollama_generate_chat
            self._utils_available = True
        except ImportError:
            logger.warning("utils.py not available. Inbuilt LLM service disabled.")
    
    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate response using inbuilt LLM service.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Optional model name (passed to Ollama)
            temperature: Ignored for inbuilt
            max_tokens: Ignored for inbuilt
        
        Returns:
            Generated text response
        """
        if not self._utils_available:
            raise RuntimeError("Inbuilt LLM service not available. utils.py not found.")
        
        # Convert messages to prompt format
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        
        prompt = "\n\n".join(prompt_parts)
        prompt += "\n\nAssistant:"
        
        # Call inbuilt API
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._call_chat_api, prompt)
        
        if isinstance(result, dict) and "error" in result:
            raise RuntimeError(f"Inbuilt LLM error: {result['error']}")
        
        return result
    
    async def generate_with_ollama(
        self,
        prompt: str,
        model: str = "llama3.2"
    ) -> str:
        """
        Generate using direct Ollama call (for cases needing specific model).
        """
        if not self._utils_available:
            raise RuntimeError("Inbuilt LLM service not available.")
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, 
            lambda: self._ollama_generate_chat(prompt, model)
        )
        
        if result.startswith("Error:"):
            raise RuntimeError(f"Ollama error: {result}")
        
        return result


class InbuiltEmbeddingService:
    """
    Embedding service using inbuilt Flask embedding server.
    Uses call_embed_api from utils.py for zero-config embedding access.
    """
    
    def __init__(self):
        """Initialize inbuilt embedding service"""
        self._utils_available = False
        try:
            from utils import call_embed_api
            self._call_embed_api = call_embed_api
            self._utils_available = True
        except ImportError:
            logger.warning("utils.py not available. Inbuilt embedding service disabled.")
    
    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding using inbuilt service.
        
        Args:
            text: Text to embed
        
        Returns:
            List of floats representing the embedding
        """
        if not self._utils_available:
            raise RuntimeError("Inbuilt embedding service not available. utils.py not found.")
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._call_embed_api, text)
        
        if isinstance(result, dict) and "error" in result:
            raise RuntimeError(f"Inbuilt embedding error: {result['error']}")
        
        return result
    
    async def generate_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        embeddings = []
        for text in texts:
            embedding = await self.generate_embedding(text)
            embeddings.append(embedding)
        return embeddings


class InbuiltVectorClient:
    """
    Vector client for inbuilt mode.
    Uses ChromaDB with INBUILT_CHROMA_URL environment variable.
    """
    
    def __init__(self):
        """Initialize inbuilt vector client (Chroma HTTP)"""
        from vector.chroma_client import ChromaDBClient
        
        # Use inbuilt mode which reads INBUILT_CHROMA_URL
        self.client = ChromaDBClient(inbuilt_mode=True)
    
    async def upsert(
        self,
        vector_id: Optional[str],
        embedding: List[float],
        metadata: Dict[str, Any],
        namespace: str
    ) -> str:
        return await self.client.upsert(vector_id, embedding, metadata, namespace)
    
    async def upsert_batch(
        self,
        vector_ids: Optional[List[str]],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        namespace: str
    ) -> List[str]:
        return await self.client.upsert_batch(vector_ids, embeddings, metadatas, namespace)
    
    async def query(
        self,
        embedding: List[float],
        namespace: str,
        limit: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        return await self.client.query(embedding, namespace, limit, filter)
    
    async def delete(self, vector_id: str, namespace: str) -> bool:
        return await self.client.delete(vector_id, namespace)
    
    async def get_by_id(self, vector_id: str, namespace: str) -> Optional[Dict[str, Any]]:
        return await self.client.get_by_id(vector_id, namespace)
    
    def health_check(self) -> Dict[str, Any]:
        return self.client.health_check()


def get_inbuilt_llm_service() -> InbuiltLLMService:
    """Factory function to get inbuilt LLM service"""
    return InbuiltLLMService()


def get_inbuilt_embedding_service() -> InbuiltEmbeddingService:
    """Factory function to get inbuilt embedding service"""
    return InbuiltEmbeddingService()


def get_inbuilt_vector_client() -> InbuiltVectorClient:
    """Factory function to get inbuilt vector client"""
    return InbuiltVectorClient()
