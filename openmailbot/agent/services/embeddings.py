"""
Embedding Service
Generates and manages embeddings for email content
Supports multiple embedding providers: OpenAI, Nomic, Gemini, Sentence-Transformers, Inbuilt
"""
from typing import List, Dict, Any, Optional
import numpy as np
import requests
import os
import logging
import json
#from config import settings
from vector import get_vector_client
from services.llm import ProviderError

logger = logging.getLogger(__name__)

# Load configuration
CONFIG_PATH = "/home/ubuntu/openmailbot/openmailbot/agent/config.json"
with open(CONFIG_PATH, 'r') as f:
    CONFIG = json.load(f)

class EmbeddingService:
    """
    Embedding service that supports multiple providers:
    - openai: OpenAI text-embedding-ada-002 or text-embedding-3-*
    - nomic: Nomic nomic-embed-text-v1.5
    - gemini: Google Gemini embeddings
    - sentence-transformers: Local sentence-transformers models
    - inbuilt: Uses utils.py call_embed_api for central server
    """
    
    def __init__(self, effective_settings: Optional[Dict[str, Any]] = None):
        """
        Initialize embedding service.
        
        Args:
            effective_settings: Dict with:
                - embedding_provider: 'openai', 'nomic', 'gemini', 'sentence-transformers', 'inbuilt'
                - embedding_model: Model name (provider-specific)
                - embedding_api_key: API key for the provider
                - vector_provider: 'pinecone', 'chroma', 'weaviate', 'inbuilt'
                - Additional vector DB settings (chroma_url, weaviate_url, etc.)
                If not provided, uses CONFIG as fallback
        """
        # Use provided settings or fall back to global CONFIG
        self.effective_settings = effective_settings if effective_settings else (CONFIG or {})
        
        # Embedding provider config
        self.embedding_provider = self.effective_settings.get("embedding_provider") 
        self.embedding_model = self.effective_settings.get("embedding_model")
        
        # Legacy fallback for embedding API URL
        #self.embedding_api_url = settings.EMBEDDING_API_URL if hasattr(settings, 'EMBEDDING_API_URL') else None
        
        # Vector DB config
        vector_db_provider = self.effective_settings.get("vector_provider") or "inbuilt"
        
        # Initialize vector client via factory
        try:
            self.vector_client = get_vector_client(vector_db_provider, self.effective_settings)
        except Exception as e:
            logger.error(f"Failed to initialize vector client: {e}")
            raise ProviderError(vector_db_provider, f"Vector DB initialization failed: {e}")
        
        # Initialize embedding provider-specific clients
        self._init_embedding_clients()
    
    def _init_embedding_clients(self):
        """Initialize clients for embedding providers"""
        
        # OpenAI embeddings
        if self.embedding_provider == "openai":
            import openai
            openai_key = self.effective_settings.get("embedding_api_key") or os.environ.get("OPENAI_API_KEY")
            if openai_key:
                openai.api_key = openai_key
            self.embedding_model = self.embedding_model or "text-embedding-ada-002"
        
        # Nomic embeddings
        elif self.embedding_provider == "nomic":
            nomic_key = self.effective_settings.get("embedding_api_key") or os.environ.get("NOMIC_API_KEY")
            if nomic_key:
                try:
                    import nomic
                    nomic.login(nomic_key)
                    self._nomic_available = True
                except ImportError:
                    logger.warning("nomic package not installed")
                    self._nomic_available = False
            else:
                self._nomic_available = False
            self.embedding_model = self.embedding_model or "nomic-embed-text-v1.5"
        
        # Gemini embeddings
        elif self.embedding_provider == "gemini":
            gemini_key = self.effective_settings.get("embedding_api_key") or os.environ.get("GEMINI_API_KEY")
            if gemini_key:
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=gemini_key)
                    self._gemini_available = True
                except ImportError:
                    logger.warning("google-generativeai package not installed")
                    self._gemini_available = False
            else:
                self._gemini_available = False
            self.embedding_model = self.embedding_model or "models/embedding-001"
        
        # Sentence-transformers (local)
        elif self.embedding_provider == "sentence-transformers":
            try:
                from sentence_transformers import SentenceTransformer
                model_name = self.embedding_model or "all-MiniLM-L6-v2"
                self._st_model = SentenceTransformer(model_name)
                self._st_available = True
            except ImportError:
                logger.warning("sentence-transformers package not installed")
                self._st_available = False
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using configured provider"""
        
        provider = self.embedding_provider
        
        if provider == "openai":
            return await self._embed_openai(text)
        elif provider == "nomic":
            return await self._embed_nomic(text)
        elif provider == "gemini":
            return await self._embed_gemini(text)
        elif provider == "sentence-transformers":
            return await self._embed_sentence_transformers(text)
        elif provider == "inbuilt":
            return await self._embed_inbuilt(text)
        else:
            # Fallback to inbuilt
            return await self._embed_inbuilt(text)
    
    async def _embed_openai(self, text: str) -> List[float]:
        """Generate embedding using OpenAI"""
        try:
            import openai
            response = openai.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            raise ProviderError("openai", f"Embedding error: {str(e)}", e)
    
    async def _embed_nomic(self, text: str) -> List[float]:
        """Generate embedding using Nomic"""
        if not getattr(self, '_nomic_available', False):
            raise ProviderError("nomic", "Nomic not configured or package not installed")
        
        try:
            from nomic import embed
            result = embed.text(
                texts=[text],
                model=self.embedding_model,
                task_type="search_document"
            )
            return result['embeddings'][0]
        except Exception as e:
            raise ProviderError("nomic", f"Embedding error: {str(e)}", e)
    
    async def _embed_gemini(self, text: str) -> List[float]:
        """Generate embedding using Google Gemini"""
        if not getattr(self, '_gemini_available', False):
            raise ProviderError("gemini", "Gemini not configured or package not installed")
        
        try:
            import google.generativeai as genai
            result = genai.embed_content(
                model=self.embedding_model,
                content=text,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            raise ProviderError("gemini", f"Embedding error: {str(e)}", e)
    
    async def _embed_sentence_transformers(self, text: str) -> List[float]:
        """Generate embedding using local sentence-transformers"""
        if not getattr(self, '_st_available', False):
            raise ProviderError("sentence-transformers", "Sentence-transformers not installed")
        
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(None, self._st_model.encode, text)
            return embedding.tolist()
        except Exception as e:
            raise ProviderError("sentence-transformers", f"Embedding error: {str(e)}", e)
    
    async def _embed_inbuilt(self, text: str) -> List[float]:
        """Generate embedding using inbuilt service (utils.py)"""
        try:
            from utils import call_embed_api
            import asyncio
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, call_embed_api, text)
            
            if isinstance(result, dict) and "error" in result:
                raise ProviderError("inbuilt", result["error"])
            
            return result
        except ImportError:
            # Fallback to embedding API URL if utils.py not available
            if self.embedding_api_url:
                try:
                    response = requests.post(
                        self.embedding_api_url,
                        json={"text": text}
                    )
                    response.raise_for_status()
                    data = response.json()
                    if "embedding" in data:
                        return data["embedding"]
                    return data
                except Exception as e:
                    raise ProviderError("inbuilt", f"Embedding API error: {str(e)}", e)
            raise ProviderError("inbuilt", "Neither utils.py nor embedding API URL available")
        except Exception as e:
            if isinstance(e, ProviderError):
                raise
            raise ProviderError("inbuilt", f"Embedding error: {str(e)}", e)
    
    async def generate_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts using embedding API"""
        
        embeddings = []
        for text in texts:
            embedding = await self.generate_embedding(text)
            embeddings.append(embedding)
        return embeddings
    
    async def store_embedding(
        self,
        embedding: List[float],
        metadata: Dict[str, Any],
        namespace: str,
        vector_id: Optional[str] = None
    ) -> str:
        """Store embedding in vector database"""
        
        return await self.vector_client.upsert(
            vector_id=vector_id,
            embedding=embedding,
            metadata=metadata,
            namespace=namespace
        )
    
    async def store_batch_embeddings(
        self,
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        namespace: str,
        vector_ids: Optional[List[str]] = None
    ) -> List[str]:
        """Store multiple embeddings"""
        
        return await self.vector_client.upsert_batch(
            vector_ids=vector_ids,
            embeddings=embeddings,
            metadatas=metadatas,
            namespace=namespace
        )
    
    async def find_similar(
        self,
        embedding: List[float],
        namespace: str,
        limit: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Find similar embeddings"""
        
        return await self.vector_client.query(
            embedding=embedding,
            namespace=namespace,
            limit=limit,
            filter=filter
        )
    
    async def find_similar_by_text(
        self,
        text: str,
        namespace: str,
        limit: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Find similar embeddings by text query"""
        
        # Generate embedding for the query text
        query_embedding = await self.generate_embedding(text)
        
        # Search for similar vectors
        return await self.find_similar(
            embedding=query_embedding,
            namespace=namespace,
            limit=limit,
            filter=filter
        )
    
    async def delete_embeddings(
        self,
        vector_id: str,
        namespace: str
    ):
        """Delete an embedding from vector database"""
        
        await self.vector_client.delete(
            vector_id=vector_id,
            namespace=namespace
        )
    
    async def get_embedding_by_id(
        self,
        vector_id: str,
        namespace: str
    ) -> Optional[Dict[str, Any]]:
        """Get embedding by ID"""
        
        return await self.vector_client.get_by_id(
            vector_id=vector_id,
            namespace=namespace
        )
