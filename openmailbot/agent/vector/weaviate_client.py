"""
Weaviate Vector Store Client - HTTP-Only Mode
Connects to remote Weaviate server via HTTP
"""
from typing import List, Dict, Any, Optional
import weaviate
from weaviate.classes.init import Auth
from weaviate.classes.query import MetadataQuery
from weaviate.classes.config import Configure, Property, DataType
from uuid import uuid4
import os
import logging

from .base import BaseVectorStore

logger = logging.getLogger(__name__)


class WeaviateClient(BaseVectorStore):
    """
    Weaviate client that connects to a remote Weaviate server via HTTP.
    Does not initialize local storage - all data lives on the remote server.
    """
    
    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        """
        Initialize Weaviate HTTP client.
        
        Args:
            settings: Dict with:
                - 'weaviateUrl': Weaviate server URL (e.g., 'https://your-cluster.weaviate.network')
                - 'weaviateApiKey': API key for authentication (optional for local)
        """
        settings = settings or {}
        
        weaviate_url = settings.get("vector_url") or os.environ.get("WEAVIATE_URL")
        weaviate_api_key = settings.get("vector_api_key") or os.environ.get("WEAVIATE_API_KEY")
        
        if not weaviate_url:
            raise ValueError(
                "Weaviate URL not configured. Set 'vector_url' in settings or "
                "WEAVIATE_URL environment variable."
            )
        
        # Connect to Weaviate
        try:
            if weaviate_api_key:
                # Weaviate Cloud Services or authenticated instance
                self.client = weaviate.connect_to_custom(
                    http_host=weaviate_url.replace("https://", "").replace("http://", "").split(":")[0],
                    http_port=443 if weaviate_url.startswith("https") else 8080,
                    http_secure=weaviate_url.startswith("https"),
                    grpc_host=weaviate_url.replace("https://", "").replace("http://", "").split(":")[0],
                    grpc_port=50051,
                    grpc_secure=weaviate_url.startswith("https"),
                    auth_credentials=Auth.api_key(weaviate_api_key)
                )
            else:
                # Local Weaviate instance without auth
                from urllib.parse import urlparse
                parsed = urlparse(weaviate_url)
                host = parsed.hostname or "localhost"
                port = parsed.port or 8080
                
                self.client = weaviate.connect_to_local(
                    host=host,
                    port=port
                )
            
            # Test connection
            self.client.is_ready()
            logger.info(f"Connected to Weaviate at {weaviate_url}")
            
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to Weaviate at {weaviate_url}. "
                f"Ensure the Weaviate server is running. Error: {e}"
            )
        
        self._collections_cache = {}
    
    def _get_class_name(self, namespace: str) -> str:
        """Convert namespace to valid Weaviate class name (PascalCase, alphanumeric)"""
        # Replace invalid characters and convert to PascalCase
        clean = "".join(c if c.isalnum() else "_" for c in namespace)
        parts = clean.split("_")
        return "".join(part.capitalize() for part in parts if part)
    
    def _ensure_collection(self, namespace: str):
        """Ensure collection exists for namespace"""
        class_name = self._get_class_name(namespace)
        
        if class_name in self._collections_cache:
            return self._collections_cache[class_name]
        
        try:
            # Check if collection exists
            if not self.client.collections.exists(class_name):
                # Create collection with vector index
                collection = self.client.collections.create(
                    name=class_name,
                    vectorizer_config=Configure.Vectorizer.none(),  # We provide our own vectors
                    properties=[
                        Property(name="text", data_type=DataType.TEXT),
                        Property(name="metadata_json", data_type=DataType.TEXT),
                        Property(name="original_id", data_type=DataType.TEXT),
                    ]
                )
                logger.info(f"Created Weaviate collection: {class_name}")
            else:
                collection = self.client.collections.get(class_name)
            
            self._collections_cache[class_name] = collection
            return collection
            
        except Exception as e:
            logger.error(f"Error ensuring collection {class_name}: {e}")
            raise
    
    async def upsert(
        self,
        vector_id: Optional[str],
        embedding: List[float],
        metadata: Dict[str, Any],
        namespace: str
    ) -> str:
        """Insert or update a single vector"""
        import json
        
        if not vector_id:
            vector_id = str(uuid4())
        
        collection = self._ensure_collection(namespace)
        
        # Extract text from metadata
        text = metadata.pop("text", "") if "text" in metadata else ""
        
        properties = {
            "text": text,
            "metadata_json": json.dumps(metadata),
            "original_id": vector_id
        }
        
        try:
            # Try to update first, then insert
            collection.data.insert(
                properties=properties,
                vector=embedding,
                uuid=vector_id
            )
        except Exception:
            # If insert fails (exists), try update
            try:
                collection.data.update(
                    uuid=vector_id,
                    properties=properties,
                    vector=embedding
                )
            except Exception as e:
                logger.error(f"Error upserting vector {vector_id}: {e}")
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
        import json
        
        if not vector_ids:
            vector_ids = [str(uuid4()) for _ in embeddings]
        
        collection = self._ensure_collection(namespace)
        
        # Batch insert
        with collection.batch.dynamic() as batch:
            for i, (vid, emb, meta) in enumerate(zip(vector_ids, embeddings, metadatas)):
                text = meta.pop("text", "") if "text" in meta else ""
                properties = {
                    "text": text,
                    "metadata_json": json.dumps(meta),
                    "original_id": vid
                }
                batch.add_object(
                    properties=properties,
                    vector=emb,
                    uuid=vid
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
        import json
        
        collection = self._ensure_collection(namespace)
        
        # Perform vector search
        results = collection.query.near_vector(
            near_vector=embedding,
            limit=limit,
            return_metadata=MetadataQuery(distance=True),
            return_properties=["text", "metadata_json", "original_id"]
        )
        
        # Format results
        formatted_results = []
        for obj in results.objects:
            metadata = {}
            if obj.properties.get("metadata_json"):
                try:
                    metadata = json.loads(obj.properties["metadata_json"])
                except:
                    pass
            
            formatted_results.append({
                "id": obj.properties.get("original_id", str(obj.uuid)),
                "score": 1 - (obj.metadata.distance or 0),  # Convert distance to similarity
                "metadata": metadata,
                "text": obj.properties.get("text", "")
            })
        
        return formatted_results
    
    async def delete(
        self,
        vector_id: str,
        namespace: str
    ) -> bool:
        """Delete a vector"""
        
        try:
            collection = self._ensure_collection(namespace)
            collection.data.delete_by_id(uuid=vector_id)
            return True
        except Exception as e:
            logger.error(f"Error deleting vector {vector_id}: {e}")
            return False
    
    async def delete_namespace(self, namespace: str) -> bool:
        """Delete an entire namespace/collection"""
        
        try:
            class_name = self._get_class_name(namespace)
            self.client.collections.delete(class_name)
            if class_name in self._collections_cache:
                del self._collections_cache[class_name]
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
        import json
        
        try:
            collection = self._ensure_collection(namespace)
            obj = collection.query.fetch_object_by_id(
                uuid=vector_id,
                include_vector=True,
                return_properties=["text", "metadata_json", "original_id"]
            )
            
            if obj:
                metadata = {}
                if obj.properties.get("metadata_json"):
                    try:
                        metadata = json.loads(obj.properties["metadata_json"])
                    except:
                        pass
                
                return {
                    "id": obj.properties.get("original_id", str(obj.uuid)),
                    "embedding": obj.vector.get("default") if obj.vector else None,
                    "metadata": metadata,
                    "text": obj.properties.get("text", "")
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting vector {vector_id}: {e}")
            return None
    
    def health_check(self) -> Dict[str, Any]:
        """Check if Weaviate server is reachable"""
        try:
            is_ready = self.client.is_ready()
            return {"status": "ok" if is_ready else "error", "ready": is_ready}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def close(self):
        """Close the Weaviate client connection"""
        try:
            self.client.close()
        except:
            pass
