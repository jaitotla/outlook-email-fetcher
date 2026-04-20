"""
Pinecone Vector Database Client
"""
from typing import List, Dict, Any, Optional
from uuid import uuid4
import logging
import json
import os
# pcsk_2ge59m_Kh4rYGYGJ6yXqrZSLsmVogrD9JPqxU9TWVcTJQiWZDpBwfefrxckGLo1pPXFSqo
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
    def __init__(self, settings_dict: Optional[Dict[str, Any]] = None):
        """Initialize Pinecone client.

        Args:
            settings_dict: Optional user settings dict. Keys ``vector_api_key`` and
                ``vector_url`` are used when present (user-facing names).  Falls back
                to the legacy ``config_settings.json`` proxy for PINECONE_* keys.
        """
        _s = settings_dict or {}

        # Resolve API key: prefer user settings key, then legacy config
        api_key = (_s.get("vector_api_key") or _s.get("PINECONE_API_KEY")
                   or settings.PINECONE_API_KEY)
        if not api_key:
            raise ValueError("Pinecone API key not configured")

        # Resolve index host / name from user settings
        vector_url = _s.get("vector_url") or ""
        # Extract hostname from full URL if necessary
        if vector_url.startswith("http"):
            from urllib.parse import urlparse
            vector_host = urlparse(vector_url).hostname or ""
        else:
            vector_host = vector_url

        # Derive a logical index name from the host prefix (before first dot)
        index_name_from_host = vector_host.split(".")[0] if vector_host else ""

        self.index_name = (_s.get("PINECONE_INDEX_NAME") or settings.PINECONE_INDEX_NAME
                           or index_name_from_host or "default")

        if not _HAS_PINECONE_CLASS:
            raise RuntimeError(
                "Pinecone initialization failed. The installed pinecone package only supports the new Pinecone class API. "
                "Ensure PINECONE_API_KEY, PINECONE_INDEX_NAME, and PINECONE_CLOUD/PINECONE_REGION are configured."
            )

        try:
            pc = Pinecone(api_key=api_key)

            # If we have a direct host URL, connect to it without listing/creating
            if vector_host:
                self.client = pc
                self.index = pc.Index(host=vector_host)
                logging.getLogger(__name__).info(
                    f"Pinecone index connected via host: {vector_host}"
                )
                return

            # Otherwise fall back to list-and-create approach
            try:
                index_list = pc.list_indexes()
                existing_names = (index_list.names() if hasattr(index_list, 'names')
                                  else [idx.name for idx in index_list])
            except Exception:
                existing_names = []

            if self.index_name not in existing_names:
                cloud = (_s.get("PINECONE_CLOUD") or settings.PINECONE_CLOUD or "aws")
                region = (_s.get("PINECONE_REGION") or settings.PINECONE_REGION or "us-west-2")
                dimension = int(_s.get("EMBEDDING_DIMENSION") or settings.EMBEDDING_DIMENSION or 1536)
                spec = ServerlessSpec(cloud=cloud, region=region)
                pc.create_index(
                    name=self.index_name,
                    dimension=dimension,
                    metric="cosine",
                    spec=spec
                )

            self.client = pc
            self.index = pc.Index(self.index_name)
        except Exception as e:
            logging.getLogger(__name__).error(
                f"Failed to initialize Pinecone via new Pinecone class: {e}"
            )
            raise
    
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
