"""
Embedding Service
Generates and manages embeddings for email content
"""
from typing import List, Dict, Any, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
import openai

from config import settings
from vector.pinecone_client import PineconeClient
from vector.faiss_client import FAISSClient


class EmbeddingService:
    def __init__(self):
        self.model_name = settings.EMBEDDING_MODEL
        self.vector_db_type = settings.VECTOR_DB_TYPE
        
        # Initialize local model if needed
        if self.model_name.startswith("sentence-transformers/") or \
           self.model_name.startswith("all-"):
            self.local_model = SentenceTransformer(self.model_name)
        else:
            self.local_model = None
        
        # Initialize vector DB client
        if self.vector_db_type == "pinecone":
            self.vector_client = PineconeClient()
        elif self.vector_db_type == "faiss":
            self.vector_client = FAISSClient()
        else:
            raise ValueError(f"Unsupported vector DB type: {self.vector_db_type}")
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        
        if self.local_model:
            # Use local sentence-transformers model
            embedding = self.local_model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        else:
            # Use OpenAI API
            if not settings.OPENAI_API_KEY:
                raise ValueError("OpenAI API key not configured")
            
            openai.api_key = settings.OPENAI_API_KEY
            
            response = openai.embeddings.create(
                model=self.model_name,
                input=text
            )
            
            return response.data[0].embedding
    
    async def generate_batch_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        
        if self.local_model:
            embeddings = self.local_model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
        else:
            # Use OpenAI API
            if not settings.OPENAI_API_KEY:
                raise ValueError("OpenAI API key not configured")
            
            openai.api_key = settings.OPENAI_API_KEY
            
            response = openai.embeddings.create(
                model=self.model_name,
                input=texts
            )
            
            return [item.embedding for item in response.data]
    
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
        vector_ids: List[str],
        namespace: str
    ):
        """Delete embeddings from vector database"""
        
        await self.vector_client.delete(
            vector_ids=vector_ids,
            namespace=namespace
        )
    
    async def delete_namespace(self, namespace: str):
        """Delete entire namespace"""
        
        await self.vector_client.delete_namespace(namespace)
