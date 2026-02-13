"""
Pinecone Vector Database Client
"""
from typing import List, Dict, Any, Optional
from uuid import uuid4
import logging
import json
import os

try:
    # Newer Pinecone versions expose a Pinecone class
    from pinecone import Pinecone, ServerlessSpec
    _HAS_PINECONE_CLASS = True
except Exception:
    Pinecone = None
    ServerlessSpec = None
    _HAS_PINECONE_CLASS = False

# Also attempt to import the pinecone module (may be present without top-level init)
try:
    import pinecone
except Exception:
    pinecone = None

from .base import BaseVectorStore


# Load settings from config_settings.json
def _load_settings():
    """Load settings from config_settings.json"""
    config_path = os.path.join(os.path.dirname(__file__), "..", "config_settings.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to load config_settings.json: {e}")
    return {}


class _SettingsProxy:
    """Proxy to access settings from JSON config"""
    def __init__(self):
        self._settings = _load_settings()
    
    def __getattr__(self, name):
        return self._settings.get(name)


settings = _SettingsProxy()


class PineconeClient(BaseVectorStore):
    def __init__(self):
        if not settings.PINECONE_API_KEY:
            raise ValueError("Pinecone API key not configured")

        self.index_name = settings.PINECONE_INDEX_NAME

        # Use new Pinecone class if available
        if _HAS_PINECONE_CLASS:
            try:
                pc = Pinecone(api_key=settings.PINECONE_API_KEY)

                # Get list of existing index names
                try:
                    index_list = pc.list_indexes()
                    existing_names = index_list.names() if hasattr(index_list, 'names') else [idx.name for idx in index_list]
                except Exception:
                    existing_names = []

                if self.index_name not in existing_names:
                    # Create index with ServerlessSpec (required in new API)
                    spec = ServerlessSpec(
                        cloud=getattr(settings, 'PINECONE_CLOUD', 'aws'),
                        region=getattr(settings, 'PINECONE_REGION', 'us-west-2')
                    )
                    pc.create_index(
                        name=self.index_name,
                        dimension=settings.EMBEDDING_DIMENSION,
                        metric="cosine",
                        spec=spec
                    )

                # Keep reference to client and index
                self.client = pc
                self.index = self.client.Index(self.index_name)
                return
            except Exception as e:
                logging.getLogger(__name__).error(
                    f"Failed to initialize Pinecone via new Pinecone class: {e}"
                )
                raise

        # New Pinecone class API is required; legacy pinecone.init() is no longer supported
        raise RuntimeError(
            "Pinecone initialization failed. The installed pinecone package only supports the new Pinecone class API. "
            "Ensure PINECONE_API_KEY, PINECONE_INDEX_NAME, and PINECONE_CLOUD/PINECONE_REGION are configured."
        )
    
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
