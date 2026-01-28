"""
Base Vector Store Interface
Defines the contract for all vector store implementations
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseVectorStore(ABC):
    """Abstract base class for vector store implementations"""
    
    @abstractmethod
    async def upsert(
        self,
        vector_id: Optional[str],
        embedding: List[float],
        metadata: Dict[str, Any],
        namespace: str
    ) -> str:
        """Insert or update a single vector"""
        pass
    
    @abstractmethod
    async def upsert_batch(
        self,
        vector_ids: Optional[List[str]],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        namespace: str
    ) -> List[str]:
        """Insert or update multiple vectors"""
        pass
    
    @abstractmethod
    async def query(
        self,
        embedding: List[float],
        namespace: str,
        limit: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Query similar vectors"""
        pass
    
    @abstractmethod
    async def delete(
        self,
        vector_id: str,
        namespace: str
    ) -> bool:
        """Delete a vector"""
        pass
    
    @abstractmethod
    async def get_by_id(
        self,
        vector_id: str,
        namespace: str
    ) -> Optional[Dict[str, Any]]:
        """Get a vector by ID"""
        pass
