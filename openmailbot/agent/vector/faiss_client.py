"""
FAISS Vector Database Client (Local)
"""
from typing import List, Dict, Any, Optional
import faiss
import numpy as np
import pickle
import os
from uuid import uuid4
from pathlib import Path

from config import settings


class FAISSClient:
    def __init__(self):
        self.dimension = settings.EMBEDDING_DIMENSION
        self.data_dir = Path("data/faiss")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Store namespace-specific indexes
        self.indexes = {}
        self.id_maps = {}  # Map vector IDs to internal FAISS IDs
        self.metadatas = {}  # Store metadata separately
    
    def _get_index_path(self, namespace: str) -> Path:
        return self.data_dir / f"{namespace}.index"
    
    def _get_metadata_path(self, namespace: str) -> Path:
        return self.data_dir / f"{namespace}.metadata.pkl"
    
    def _load_index(self, namespace: str):
        """Load or create FAISS index for namespace"""
        
        if namespace in self.indexes:
            return
        
        index_path = self._get_index_path(namespace)
        metadata_path = self._get_metadata_path(namespace)
        
        if index_path.exists():
            # Load existing index
            self.indexes[namespace] = faiss.read_index(str(index_path))
            
            # Load metadata
            with open(metadata_path, 'rb') as f:
                data = pickle.load(f)
                self.id_maps[namespace] = data['id_map']
                self.metadatas[namespace] = data['metadatas']
        else:
            # Create new index
            self.indexes[namespace] = faiss.IndexFlatL2(self.dimension)
            self.id_maps[namespace] = {}
            self.metadatas[namespace] = {}
    
    def _save_index(self, namespace: str):
        """Save FAISS index and metadata to disk"""
        
        index_path = self._get_index_path(namespace)
        metadata_path = self._get_metadata_path(namespace)
        
        # Save index
        faiss.write_index(self.indexes[namespace], str(index_path))
        
        # Save metadata
        with open(metadata_path, 'wb') as f:
            pickle.dump({
                'id_map': self.id_maps[namespace],
                'metadatas': self.metadatas[namespace]
            }, f)
    
    async def upsert(
        self,
        vector_id: Optional[str],
        embedding: List[float],
        metadata: Dict[str, Any],
        namespace: str
    ) -> str:
        """Insert or update a vector"""
        
        self._load_index(namespace)
        
        if not vector_id:
            vector_id = str(uuid4())
        
        # Convert to numpy array
        vector = np.array([embedding], dtype=np.float32)
        
        # Add to FAISS index
        internal_id = self.indexes[namespace].ntotal
        self.indexes[namespace].add(vector)
        
        # Store mappings
        self.id_maps[namespace][vector_id] = internal_id
        self.metadatas[namespace][internal_id] = metadata
        
        # Save to disk
        self._save_index(namespace)
        
        return vector_id
    
    async def upsert_batch(
        self,
        vector_ids: Optional[List[str]],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        namespace: str
    ) -> List[str]:
        """Insert or update multiple vectors"""
        
        self._load_index(namespace)
        
        if not vector_ids:
            vector_ids = [str(uuid4()) for _ in embeddings]
        
        # Convert to numpy array
        vectors = np.array(embeddings, dtype=np.float32)
        
        # Get starting internal ID
        start_id = self.indexes[namespace].ntotal
        
        # Add to FAISS index
        self.indexes[namespace].add(vectors)
        
        # Store mappings
        for i, (vector_id, metadata) in enumerate(zip(vector_ids, metadatas)):
            internal_id = start_id + i
            self.id_maps[namespace][vector_id] = internal_id
            self.metadatas[namespace][internal_id] = metadata
        
        # Save to disk
        self._save_index(namespace)
        
        return vector_ids
    
    async def query(
        self,
        embedding: List[float],
        namespace: str,
        limit: int = 10,
        filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Query similar vectors"""
        
        self._load_index(namespace)
        
        # Convert to numpy array
        query_vector = np.array([embedding], dtype=np.float32)
        
        # Search
        distances, indices = self.indexes[namespace].search(query_vector, limit)
        
        # Convert results
        results = []
        for distance, idx in zip(distances[0], indices[0]):
            if idx == -1:  # FAISS returns -1 for missing results
                continue
            
            # Find vector ID
            vector_id = None
            for vid, iid in self.id_maps[namespace].items():
                if iid == idx:
                    vector_id = vid
                    break
            
            if vector_id is None:
                continue
            
            metadata = self.metadatas[namespace].get(idx, {})
            
            # Apply filter if provided
            if filter:
                match = all(
                    metadata.get(k) == v
                    for k, v in filter.items()
                )
                if not match:
                    continue
            
            # Convert L2 distance to similarity score (inverse)
            similarity = 1 / (1 + float(distance))
            
            results.append({
                "id": vector_id,
                "score": similarity,
                "metadata": metadata
            })
        
        return results
    
    async def delete(
        self,
        vector_ids: List[str],
        namespace: str
    ):
        """Delete vectors by IDs"""
        
        self._load_index(namespace)
        
        # FAISS doesn't support deletion, so we need to rebuild the index
        # Remove from id_map and metadata
        for vector_id in vector_ids:
            internal_id = self.id_maps[namespace].get(vector_id)
            if internal_id is not None:
                del self.id_maps[namespace][vector_id]
                if internal_id in self.metadatas[namespace]:
                    del self.metadatas[namespace][internal_id]
        
        # Save (metadata is updated)
        self._save_index(namespace)
    
    async def delete_namespace(self, namespace: str):
        """Delete all vectors in a namespace"""
        
        index_path = self._get_index_path(namespace)
        metadata_path = self._get_metadata_path(namespace)
        
        # Remove files
        if index_path.exists():
            index_path.unlink()
        if metadata_path.exists():
            metadata_path.unlink()
        
        # Clear from memory
        if namespace in self.indexes:
            del self.indexes[namespace]
            del self.id_maps[namespace]
            del self.metadatas[namespace]
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        
        stats = {}
        for namespace in self.indexes:
            stats[namespace] = {
                "total_vectors": self.indexes[namespace].ntotal
            }
        
        return stats
