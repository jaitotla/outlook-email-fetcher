"""
Pinecone Vector Database Client
"""
from typing import List, Dict, Any, Optional
import pinecone
from uuid import uuid4

from config import settings
from .base import BaseVectorStore


class PineconeClient(BaseVectorStore):
    def __init__(self):
        if not settings.PINECONE_API_KEY:
            raise ValueError("Pinecone API key not configured")
        
        # Initialize Pinecone
        pinecone.init(
            api_key=settings.PINECONE_API_KEY,
            environment=settings.PINECONE_ENVIRONMENT
        )
        
        self.index_name = settings.PINECONE_INDEX_NAME
        
        # Create index if it doesn't exist
        if self.index_name not in pinecone.list_indexes():
            pinecone.create_index(
                name=self.index_name,
                dimension=settings.EMBEDDING_DIMENSION,
                metric="cosine"
            )
        
        self.index = pinecone.Index(self.index_name)
    
    async def upsert(
        self,
        vector_id: Optional[str],
        embedding: List[float],
        metadata: Dict[str, Any],
        namespace: str
    ) -> str:
        """Insert or update a vector"""
        
        if not vector_id:
            vector_id = str(uuid4())
        
        self.index.upsert(
            vectors=[(vector_id, embedding, metadata)],
            namespace=namespace
        )
        
        return vector_id
    
    async def upsert_batch(
        self,
        vector_ids: Optional[List[str]],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        namespace: str
    ) -> List[str]:
        """Insert or update multiple vectors"""
        
        if not vector_ids:
            vector_ids = [str(uuid4()) for _ in embeddings]
        
        vectors = [
            (vid, emb, meta)
            for vid, emb, meta in zip(vector_ids, embeddings, metadatas)
        ]
        
        # Batch upsert (Pinecone recommends batches of 100)
        batch_size = 100
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            self.index.upsert(vectors=batch, namespace=namespace)
        
        return vector_ids
    
    async def query(
        self,
        embedding: List[float],
        namespace: str,
        limit: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Query similar vectors"""
        
        results = self.index.query(
            vector=embedding,
            top_k=limit,
            namespace=namespace,
            filter=filter,
            include_metadata=True
        )
        
        return [
            {
                "id": match.id,
                "score": match.score,
                "metadata": match.metadata
            }
            for match in results.matches
        ]
    
    async def delete(
        self,
        vector_id: str,
        namespace: str
    ) -> bool:
        """Delete a vector"""
        
        try:
            self.index.delete(ids=[vector_id], namespace=namespace)
            return True
        except Exception:
            return False
    
    async def get_by_id(
        self,
        vector_id: str,
        namespace: str
    ) -> Optional[Dict[str, Any]]:
        """Get a vector by ID"""
        
        try:
            results = self.index.fetch(ids=[vector_id], namespace=namespace)
            if vector_id in results.vectors:
                vector = results.vectors[vector_id]
                return {
                    "id": vector_id,
                    "metadata": vector.metadata
                }
            return None
        except Exception:
            return None
