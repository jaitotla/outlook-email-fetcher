"""
ChromaDB Vector Store Client - HTTP-Only Mode
Connects to remote ChromaDB server, does not initialize local storage
"""
from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from uuid import uuid4
import os
import logging

from .base import BaseVectorStore

logger = logging.getLogger(__name__)


class ChromaDBClient(BaseVectorStore):
    """
    ChromaDB client that connects to a remote Chroma server via HTTP.
    Does not create local directories or initialize local storage.
    """
    
    def __init__(self, settings: Optional[Dict[str, Any]] = None, inbuilt_mode: bool = False):
        """
        Initialize ChromaDB HTTP client.
        
        Args:
            settings: Dict with 'chromaUrl' (e.g., 'http://localhost:8000')
            inbuilt_mode: If True, uses INBUILT_CHROMA_URL env var
        """
        settings = settings or {}
        
        if inbuilt_mode:
            # Inbuilt mode uses central tenant Chroma server
            chroma_url = os.environ.get("INBUILT_CHROMA_URL", "http://localhost:8000")
        else:
            chroma_url = settings.get("chromaUrl") or os.environ.get("CHROMA_URL")
        
        if not chroma_url:
            raise ValueError(
                "ChromaDB URL not configured. Set 'chromaUrl' in settings or "
                "CHROMA_URL environment variable. ChromaDB runs in HTTP-only mode."
            )
        
        # Parse host and port from URL
        try:
            from urllib.parse import urlparse
            parsed = urlparse(chroma_url)
            host = parsed.hostname or "localhost"
            port = parsed.port or 8000
        except Exception as e:
            logger.warning(f"Failed to parse Chroma URL '{chroma_url}': {e}. Using defaults.")
            host = "localhost"
            port = 8000
        
        # Initialize HTTP client - no local storage
        try:
            self.client = chromadb.HttpClient(
                host=host,
                port=port,
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            # Test connection
            self.client.heartbeat()
            logger.info(f"Connected to ChromaDB at {host}:{port}")
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to ChromaDB at {host}:{port}. "
                f"Ensure the Chroma server is running. Error: {e}"
            )
        
        self.collections = {}
    
    def _get_collection(self, namespace: str):
        """Get collection for namespace (must already exist on server)"""
        if namespace not in self.collections:
            try:
                # Try to get existing collection first
                self.collections[namespace] = self.client.get_collection(
                    name=namespace
                )
            except Exception:
                # Collection doesn't exist - in remote mode, we create it
                # but the actual data/index lives on the remote server
                self.collections[namespace] = self.client.get_or_create_collection(
                    name=namespace,
                    metadata={"hnsw:space": "cosine"}
                )
        return self.collections[namespace]
    
    async def upsert(
        self,
        vector_id: Optional[str],
        embedding: List[float],
        metadata: Dict[str, Any],
        namespace: str
    ) -> str:
        """Insert or update a single vector"""
        
        if not vector_id:
            vector_id = str(uuid4())
        
        collection = self._get_collection(namespace)
        
        # ChromaDB requires documents for text storage
        document = metadata.pop("text", "") if "text" in metadata else ""
        
        collection.upsert(
            ids=[vector_id],
            embeddings=[embedding],
            metadatas=[metadata],
            documents=[document] if document else None
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
        
        collection = self._get_collection(namespace)
        
        # Extract documents from metadata
        documents = []
        clean_metadatas = []
        for meta in metadatas:
            meta_copy = meta.copy()
            documents.append(meta_copy.pop("text", ""))
            clean_metadatas.append(meta_copy)
        
        collection.upsert(
            ids=vector_ids,
            embeddings=embeddings,
            metadatas=clean_metadatas,
            documents=documents if any(documents) else None
        )
        
        return vector_ids
    
    async def query(
        self,
        embedding: List[float],
        namespace: str,
        limit: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Query similar vectors"""
        
        collection = self._get_collection(namespace)
        
        results = collection.query(
            query_embeddings=[embedding],
            n_results=limit,
            where=filter,
            include=["documents", "metadatas", "distances"]
        )
        
        # Format results to match standard interface
        formatted_results = []
        
        if results["ids"] and len(results["ids"]) > 0:
            for idx, doc_id in enumerate(results["ids"][0]):
                formatted_results.append({
                    "id": doc_id,
                    "score": 1 - results["distances"][0][idx],  # Convert distance to similarity
                    "metadata": results["metadatas"][0][idx],
                    "text": results["documents"][0][idx] if results["documents"][0] else ""
                })
        
        return formatted_results
    
    async def delete(
        self,
        vector_id: str,
        namespace: str
    ) -> bool:
        """Delete a vector"""
        
        try:
            collection = self._get_collection(namespace)
            collection.delete(ids=[vector_id])
            return True
        except Exception as e:
            logger.error(f"Error deleting vector {vector_id}: {e}")
            return False
    
    async def delete_namespace(self, namespace: str) -> bool:
        """Delete an entire namespace/collection"""
        
        try:
            self.client.delete_collection(name=namespace)
            if namespace in self.collections:
                del self.collections[namespace]
            return True
        except Exception as e:
            logger.error(f"Error deleting namespace {namespace}: {e}")
            return False
    
    async def get_by_id(
        self,
        vector_id: str,
        namespace: str
    ) -> Optional[Dict[str, Any]]:
        """Get a vector by ID"""
        
        try:
            collection = self._get_collection(namespace)
            results = collection.get(
                ids=[vector_id],
                include=["embeddings", "metadatas", "documents"]
            )
            
            if results["ids"] and len(results["ids"]) > 0:
                return {
                    "id": results["ids"][0],
                    "embedding": results["embeddings"][0] if results.get("embeddings") else None,
                    "metadata": results["metadatas"][0] if results.get("metadatas") else {},
                    "text": results["documents"][0] if results.get("documents") else ""
                }
            return None
        except Exception as e:
            logger.error(f"Error getting vector {vector_id}: {e}")
            return None
    
    def health_check(self) -> Dict[str, Any]:
        """Check if ChromaDB server is reachable"""
        try:
            heartbeat = self.client.heartbeat()
            return {"status": "ok", "heartbeat": heartbeat}
        except Exception as e:
            return {"status": "error", "error": str(e)}
