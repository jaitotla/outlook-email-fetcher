"""
ChromaDB Vector Store Client - Persistent Local Storage
Uses local persistent ChromaDB storage for all modes.
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
    ChromaDB client using local persistent storage.
    Works the same for both inbuilt and standard usage.
    """
    
    def __init__(self, settings: Optional[Dict[str, Any]] = None, inbuilt_mode: bool = False):
        """
        Initialize ChromaDB with local persistent storage per user.
        
        Args:
            settings: Dict with 'user_id' key or None (uses USER_ID env var or default)
            inbuilt_mode: Unused, kept for interface compatibility
        """
        settings = settings or {}
        a=settings.get("user_id")
        logger.info(f" look at the userid {a} ")
        # Get user_id from settings, environment, or default
        user_id = settings.get("user_id")
        if not user_id:
            
            raise ValueError("user_id is required for ChromaDBClient")
        
        # Create per-user isolated storage path
        persistent_path = os.path.join(
            os.path.dirname(__file__), 
            "..", "data", user_id, "vector_db"
        )
        os.makedirs(persistent_path, exist_ok=True)
        self.persistent_path = persistent_path
        self._fix_permissions()

        try:
            self.client = chromadb.PersistentClient(
                path=persistent_path,
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            # Fix permissions again to catch any files created during client init
            self._fix_permissions()
            logger.info(f"Initialized local persistent ChromaDB at {persistent_path}")
        except Exception as e:
            raise ConnectionError(
                f"Failed to initialize persistent ChromaDB at {persistent_path}: {e}"
            )

        self.collections = {}
        self._persistent = True
        self.user_id = user_id
    
    def _fix_permissions(self) -> bool:
        """Recursively ensure the chromadb directory and all its files are writable.

        Returns True if all chmod calls succeeded.  Returns False when any call
        fails, which usually means the files are owned by a different OS user and
        require a ``chown`` fix at the OS level.
        """
        all_ok = True
        for dirpath, _dirnames, filenames in os.walk(self.persistent_path):
            try:
                dir_mode = os.stat(dirpath).st_mode
                os.chmod(dirpath, dir_mode | 0o700)
            except OSError as e:
                logger.warning(f"Could not chmod dir {dirpath}: {e}")
                all_ok = False
            for fname in filenames:
                fpath = os.path.join(dirpath, fname)
                try:
                    file_mode = os.stat(fpath).st_mode
                    os.chmod(fpath, file_mode | 0o600)
                except OSError as e:
                    logger.warning(f"Could not chmod file {fpath}: {e}")
                    all_ok = False
        return all_ok

    def _get_collection(self, namespace: str):
        """Get or create collection for namespace"""
        if namespace not in self.collections:
            try:
                # Try to get existing collection first
                self.collections[namespace] = self.client.get_collection(
                    name=namespace
                )
            except Exception:
                # Collection doesn't exist, create it
                self.collections[namespace] = self.client.create_collection(
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

        def _do_upsert() -> None:
            collection.upsert(
                ids=[vector_id],
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[document] if document else None
            )

        try:
            _do_upsert()
        except Exception as e:
            if "readonly" in str(e).lower():
                fixed = self._fix_permissions()
                if not fixed:
                    raise PermissionError(
                        f"ChromaDB at '{self.persistent_path}' is read-only and permissions "
                        f"could not be fixed automatically (files are likely owned by another "
                        f"OS user). Fix with: "
                        f"sudo chown -R $(whoami) {self.persistent_path}"
                    ) from e
                _do_upsert()
            else:
                raise

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
        
        def _do_upsert_batch() -> None:
            collection.upsert(
                ids=vector_ids,
                embeddings=embeddings,
                metadatas=clean_metadatas,
                documents=documents if any(documents) else None
            )

        try:
            _do_upsert_batch()
        except Exception as e:
            if "readonly" in str(e).lower():
                fixed = self._fix_permissions()
                if not fixed:
                    raise PermissionError(
                        f"ChromaDB at '{self.persistent_path}' is read-only and permissions "
                        f"could not be fixed automatically (files are likely owned by another "
                        f"OS user). Fix with: "
                        f"sudo chown -R $(whoami) {self.persistent_path}"
                    ) from e
                _do_upsert_batch()
            else:
                raise

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
