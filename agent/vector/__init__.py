"""
Vector database clients initialization
"""
from typing import Dict, Any, Optional
from .base import BaseVectorStore
from .pinecone_client import PineconeClient
from .chroma_client import ChromaDBClient
from .noop_client import NoOpVectorClient
import logging


def get_vector_client(provider: str, settings: Optional[Dict[str, Any]] = None) -> BaseVectorStore:
    """
    Factory function to get the appropriate vector client based on provider.
    
    Args:
        provider: One of 'pinecone', 'chroma', 'weaviate', 'inbuilt'
        settings: Optional settings dict with provider-specific config
    
    Returns:
        BaseVectorStore implementation
    """
    provider = (provider or "").lower()
    
    if provider == "pinecone":
        try:
            return PineconeClient(settings_dict=settings)
        except Exception as e:
            logging.getLogger(__name__).warning(f"Pinecone init failed, falling back to NoOpVectorClient: {e}")
            return NoOpVectorClient()
    elif provider == "chroma":
        return ChromaDBClient(settings=settings)
    elif provider == "weaviate":
        from .weaviate_client import WeaviateClient
        return WeaviateClient(settings=settings)
    elif provider in ("inbuilt", "manotr"):
        # Inbuilt/manotr mode uses tenant's Chroma instance
        return ChromaDBClient(settings=settings, inbuilt_mode=True)
    else:
        raise ValueError(f"Unsupported vector DB provider: {provider}. "
                        f"Supported: pinecone, chroma, weaviate, inbuilt")


__all__ = ['BaseVectorStore', 'PineconeClient', 'ChromaDBClient', 'get_vector_client']
