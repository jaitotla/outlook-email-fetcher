"""
Services initialization
"""
#from .ingestion import EmailIngestionService
from .embeddings import EmbeddingService
from .rag import RAGService
from .llm import LLMService
from .preprocessing_emails import EmailPreprocessingPipeline
from .label_pipeline import EmailLabelPipeline

__all__ = [
    'EmailIngestionService', 
    'EmbeddingService', 
    'RAGService', 
    'LLMService',
    'EmailPreprocessingPipeline',
    'EmailLabelPipeline'
]
