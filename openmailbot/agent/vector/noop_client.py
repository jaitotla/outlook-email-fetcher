from typing import List, Dict, Any, Optional
from .base import BaseVectorStore


class NoOpVectorClient(BaseVectorStore):
    """A no-op vector store used when a real vector DB is not configured."""

    async def upsert(self, vector_id: Optional[str], embedding: List[float], metadata: Dict[str, Any], namespace: str) -> str:
        # Return provided id or a placeholder
        return vector_id or "noop-id"

    async def upsert_batch(self, vector_ids: Optional[List[str]], embeddings: List[List[float]], metadatas: List[Dict[str, Any]], namespace: str) -> List[str]:
        if vector_ids:
            return vector_ids
        return [f"noop-{i}" for i in range(len(embeddings))]

    async def query(self, embedding: List[float], namespace: str, limit: int = 10, filter: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return []

    async def delete(self, vector_id: str, namespace: str) -> bool:
        return True

    async def get_by_id(self, vector_id: str, namespace: str) -> Optional[Dict[str, Any]]:
        return None
