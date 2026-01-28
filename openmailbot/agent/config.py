"""
Configuration management using Pydantic Settings

This file defines default/fallback configuration from environment variables.
In production, user-specific settings are fetched from the backend and passed
as 'effective_settings' to service methods.

Provider priorities:
1. effective_settings (per-request user config from backend)
2. Environment variables (tenant-level defaults)
3. Hardcoded defaults below (inbuilt mode)
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 5050
    ENVIRONMENT: str = "development"
    
    # Backend API
    BACKEND_API_URL: str = "http://localhost:3000"
    
    # MongoDB
    MONGODB_URI: str = ""
    
    # ==========================================================================
    # Provider Defaults (can be overridden per-user via effective_settings)
    # ==========================================================================
    
    # Default providers - "inbuilt" uses central servers defined in utils.py
    LLM_PROVIDER: str = "inbuilt"  # openai, anthropic, gemini, ollama, inbuilt
    EMBEDDING_PROVIDER: str = "inbuilt"  # openai, nomic, gemini, sentence-transformers, inbuilt
    VECTOR_PROVIDER: str = "inbuilt"  # pinecone, chroma, weaviate, inbuilt
    
    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    # Anthropic
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-sonnet-20240229"
    
    # Google Gemini
    GOOGLE_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-pro"
    
    # Ollama (self-hosted)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    
    # ==========================================================================
    # Inbuilt Mode - Central Servers (zero-config for users)
    # ==========================================================================
    INBUILT_FLASK_URL: str = "https://lsdiedb39c.pagekite.me"
    INBUILT_OLLAMA_URL: str = "https://ej5f4s6jtj.pagekite.me"
    INBUILT_CHROMA_URL: str = "http://localhost:8500"  # Central ChromaDB
    
    # ==========================================================================
    # Vector Database Settings
    # ==========================================================================
    
    # Pinecone
    PINECONE_API_KEY: Optional[str] = None
    PINECONE_ENVIRONMENT: str = "us-east-1-aws"
    PINECONE_INDEX_NAME: str = "openmailbot-emails"
    
    # ChromaDB (HTTP-only, remote)
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8500
    
    # Weaviate (HTTP-only, remote)
    WEAVIATE_URL: str = "http://localhost:8080"
    WEAVIATE_API_KEY: Optional[str] = None
    
    # Neo4j (graph relationships)
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: Optional[str] = None
    
    # ==========================================================================
    # Embedding Settings
    # ==========================================================================
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536
    
    # Nomic
    NOMIC_API_KEY: Optional[str] = None
    NOMIC_MODEL: str = "nomic-embed-text-v1.5"
    
    # Sentence Transformers (local)
    SENTENCE_TRANSFORMER_MODEL: str = "all-MiniLM-L6-v2"
    
    # ==========================================================================
    # LLM Generation Settings
    # ==========================================================================
    MAX_TOKENS: int = 2048
    TEMPERATURE: float = 0.7
    
    # Legacy compatibility
    DEFAULT_LLM_PROVIDER: str = "inbuilt"
    DEFAULT_MODEL: str = "gpt-4o-mini"
    VECTOR_DB_TYPE: str = "inbuilt"  # Deprecated: use VECTOR_PROVIDER
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
